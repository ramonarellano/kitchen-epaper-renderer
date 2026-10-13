import os, io, re, datetime, json, requests
from PIL import Image
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import secretmanager
import logging
import pytz

from sketch import (Sketch, Font, weather_icon, ellipse_pts, bin_icon, tooth_icon, plane_icon, star_icon,
                    wind_icon, drop_icon, RED, BLUE, GREEN, ORANGE, YELLOW)
from seasonal import scene, special_days, next_countdown

# env vars (set these when deploying)
CALENDAR_ID = os.environ['CALENDAR_ID']
YR_LAT      = os.environ['YR_LAT']
YR_LON      = os.environ['YR_LON']
SECRET_NAME = os.environ['SECRET_NAME']  # e.g. "projects/12345/secrets/calendar-sa-key"

# Configure logging
logging.basicConfig(level=logging.INFO)

# All displayed times and day boundaries use Norwegian local time
OSLO_TZ = pytz.timezone('Europe/Oslo')

# Load fonts once on cold start (Kalam: handwritten, SIL Open Font License).
# Readable from across the kitchen: nothing is smaller than 22 px.
FONT_DIR = 'fonts'
KALAM_REGULAR = os.path.join(FONT_DIR, 'Kalam-Regular.ttf')
KALAM_BOLD    = os.path.join(FONT_DIR, 'Kalam-Bold.ttf')
font_now_temp = Font(KALAM_BOLD, 40)     # current temperature
font_date     = Font(KALAM_BOLD, 36)     # header date
font_countdown = Font(KALAM_BOLD, 34)    # "19 dager"
font_wx_temp  = Font(KALAM_BOLD, 30)     # temperature in the weather cells
font_title    = Font(KALAM_REGULAR, 29)  # event titles
font_section  = Font(KALAM_BOLD, 28)     # "I morgen"
font_time     = Font(KALAM_BOLD, 26)     # event start time / weekday
font_wx_head  = Font(KALAM_BOLD, 24)     # "Været i morgen"
font_small    = Font(KALAM_REGULAR, 22)  # wind, "til Halloween"
font_small_b  = Font(KALAM_BOLD, 22)     # weather cell hours, precipitation, "+N til"
font_badge    = Font(KALAM_BOLD, 21)     # person initials

# Norwegian names, independent of which locales the runtime has installed
WEEKDAYS = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag', 'lørdag', 'søndag']
WEEKDAYS_SHORT = ['man', 'tir', 'ons', 'tor', 'fre', 'lør', 'søn']
MONTHS = ['januar', 'februar', 'mars', 'april', 'mai', 'juni', 'juli',
          'august', 'september', 'oktober', 'november', 'desember']

# Family members: an event title prefixed with initials ("S: Piano", "K&R&E: Høsttreff")
# gets a coloured ring per person instead of the prefix.
PEOPLE = {'K': RED, 'S': BLUE, 'R': GREEN, 'E': ORANGE, 'M': YELLOW}
_P = ''.join(PEOPLE)
PEOPLE_PREFIX = re.compile(rf'^([{_P}](?:\s*[&+,/]\s*[{_P}])*)(?::\s*|\s+)(\S.*)$')

# Keyword -> icon for all-day events (shown after the date / "I morgen" instead of a row)
EVENT_ICONS = [
    (re.compile(r'søppel|avfall|papir|plast|glass', re.I), bin_icon),
    (re.compile(r'tannlege', re.I), tooth_icon),
    (re.compile(r'\bfly\b|flyplass|gardermoen|reise', re.I), plane_icon),
]

# Short titles: explicit overrides first, otherwise cut at the first of these words
SHORT_TITLES = {
    'levere i barnehagen': 'Barnehagen',
}
TITLE_CUT = re.compile(r'\s+(?:–|-|med|hos|i|på)\s+', re.I)

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
LX, LW = 26, 496      # left column (agenda)
RX, RE = 522, 776     # right column (weather + season)
ROW = 34              # agenda row height
BOTTOM = 452          # lowest agenda baseline


def short_title(title):
    """One or two words: 'Øvelseskjøring med Solveig' -> 'Øvelseskjøring'."""
    title = title.strip()
    override = SHORT_TITLES.get(title.lower())
    if override:
        return override
    return TITLE_CUT.split(title, maxsplit=1)[0].strip(' ,.:;') or title


def fit(text, font, max_w):
    """Drop whole words until text fits; '…' only as a last resort."""
    words = text.split()
    while len(words) > 1 and font.width(' '.join(words)) > max_w:
        words.pop()
    text = ' '.join(words)
    if font.width(text) <= max_w:
        return text
    while text and font.width(text + '…') > max_w:
        text = text[:-1]
    return text.rstrip() + '…'


def parse_events(events):
    """Calendar tuples -> dicts with Oslo-local first/last day, start time (None if all-day), people and short title."""
    out = []
    for _date, start, end, summary in events:
        summary = summary.strip()
        who, title = '', summary
        m = PEOPLE_PREFIX.match(summary)
        if m:
            who, title = re.sub(r'[^A-Z]', '', m.group(1)), m.group(2)
        try:
            if len(start) == 10:
                # All-day events have date-only start/end ('YYYY-MM-DD'); end is exclusive
                first = datetime.date.fromisoformat(start)
                last = datetime.date.fromisoformat(end) - datetime.timedelta(days=1)
                st = None
            else:
                st = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(OSLO_TZ)
                et = datetime.datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(OSLO_TZ)
                first = st.date()
                last = max(first, (et - datetime.timedelta(microseconds=1)).date())
        except ValueError:
            continue
        icon = next((fn for rx, fn in EVENT_ICONS if rx.search(summary)), star_icon)
        out.append({'first': first, 'last': max(first, last), 'start': st, 'who': who,
                    'title': short_title(title), 'icon': icon})
    out.sort(key=lambda e: (e['first'], e['start'] is not None, e['start'] or 0))
    return out


def day_rows(evs, d):
    """Timed events starting on d."""
    return [e for e in evs if e['start'] is not None and e['first'] == d]


def day_icons(evs, d, limit=3):
    """Icons for all-day events (and timed events that started earlier) covering d, plus the day's holiday icon."""
    icons = [e['icon'] for e in evs if e['first'] <= d <= e['last'] and (e['start'] is None or e['first'] < d)]
    icons += [icon for day, _, icon, _ in special_days(d.year) if day == d and icon]
    unique = []
    for ic in icons:
        if ic not in unique:
            unique.append(ic)
    return unique[:limit]


def _badges(sk, x, y, who):
    """Coloured rings with the initial inside; returns the width used."""
    for i, letter in enumerate(who):
        cx = x + 14 + i * 31
        sk.stroke(ellipse_pts(cx, y - 9, 14.5, 14.5, n=28, start=sk.rng.uniform(0, 6)),
                  width=3.2, amp=0.3, closed=True, color=PEOPLE.get(letter))
        sk.text((cx, y - 1), letter, font_badge, anchor='ms')
    return len(who) * 31 + 8 if who else 0


def _row(sk, x, y, ev):
    """HH:MM, person rings, short title; baseline y."""
    sk.text((x, y), ev['start'].strftime('%H:%M'), font_time)
    cx = x + 76
    cx += _badges(sk, cx, y, ev['who'])
    sk.text((cx, y), fit(ev['title'], font_title, LW - cx), font_title)


def _icons(sk, x, y, icons, size=32):
    for ic in icons:
        ic(sk, x, y, size)
        x += size + 8
    return x


def _temp(t):
    return f"{round(t)}°".replace('-', '−')


def _draw_header(sk, today):
    date = f"{WEEKDAYS[today.weekday()].capitalize()} {today.day}. {MONTHS[today.month - 1]}"
    box = sk.text((28, 54), date, font_date)
    return box[2] + 12


def _draw_now(sk, current):
    if not current:
        return
    temp = _temp(current['temp'])
    sk.text((RE - 4, 55), temp, font_now_temp, anchor='rs')
    weather_icon(sk, current['icon'], RE - 4 - font_now_temp.width(temp) - 54, 16, 46)


def _draw_agenda(sk, evs, today):
    tomorrow = today + datetime.timedelta(days=1)

    # Today: no title, it goes without saying
    y = 108
    for ev in day_rows(evs, today)[:3]:
        _row(sk, LX + 6, y, ev)
        y += ROW
    y += 8

    # Tomorrow: title with all-day icons, max 3 rows, the rest counted
    rows = day_rows(evs, tomorrow)
    label = sk.text((LX + 8, y), "I morgen", font_section)
    _icons(sk, label[2] + 10, y - 27, day_icons(evs, tomorrow))
    if len(rows) > 3:
        sk.text((LW, y), f"+{len(rows) - 3} til", font_small_b, anchor='rs')
    y += ROW + 2
    for ev in rows[:3]:
        _row(sk, LX + 6, y, ev)
        y += ROW
    y += 4
    sk.dashed((LX + 4, y - 22), (LW, y - 21), dash=8, gap=7, width=1.8, amp=0.6)
    y += 10

    # Later: one line per day, first event and a count of the rest
    later = {}
    for e in evs:
        if e['first'] > tomorrow:
            later.setdefault(e['first'], []).append(e)
    for d, items in sorted(later.items())[:3]:
        if y > BOTTOM:
            break
        dn = WEEKDAYS_SHORT[d.weekday()] if (d - today).days < 7 else f"{d.day}.{d.month}"
        sk.text((LX + 6, y), dn, font_time)
        cx = LX + 70
        extra = f"+{len(items) - 1}" if len(items) > 1 else ''
        ew = font_small_b.width(extra) + 10 if extra else 0
        sk.text((cx, y), fit(items[0]['title'], font_title, LW - cx - ew), font_title)
        if extra:
            sk.text((LW, y), extra, font_small_b, anchor='rs')
        y += ROW


def _wx_at(hours, d, hour):
    """Forecast entry for date d nearest to hour, plus precipitation summed over the 4 hours from it."""
    day = [h for h in hours if h['date'] == d]
    if not day:
        return None, 0
    h = min(day, key=lambda h: abs(h['hour'] - hour))
    precip = sum(x['precip'] for x in day if hour <= x['hour'] < hour + 4)
    return h, precip


def _draw_weather(sk, hours, tomorrow):
    sk.text((RX + 4, 108), "Været i morgen", font_wx_head)
    cw = (RE - RX) / 4
    for i, hour in enumerate((8, 12, 16, 20)):
        h, precip = _wx_at(hours, tomorrow, hour)
        if not h:
            continue
        cx = RX + cw * i + cw / 2
        sk.text((cx, 138), f"{hour:02d}", font_small_b, anchor='ms')
        weather_icon(sk, h['icon'], cx - 21, 144, 42)
        sk.text((cx, 208), _temp(h['temp']), font_wx_temp, anchor='ms')
        wind_icon(sk, cx - 24, 223, 21)
        sk.text((cx + 2, 238), str(round(h['wind'])), font_small)
        if precip >= 0.1:
            drop_icon(sk, cx - 20, 249, 14)
            sk.text((cx - 2, 264), '<1' if precip < 1 else str(round(precip)), font_small_b, color=BLUE)
    sk.dashed((RX + 6, 276), (RE - 4, 277), dash=8, gap=7, width=1.6, amp=0.6)


def _draw_season(sk, today):
    x, y, w = RX + 8, 290, RE - RX - 8
    countdown = next_countdown(today)
    if countdown:
        name, left, icon = countdown
        if icon:
            icon(sk, x + 2, y + 2, 42)
        if left == 0:
            big, small = "I dag!", name
        else:
            big = "1 dag" if left == 1 else f"{left} dager"
            small = "til " + (name if name == 'Halloween' else name[0].lower() + name[1:])
        sk.text((x + 50, y + 30), big, font_countdown)
        sk.text((x + 50, y + 58), fit(small, font_small, RE - x - 50), font_small)
        y += 72
    # Scene stands on a ground line at y=452
    scene(sk, x, y, w, 462 - y, today)


def render_image(events, weather, now=None):
    now = now or datetime.datetime.now(tz=OSLO_TZ)
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)
    evs = parse_events(events)
    # Seed by date so the hand-drawn wobble stays put between refreshes in a day (no ghosting)
    sk = Sketch(W, H, seed=today.toordinal())

    sk.wave_border(11, 11, 789, 469)

    hx = _draw_header(sk, today)
    _icons(sk, hx, 24, day_icons(evs, today))
    _draw_now(sk, weather.get('now'))
    sk.stroke([(24, 72), (400, 73), (776, 74)], width=2.4, amp=0.8)

    _draw_agenda(sk, evs, today)
    sk.stroke([(509, 86), (509.5, 280), (510, 458)], width=1.6, amp=1.2)  # column divider
    _draw_weather(sk, weather.get('hours', []), tomorrow)
    _draw_season(sk, today)

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
        (255, 128, 0),    # orange
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
