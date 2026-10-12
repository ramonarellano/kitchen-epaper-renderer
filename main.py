import os, io, datetime, json, requests
from PIL import Image
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import secretmanager
import logging
import pytz

from sketch import Sketch, Font, weather_icon
from seasonal import decorate

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
font_heading = Font(KALAM_BOLD, 26)     # day / weather section headings
font_time    = Font(KALAM_REGULAR, 19)  # event times
font_event   = Font(KALAM_REGULAR, 22)  # event titles
font_wx      = Font(KALAM_REGULAR, 21)  # weather hour
font_temp    = Font(KALAM_BOLD, 23)     # weather temperature
font_wx_small= Font(KALAM_REGULAR, 18)  # precipitation and wind
font_tiny    = Font(KALAM_REGULAR, 15)  # last updated

# Norwegian names, independent of which locales the runtime has installed
WEEKDAYS = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag', 'lørdag', 'søndag']
MONTHS = ['januar', 'februar', 'mars', 'april', 'mai', 'juni', 'juli',
          'august', 'september', 'oktober', 'november', 'desember']

def norwegian_date(d):
    """e.g. 'mandag 12. oktober'"""
    return f"{WEEKDAYS[d.weekday()]} {d.day}. {MONTHS[d.month - 1]}"

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
    # Oslo, Norway coordinates
    lat = 59.9139
    lon = 10.7522
    url = f'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}'
    headers = {'User-Agent':'kitchen-epaper/1.0'}
    data = requests.get(url, headers=headers).json()
    # Get periods: every 2 hours for today and tomorrow, starting at 08:00
    periods = list(range(8, 24, 2))  # 8, 10, ..., 22
    now = datetime.datetime.now(tz=OSLO_TZ)
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)
    current_hour = now.hour
    times = []
    for ts in data['properties']['timeseries']:
        t = datetime.datetime.fromisoformat(ts['time'].replace('Z','+00:00')).astimezone(OSLO_TZ)
        # For today, only include periods >= current hour (rounded up to next even hour)
        if t.date() == today:
            # Find the next period >= now (e.g., if now is 11:15, show 12:00 and later)
            if t.hour in periods and t.hour >= ((current_hour + 1) // 2) * 2:
                times.append(ts)
        elif t.date() == tomorrow and t.hour in periods:
            times.append(ts)
    details = []
    for ts in times:
        t = datetime.datetime.fromisoformat(ts['time'].replace('Z','+00:00')).astimezone(OSLO_TZ)
        day = t.date()
        hour = t.hour
        temp = ts['data']['instant']['details']['air_temperature']
        wind = ts['data']['instant']['details'].get('wind_speed', 0)
        precip = 0
        if 'next_1_hours' in ts['data']:
            precip = ts['data']['next_1_hours']['details'].get('precipitation_amount', 0)
            symbol = ts['data']['next_1_hours']['summary']['symbol_code']
        else:
            symbol = None
        icon = symbol  # Use symbol_code directly as icon filename
        details.append({
            'date': day,
            'hour': hour,
            'temp': temp,
            'wind': wind,
            'precip': precip,
            'icon': icon
        })
    return details

W, H = 800, 480
MARGIN = 22
DIVIDER_X = 400

def _heading(sk, x, baseline, text):
    """Bold handwritten heading with a hand-drawn underline."""
    box = sk.text((x, baseline), text, font_heading)
    w = box[2] - x
    sk.stroke([(x - 2, baseline + 7), (x + w * 0.55, baseline + 5 + sk.rng.uniform(-1, 1)), (x + w + 6, baseline + 6)],
              width=2, amp=0.8)
    sk.mark((x - 2, baseline, x + w + 8, baseline + 10), pad=2)

def _truncate(text, font, max_w):
    if font.width(text) <= max_w:
        return text
    while text and font.width(text + '…') > max_w:
        text = text[:-1]
    return text.rstrip() + '…'

MONTHS_SHORT = ['jan', 'feb', 'mar', 'apr', 'mai', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'des']

def _event_time(start, end, shown_on):
    """Time label for an event listed under the date shown_on.

    Multi-day events (and events that started before shown_on) show when they end, e.g. 'til 16. okt'.
    """
    try:
        if len(start) == 10:
            # All-day events have date-only start/end ('YYYY-MM-DD'); end is exclusive
            last_day = datetime.date.fromisoformat(end) - datetime.timedelta(days=1)
            if last_day > shown_on:
                return f"til {last_day.day}. {MONTHS_SHORT[last_day.month - 1]}"
            return "Hele dagen"
        st = datetime.datetime.fromisoformat(start.replace('Z','+00:00')).astimezone(OSLO_TZ)
        et = datetime.datetime.fromisoformat(end.replace('Z','+00:00')).astimezone(OSLO_TZ)
        if et.date() > shown_on:
            return f"til {et.day}. {MONTHS_SHORT[et.month - 1]}"
        if st.date() < shown_on:
            return f"til {et.strftime('%H:%M')}"
        return f"{st.strftime('%H:%M')}–{et.strftime('%H:%M')}"
    except Exception:
        return "Hele dagen"

def render_image(events, weather, now=None):
    now = now or datetime.datetime.now(tz=OSLO_TZ)
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)
    # Seed by date so the hand-drawn wobble and doodles stay put between refreshes in a day
    sk = Sketch(W, H, seed=today.toordinal())

    # --- Left: Calendar ---
    from collections import defaultdict
    events_by_date = defaultdict(list)
    for date, start, end, summary in events:
        # Ongoing events that started before today are listed under today
        events_by_date[max(date, today.isoformat())].append((start, end, summary))
    x0 = MARGIN
    col_right = DIVIDER_X - 16
    times = [_event_time(st, et, datetime.date.fromisoformat(date))
             for date, items in events_by_date.items() for st, et, _ in items]
    title_x = x0 + 8 + max([font_time.width(t) for t in times] or [0]) + 12
    max_y = H - MARGIN
    y = MARGIN - 4
    if not events_by_date:
        _heading(sk, x0, y + 28, "Ingen avtaler")
    for date, items in sorted(events_by_date.items()):
        if y + 28 + 14 + 26 > max_y:  # room for heading and at least one event
            break
        d = datetime.date.fromisoformat(date)
        label = norwegian_date(d)
        if d == today:
            label = f"I dag, {label}"
        elif d == tomorrow:
            label = f"I morgen, {label}"
        y += 28
        _heading(sk, x0, y, label[0].upper() + label[1:])
        y += 10
        for start, end, summary in items:
            if y + 27 > max_y:
                break
            y += 27
            sk.text((x0 + 8, y), _event_time(start, end, d), font_time)
            sk.text((title_x, y), _truncate(summary, font_event, col_right - title_x), font_event)
            sk.mark((x0, y - 20, col_right, y + 6))  # keep doodles out of the row
        y += 12

    # --- Divider ---
    sk.stroke([(DIVIDER_X, MARGIN + 6), (DIVIDER_X + 1.5, H / 2), (DIVIDER_X - 0.5, H - MARGIN - 6)],
              width=2, amp=1.3)
    sk.mark((DIVIDER_X - 4, MARGIN, DIVIDER_X + 4, H - MARGIN), pad=4)

    # --- Right: Weather ---
    wx_x = DIVIDER_X + 22
    wx_right = W - MARGIN
    icon_size, row_h = 38, 42
    wx_max_y = H - 28  # keep room for the last-updated line
    today_periods = [p for p in weather if p.get('date') == today]
    # For tomorrow, only include periods from 06:00 and later
    tomorrow_periods = [p for p in weather if p.get('date') == tomorrow and p.get('hour', 0) >= 6]
    y = MARGIN - 4
    for title, periods in (("Været i dag", today_periods), ("I morgen", tomorrow_periods)):
        if not periods or y + 28 + 10 + row_h > wx_max_y:
            continue
        y += 28
        _heading(sk, wx_x, y, title)
        y += 12
        for p in periods[:8]:
            if y + row_h > wx_max_y:
                break
            weather_icon(sk, p['icon'], wx_x, y, icon_size)
            baseline = y + 28
            sk.text((wx_x + icon_size + 10, baseline), f"{p['hour']:02d}:00", font_wx)
            sk.text((wx_x + icon_size + 118, baseline), f"{round(p['temp'])}°", font_temp, anchor='rs')
            if p['precip'] >= 0.1:
                sk.text((wx_x + icon_size + 130, baseline), f"{p['precip']:.1f} mm".replace('.', ','), font_wx_small)
            sk.text((wx_right, baseline), f"{round(p['wind'])} m/s", font_wx_small, anchor='rs')
            sk.mark((wx_x, y, wx_right, y + icon_size))  # keep doodles out of the row
            y += row_h
        y += 6

    # Last updated (Norwegian local time), lower right corner
    sk.text((W - MARGIN, H - 8), f"Oppdatert {now.strftime('%H:%M')}", font_tiny, anchor='rs')

    # Seasonal doodles in whatever white space is left
    decorate(sk, today)

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
