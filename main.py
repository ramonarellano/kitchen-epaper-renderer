import os, io, re, math, datetime, json, requests
from PIL import Image
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import secretmanager
import logging
import pytz

from sketch import (Sketch, Font, weather_icon, ellipse_pts, bin_icon, tooth_icon, plane_icon, star_icon,
                    wind_icon, drop_icon, _sun, RED, BLUE, GREEN, ORANGE, YELLOW)
from seasonal import decorate, scene, day_name, next_countdown

# env vars (set these when deploying)
CALENDAR_ID = os.environ['CALENDAR_ID']
YR_LAT      = os.environ['YR_LAT']
YR_LON      = os.environ['YR_LON']
SECRET_NAME = os.environ['SECRET_NAME']  # e.g. "projects/12345/secrets/calendar-sa-key"

# Configure logging
logging.basicConfig(level=logging.INFO)

# All displayed times and day boundaries use Norwegian local time
OSLO_TZ = pytz.timezone('Europe/Oslo')

# Load fonts once on cold start (Kalam: handwritten, SIL Open Font License)
FONT_DIR = 'fonts'
KALAM_REGULAR = os.path.join(FONT_DIR, 'Kalam-Regular.ttf')
KALAM_BOLD    = os.path.join(FONT_DIR, 'Kalam-Bold.ttf')
font_date     = Font(KALAM_BOLD, 34)     # header date
font_sub      = Font(KALAM_REGULAR, 18)  # header subtitle (week, sun times)
font_now_temp = Font(KALAM_BOLD, 40)     # current temperature
font_now      = Font(KALAM_REGULAR, 17)  # current conditions
font_section  = Font(KALAM_BOLD, 21)     # "I dag" / "I morgen"
font_daynum   = Font(KALAM_BOLD, 21)     # day number in agenda
font_weekday  = Font(KALAM_REGULAR, 17)  # short weekday in agenda
font_time     = Font(KALAM_BOLD, 17)     # event start time
font_event    = Font(KALAM_REGULAR, 19)  # event titles
font_badge    = Font(KALAM_BOLD, 15)     # person initials
font_chart_t  = Font(KALAM_BOLD, 17)     # chart temperatures
font_chart_h  = Font(KALAM_BOLD, 16)     # chart hours
font_chart    = Font(KALAM_REGULAR, 16)  # chart wind / summary
font_note     = Font(KALAM_REGULAR, 18)  # countdown note
font_note_b   = Font(KALAM_BOLD, 20)
font_tiny     = Font(KALAM_REGULAR, 14)  # last updated

# Norwegian names, independent of which locales the runtime has installed
WEEKDAYS = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag', 'lørdag', 'søndag']
WEEKDAYS_SHORT = ['man', 'tir', 'ons', 'tor', 'fre', 'lør', 'søn']
MONTHS = ['januar', 'februar', 'mars', 'april', 'mai', 'juni', 'juli',
          'august', 'september', 'oktober', 'november', 'desember']
MONTHS_SHORT = ['jan', 'feb', 'mar', 'apr', 'mai', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'des']

# Family members: an event title prefixed with initials ("S: Piano", "K&R&E: Høsttreff")
# gets a coloured ring per person instead of the prefix.
PEOPLE = {'K': RED, 'S': BLUE, 'R': GREEN, 'E': ORANGE, 'M': YELLOW}
_P = ''.join(PEOPLE)
PEOPLE_PREFIX = re.compile(rf'^([{_P}](?:\s*[&+,/]\s*[{_P}])*)(?::\s*|\s+)(\S.*)$')

# Keyword -> small icon shown in the time column of all-day / ongoing events
EVENT_ICONS = [
    (re.compile(r'søppel|avfall|papir|plast|glass', re.I), bin_icon),
    (re.compile(r'tannlege', re.I), tooth_icon),
    (re.compile(r'\bfly\b|flyplass|gardermoen|reise', re.I), plane_icon),
]

CONDITIONS = {'clearsky': 'klart', 'fair': 'lettskyet', 'partlycloudy': 'delvis skyet',
              'cloudy': 'skyet', 'fog': 'tåke'}

def precip_kind(code):
    base = (code or '').partition('_')[0]
    return 'snø' if 'snow' in base else 'sludd' if 'sleet' in base else 'regn'

def condition_text(code):
    """Norwegian description of a Met.no symbol code, e.g. 'lett regn', 'snøbyger og torden'."""
    base = (code or 'cloudy').partition('_')[0]
    if base in CONDITIONS:
        return CONDITIONS[base]
    kind = precip_kind(base)
    if 'showers' in base:
        text = kind + 'byger' if kind != 'regn' else 'regnbyger'
    else:
        text = kind
    if base.startswith('light'):
        text = 'lett ' + text
    elif base.startswith('heavy'):
        text = 'kraftig ' + text
    if 'thunder' in base:
        text += ' og torden'
    return text

def part_of_day(hour):
    return 'i natt' if hour < 6 else 'i formiddag' if hour < 12 else 'i ettermiddag' if hour < 18 else 'i kveld'

def sun_times(d, lat, lon):
    """Sunrise and sunset (local datetimes) for date d, or None during polar day/night."""
    def event(rising):
        n = d.timetuple().tm_yday
        lng_hour = lon / 15
        t = n + ((6 if rising else 18) - lng_hour) / 24
        m = 0.9856 * t - 3.289
        l = (m + 1.916 * math.sin(math.radians(m)) + 0.020 * math.sin(math.radians(2 * m)) + 282.634) % 360
        ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l)))) % 360
        ra = (ra + (l // 90) * 90 - (ra // 90) * 90) / 15
        sin_dec = 0.39782 * math.sin(math.radians(l))
        cos_dec = math.cos(math.asin(sin_dec))
        cos_h = (math.cos(math.radians(90.833)) - sin_dec * math.sin(math.radians(lat))) / (cos_dec * math.cos(math.radians(lat)))
        if not -1 <= cos_h <= 1:
            return None
        h = (360 - math.degrees(math.acos(cos_h)) if rising else math.degrees(math.acos(cos_h))) / 15
        ut = (h + ra - 0.06571 * t - 6.622 - lng_hour) % 24
        utc = datetime.datetime(d.year, d.month, d.day, tzinfo=pytz.utc) + datetime.timedelta(hours=ut)
        return utc.astimezone(OSLO_TZ)
    rise, set_ = event(True), event(False)
    return (rise, set_) if rise and set_ else None

def load_credentials():
    client = secretmanager.SecretManagerServiceClient()
    name = f"{SECRET_NAME}/versions/latest"
    payload = client.access_secret_version(name=name).payload.data.decode()
    info = json.loads(payload)
    return service_account.Credentials.from_service_account_info(
        info,
        scopes=['https://www.googleapis.com/auth/calendar.readonly']
    )

def get_events():
    creds   = load_credentials()
    service = build('calendar','v3',credentials=creds)
    now     = datetime.datetime.utcnow()
    # Fetch up to 14 days ahead to ensure enough events to fill the image
    then    = now + datetime.timedelta(days=14)
    items   = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat()+'Z',
        timeMax=then.isoformat()+'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items',[])
    # Return as list of (date-str, start, end, summary)
    events = []
    for evt in items:
        start = evt['start'].get('dateTime', evt['start'].get('date'))
        end = evt['end'].get('dateTime', evt['end'].get('date'))
        date = start[:10]
        summary = evt.get('summary','(No title)')
        events.append((date, start, end, summary))
    return events

def get_weather():
    """Hourly forecast for today and tomorrow (Oslo time) plus the current conditions."""
    url = f'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={YR_LAT}&lon={YR_LON}'
    headers = {'User-Agent':'kitchen-epaper/1.0'}
    data = requests.get(url, headers=headers).json()
    now = datetime.datetime.now(tz=OSLO_TZ)
    days = (now.date(), now.date() + datetime.timedelta(days=1))
    hours = []
    for ts in data['properties']['timeseries']:
        t = datetime.datetime.fromisoformat(ts['time'].replace('Z','+00:00')).astimezone(OSLO_TZ)
        if t.date() not in days:
            continue
        details = ts['data']['instant']['details']
        nxt = ts['data'].get('next_1_hours') or ts['data'].get('next_6_hours') or {}
        hours.append({
            'time': t,
            'date': t.date(),
            'hour': t.hour,
            'temp': details['air_temperature'],
            'wind': details.get('wind_speed', 0),
            'precip': nxt.get('details', {}).get('precipitation_amount', 0),
            'icon': nxt.get('summary', {}).get('symbol_code'),
        })
    # The first timeseries entry is the current hour
    current = next((h for h in hours if h['time'] > now - datetime.timedelta(hours=1)), hours[0] if hours else None)
    return {'now': current, 'hours': hours}

W, H = 800, 480
AGENDA_X0, AGENDA_X1 = 26, 490   # left column
CHART_X, CHART_W = 532, 246      # right column
BOTTOM = 458                     # lowest baseline for content

def _until(d, shown_on):
    """'fredag' within a week, else '19. okt'."""
    if (d - shown_on).days < 7:
        return WEEKDAYS[d.weekday()]
    return f"{d.day}. {MONTHS_SHORT[d.month - 1]}"

def _prepare_event(start, end, summary, shown_on):
    """Turn a calendar event into a display row for the date shown_on."""
    summary = summary.strip()
    who, title = '', summary
    m = PEOPLE_PREFIX.match(summary)
    if m:
        who, title = re.sub(r'[^A-Z]', '', m.group(1)), m.group(2)
    icon = next((fn for rx, fn in EVENT_ICONS if rx.search(summary)), None)
    time = None
    try:
        if len(start) == 10:
            # All-day events have date-only start/end ('YYYY-MM-DD'); end is exclusive
            last_day = datetime.date.fromisoformat(end) - datetime.timedelta(days=1)
            if last_day > shown_on:
                title += f" – til {_until(last_day, shown_on)}"
        else:
            st = datetime.datetime.fromisoformat(start.replace('Z','+00:00')).astimezone(OSLO_TZ)
            et = datetime.datetime.fromisoformat(end.replace('Z','+00:00')).astimezone(OSLO_TZ)
            if st.date() >= shown_on:
                time = st.strftime('%H:%M')
            if et.date() > shown_on:
                title += f" – til {_until(et.date(), shown_on)}"
            elif st.date() < shown_on:
                title += f" – til {et.strftime('%H:%M')}"
    except ValueError:
        pass
    if time is None and icon is None:
        icon = star_icon
    return {'time': time, 'icon': icon, 'who': who, 'title': title}

def _row(sk, x, y, ev, max_x):
    """One agenda row with its baseline at y: time (or icon), person rings, title."""
    if ev['time']:
        sk.text((x, y), ev['time'], font_time)
    else:
        ev['icon'](sk, x + 8, y - 18, 22)
    cx = x + 56
    for i, letter in enumerate(ev['who']):
        px = cx + 10 + i * 24
        sk.stroke(ellipse_pts(px, y - 6, 10.5, 10.5, n=24, start=sk.rng.uniform(0, 6)),
                  width=2.6, amp=0.3, closed=True, color=PEOPLE.get(letter))
        sk.text((px, y - 0.5), letter, font_badge, anchor='ms')
    if ev['who']:
        cx += len(ev['who']) * 24 + 5
    title = ev['title']
    max_w = max_x - cx
    if font_event.width(title) > max_w:
        while title and font_event.width(title + '…') > max_w:
            title = title[:-1]
        title = title.rstrip() + '…'
    sk.text((cx, y), title, font_event)
    sk.mark((x, y - 18, max_x, y + 6))

def _chart_periods(hours, now):
    """Rest of today while there is enough of it left, otherwise tomorrow (08-20, every 2 hours)."""
    today = now.date()
    left = [h for h in hours if h['date'] == today and h['hour'] % 2 == 0 and now.hour < h['hour'] <= 22]
    if now.hour < 14 and len(left) >= 4:
        return "Resten av dagen", left[:7]
    tomorrow = today + datetime.timedelta(days=1)
    return "I morgen", [h for h in hours if h['date'] == tomorrow and h['hour'] % 2 == 0 and 8 <= h['hour'] <= 20]

def _chart_summary(periods):
    wet = [p for p in periods if p['precip'] >= 0.1]
    if not wet:
        codes = [(p['icon'] or 'cloudy').partition('_')[0] for p in periods]
        return condition_text(max(set(codes), key=codes.count)) if codes else ''
    kind = precip_kind(wet[0]['icon'])
    if len(wet) >= len(periods) - 1:
        return f"{kind} hele dagen"
    h = wet[0]['hour']
    return f"{kind} {'om morgenen' if h < 11 else 'midt på dagen' if h < 16 else 'i kveld'}"

def _draw_header(sk, now, current):
    today = now.date()
    sk.text((30, 54), f"{WEEKDAYS[today.weekday()].capitalize()} {today.day}. {MONTHS[today.month - 1]}", font_date)
    parts = [f"uke {today.isocalendar()[1]}"]
    name = day_name(today)
    if name:
        parts.append(name)
    sub = '  ·  '.join(parts)
    times = sun_times(today, float(YR_LAT), float(YR_LON))
    if times:
        sub += '  ·  '
    box = sk.text((32, 80), sub, font_sub)
    if times:
        sx = box[2] + 4
        _sun(sk, sx + 9, 74, 4.5, tint=True)
        sk.text((sx + 24, 80), f"{times[0].strftime('%H:%M')} – {times[1].strftime('%H:%M')}", font_sub)
    if current:
        label = f"{part_of_day(now.hour)}, {condition_text(current['icon'])}"
        wind = f"{round(current['wind'])} m/s"
        label_w = max(font_now.width(label), font_now.width(wind), 40)
        lx = 772 - label_w
        temp = f"{round(current['temp'])}°"
        tx = lx - 12 - font_now_temp.width(temp)
        weather_icon(sk, current['icon'], tx - 52, 22, 46)
        sk.text((tx, 62), temp, font_now_temp)
        sk.text((lx, 44), label, font_now)
        sk.text((lx, 65), wind, font_now)
    sk.stroke([(24, 92), (400, 93.5), (776, 94)], width=2.2, amp=0.8)
    sk.mark((0, 0, W, 98))

def _draw_agenda(sk, events, today):
    from collections import defaultdict
    by_date = defaultdict(list)
    for date, start, end, summary in events:
        # Ongoing events that started before today are listed under today
        by_date[max(date, today.isoformat())].append((start, end, summary))
    x0, x1 = AGENDA_X0, AGENDA_X1

    # "I dag" card
    today_rows = [_prepare_event(st, et, sm, today) for st, et, sm in by_date.pop(today.isoformat(), [])]
    max_rows = (BOTTOM - 150) // 25
    today_rows = today_rows[:max_rows]
    card_h = 34 + max(1, len(today_rows)) * 25
    sk.rect(x0, 100, x1, 100 + card_h, width=2.4, amp=0.8)
    mark_w = font_section.width("I dag")
    sk.stroke([(x0 + 6, 121), (x0 + 20 + mark_w, 119)], width=9, amp=0.4, color=YELLOW)  # highlighter
    sk.text((x0 + 12, 124), "I dag", font_section)
    y = 150
    for ev in today_rows:
        _row(sk, x0 + 14, y, ev, x1 - 6)
        y += 25
    if not today_rows:
        sk.text((x0 + 70, y), "Ingen avtaler", font_event)
    sk.mark((x0, 96, x1, 100 + card_h + 4))

    # Following days, compact
    y = 100 + card_h + 26
    days = sorted(by_date.items())
    for i, (date, items) in enumerate(days):
        if y > BOTTOM:
            break
        d = datetime.date.fromisoformat(date)
        sk.text((x0 + 2, y), WEEKDAYS_SHORT[d.weekday()], font_weekday)
        sk.text((x0 + 64, y), str(d.day), font_daynum, anchor='rs')
        shown = 0
        for st, et, sm in items:
            if y + shown * 24 > BOTTOM:
                break
            _row(sk, x0 + 76, y + shown * 24, _prepare_event(st, et, sm, d), x1)
            shown += 1
        sk.mark((x0, y - 22, x1, y + max(shown - 1, 0) * 24 + 6))  # whole day block
        y += shown * 24 + 6
        if i < len(days) - 1 and y + 6 <= BOTTOM:
            sk.dashed((x0 + 4, y - 17), (x1, y - 16))
        y += 6

def _draw_chart(sk, hours, now):
    title, hrs = _chart_periods(hours, now)
    if len(hrs) < 2:
        return
    rx, rw = CHART_X, CHART_W
    title_box = sk.text((rx, 122), title, font_section)
    summary = _chart_summary(hrs)
    room = rx + rw - title_box[2] - 10
    if summary and font_chart.width(summary) > room:
        summary = summary.split(' ')[0]  # e.g. "regn om morgenen" -> "regn"
    if summary and font_chart.width(summary) <= room:
        sk.text((rx + rw, 122), summary, font_chart, anchor='rs')
    n = len(hrs)
    dx = (rw - 36) / (n - 1)
    x0 = rx + 28
    temps = [h['temp'] for h in hrs]
    tmin, tmax = min(temps) - 1, max(temps) + 1
    y_of = lambda t: 226 - (t - tmin) / (tmax - tmin) * 44
    pts = [(x0 + i * dx, y_of(h['temp'])) for i, h in enumerate(hrs)]
    for (x, _), h in zip(pts, hrs):
        weather_icon(sk, h['icon'], x - 14, 130, 28)
    sk.curve(pts, width=2.4, amp=0.4, color=RED)
    any_wet = False
    for (x, y), h in zip(pts, hrs):
        sk.dot(x, y, 3.2)
        sk.text((x, y - 9), f"{round(h['temp'])}°", font_chart_t, anchor='ms')
        sk.text((x, 256), f"{h['hour']:02d}", font_chart_h, anchor='ms')
        sk.text((x, 275), str(round(h['wind'])), font_chart, anchor='ms')
        if h['precip'] >= 0.1:
            any_wet = True
            sk.text((x, 293), f"{h['precip']:.1f}".replace('.', ','), font_chart_h, anchor='ms')
    sk.line((x0 - 8, 238), (x0 + (n - 1) * dx + 8, 238), width=1.6, amp=0.6)
    wind_icon(sk, rx - 8, 262, 20)
    if any_wet:
        drop_icon(sk, rx - 3, 280, 13)

def _draw_vignette(sk, today):
    rx, rw = CHART_X, CHART_W
    top = 304
    countdown = next_countdown(today)
    if countdown:
        name, left, icon = countdown
        sk.rect(rx + 2, top, rx + rw - 2, top + 34, width=1.8, amp=0.8)
        if icon:
            icon(sk, rx + 9, top + 5, 25)
        if left == 0:
            sk.text((rx + 40, top + 24), f"I dag: {name}!", font_note_b)
        else:
            sk.text((rx + 40, top + 24), f"{name} om", font_note)
            sk.text((rx + rw - 10, top + 25), "i morgen!" if left == 1 else f"{left} dager", font_note_b, anchor='rs')
        top += 40
    scene(sk, rx, top, rw, BOTTOM - top - 10, today)

def render_image(events, weather, now=None):
    now = now or datetime.datetime.now(tz=OSLO_TZ)
    today = now.date()
    # Seed by date so the hand-drawn wobble and doodles stay put between refreshes in a day
    sk = Sketch(W, H, seed=today.toordinal())

    # Double frame, like a pen that went round twice
    sk.rect(9, 9, 791, 471, width=1.5, amp=1.2)
    sk.rect(13, 13, 787, 467, width=1.3, amp=1.4)
    for box in ((0, 0, W, 18), (0, H - 18, W, H), (0, 0, 18, H), (W - 18, 0, W, H)):
        sk.mark(box)

    _draw_header(sk, now, weather.get('now'))
    _draw_agenda(sk, events, today)
    sk.stroke([(512, 104), (512.5, 280), (513, BOTTOM)], width=1.4, amp=1.2)  # column divider
    sk.mark((500, 96, W, H))
    _draw_chart(sk, weather.get('hours', []), now)
    _draw_vignette(sk, today)
    sk.text((776, 464), f"oppdatert {now.strftime('%H:%M')}", font_tiny, anchor='rs')

    # A few seasonal doodles in white space left over in the agenda column
    decorate(sk, today, max_doodles=3, margin=20)

    buf = io.BytesIO()
    sk.flatten().save(buf, 'PNG')
    return buf.getvalue()

def pil_to_waveshare_7in3f_raw(img):
    # Convert PIL image to 800x480, 7-color (3-bit per pixel) raw format, packed as 4 bits per pixel (2 pixels per byte)
    palette = [
        (0, 0, 0),        # black
        (255, 255, 255),  # white
        (0, 255, 0),      # green
        (0, 0, 255),      # blue
        (255, 0, 0),      # red
        (255, 255, 0),    # yellow
        (255, 165, 0),    # orange
    ]
    # Rotate image 180 degrees to correct upside-down display
    img = img.rotate(180)
    img = img.convert('RGB').resize((800, 480))
    # Map each pixel to the closest palette index (0-6) with Pillow's C quantizer.
    # Unused palette slots repeat black so they can never win over index 0.
    pal_img = Image.new('P', (1, 1))
    pal_img.putpalette([c for rgb in palette for c in rgb] + list(palette[0]) * (256 - len(palette)))
    idxs = img.quantize(palette=pal_img, dither=Image.Dither.NONE).tobytes()
    # Pack two 4-bit pixels per byte, MSB first
    return bytes((idxs[i] << 4) | idxs[i + 1] for i in range(0, len(idxs), 2))

def epaper(request):
    fmt = None
    # Google Cloud Functions: request.args for GET, request.get_json() for POST
    if hasattr(request, 'args') and request.args:
        fmt = request.args.get('format', 'png').lower()
    elif hasattr(request, 'get_json'):
        try:
            data = request.get_json(silent=True)
            if data and 'format' in data:
                fmt = data['format'].lower()
        except Exception:
            pass
    if not fmt:
        fmt = 'png'
    logging.info(f"epaper endpoint called with format={fmt}")
    events = get_events()
    weather = get_weather()
    if fmt == 'jpeg' or fmt == 'jpg':
        png_bytes = render_image(events, weather)
        img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=90)
        return (
            buf.getvalue(), 200,
            {
              'Content-Type':'image/jpeg',
              'Cache-Control':'no-cache, max-age=0'
            }
        )
    elif fmt == 'raw':
        png_bytes = render_image(events, weather)
        img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
        raw = pil_to_waveshare_7in3f_raw(img)
        return (
            raw, 200,
            {
              'Content-Type':'application/octet-stream',
              'Cache-Control':'no-cache, max-age=0'
            }
        )
    else:  # default to PNG
        png = render_image(events, weather)
        return (
            png, 200,
            {
              'Content-Type':'image/png',
              'Cache-Control':'no-cache, max-age=0'
            }
        )
