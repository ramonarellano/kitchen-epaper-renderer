import os, io, datetime, json, requests, locale
from PIL import Image, ImageDraw, ImageFont
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import secretmanager
import logging

# env vars (set these when deploying)
CALENDAR_ID = os.environ['CALENDAR_ID']
YR_LAT      = os.environ['YR_LAT']
YR_LON      = os.environ['YR_LON']
SECRET_NAME = os.environ['SECRET_NAME']  # e.g. "projects/12345/secrets/calendar-sa-key"

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load icons & fonts once on cold start
ICON_DIR = 'icons/png'  # Use relative path for local dev
FONT_DIR = 'fonts'
ROBOTO_PATH = os.path.join(FONT_DIR, 'Roboto-Regular.ttf')
font_header = ImageFont.truetype(ROBOTO_PATH, 24)  # match left-side title size
font_date   = ImageFont.truetype(ROBOTO_PATH, 24)  # smaller date title font
font_event  = ImageFont.truetype(ROBOTO_PATH, 20)  # smaller event name font
font_weather= ImageFont.truetype(ROBOTO_PATH, 20)
font_small  = ImageFont.truetype(ROBOTO_PATH, 18)
weather_icons = {
    'cloudy': Image.open(f'{ICON_DIR}/cloudy-day-3.png'),
    'partly_cloudy': Image.open(f'{ICON_DIR}/partly-cloudy-day.png'),
    'sunny': Image.open(f'{ICON_DIR}/sunny-day.png'),
    'clear_night': Image.open(f'{ICON_DIR}/clear-night.png'),
    'rain': Image.open(f'{ICON_DIR}/rainy-3.png'),
    'showers': Image.open(f'{ICON_DIR}/rainy-1-day.png'),
    'snow': Image.open(f'{ICON_DIR}/snowy-3.png'),
    'fog': Image.open(f'{ICON_DIR}/fog.png'),
    'sleet': Image.open(f'{ICON_DIR}/sleet.png'),
    'thunder': Image.open(f'{ICON_DIR}/thunder.png'),
}

try:
    locale.setlocale(locale.LC_TIME, 'nb_NO.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'no_NO.UTF-8')
    except locale.Error:
        pass  # fallback to system default if Norwegian locale not available

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
    # Get 12 periods: every 2 hours for today
    periods = list(range(0, 24, 2))  # 0, 2, ..., 22
    now = datetime.datetime.utcnow()
    times = []
    for ts in data['properties']['timeseries']:
        t = datetime.datetime.fromisoformat(ts['time'].replace('Z','+00:00'))
        if t.date() == now.date() and t.hour in periods:
            times.append(ts)
            if len(times) == 12:
                break
    details = []
    for ts in times:
        t = datetime.datetime.fromisoformat(ts['time'].replace('Z','+00:00'))
        hour = t.hour
        temp = ts['data']['instant']['details']['air_temperature']
        wind = ts['data']['instant']['details'].get('wind_speed', 0)
        precip = 0
        if 'next_1_hours' in ts['data']:
            precip = ts['data']['next_1_hours']['details'].get('precipitation_amount', 0)
            symbol = ts['data']['next_1_hours']['summary']['symbol_code']
        else:
            symbol = 'cloudy'
        if symbol.startswith('clearsky'):
            icon = 'clear_night' if 'night' in symbol else 'sunny'
        elif symbol.startswith('cloudy'):
            icon = 'cloudy'
        elif symbol.startswith('partlycloudy'):
            icon = 'partly_cloudy'
        elif symbol.startswith('fair'):
            icon = 'sunny'
        elif symbol.startswith('rain'):
            icon = 'rain'
        elif symbol.startswith('showers'):
            icon = 'showers'
        elif symbol.startswith('snow'):
            icon = 'snow'
        elif symbol.startswith('fog'):
            icon = 'fog'
        elif symbol.startswith('sleet'):
            icon = 'sleet'
        elif symbol.startswith('thunder'):
            icon = 'thunder'
        else:
            icon = 'cloudy'
        details.append({
            'hour': hour,
            'temp': temp,
            'wind': wind,
            'precip': precip,
            'icon': icon
        })
    return details

def render_image(events, weather):
    W,H = 800,480
    img = Image.new('RGB',(W,H),(255,255,255))
    draw = ImageDraw.Draw(img)

    margin = 24
    cal_w = int(W*0.5) - margin
    wx_x = int(W*0.5) + margin
    wx_w = int(W*0.5) - 2*margin
    y = margin
    block_h = 32
    # --- Left: Calendar ---
    from collections import defaultdict
    events_by_date = defaultdict(list)
    for date, start, end, summary in events:
        events_by_date[date].append((start, end, summary))
    y = margin
    max_y = H - margin
    # Fill up the left side with events from as many days as needed
    for date, summaries in sorted(events_by_date.items()):
        if y + font_date.size > max_y:
            break
        # Format date as 'Mandag 25. januar' in Norwegian
        try:
            dt = datetime.datetime.strptime(date, "%Y-%m-%d")
            date_str = dt.strftime("%A %d. %B").capitalize()
        except Exception:
            date_str = date
        draw.text((margin, y), date_str, font=font_date, fill=(0,0,0))
        y += font_date.size + 2  # Add a tiny bit of space after the date title
        y += 4  # Extra tiny space between title and events
        for start, end, summary in summaries:
            if y + font_event.size + 8 > max_y:
                break
            # Draw green box
            box_x0 = margin+10
            box_y0 = y
            box_x1 = margin+cal_w-10
            box_y1 = y + font_event.size + 8
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=(120,220,120), outline=(60,180,60), width=2)
            # Format time
            try:
                st = datetime.datetime.fromisoformat(start.replace('Z','+00:00'))
                et = datetime.datetime.fromisoformat(end.replace('Z','+00:00'))
                time_str = f"{st.strftime('%H:%M')}-{et.strftime('%H:%M')}"
            except Exception:
                time_str = "All day"
            # Truncate summary if too long
            time_x = box_x0+6
            event_x = box_x0+120  # start event title further right
            max_event_width = box_x1 - event_x - 8
            event_text = summary
            while draw.textlength(event_text, font=font_event) > max_event_width and len(event_text) > 3:
                event_text = event_text[:-1]
            if event_text != summary:
                event_text = event_text[:-3] + '...'
            # Draw time and summary
            draw.text((time_x, box_y0+2), time_str, font=font_small, fill=(0,80,0))
            draw.text((event_x, box_y0+2), event_text, font=font_event, fill=(0,60,0))
            y += font_event.size + 12
        y += 10
        if y + font_date.size > max_y:
            break
    # --- Right: Weather ---
    today = datetime.datetime.utcnow().strftime('%d.%m.%Y')
    draw.text((wx_x, margin), f"Oslo idag {today}", font=font_date, fill=(0,0,0))  # Match left-side title size
    y_wx = margin + font_date.size + 10
    # Make weather rows and icons larger to fill the image
    row_h = int((H - y_wx - margin) / 8) + 8  # increase row spacing
    icon_size = min(row_h-2, 96)              # larger icons, up to 96px
    for period in weather[:8]:                # show 8 periods to match new row count
        hour = period['hour']
        temp = period['temp']
        wind = period['wind']
        precip = period['precip']
        icon = period['icon']
        icon_img = weather_icons[icon].resize((icon_size,icon_size), Image.Resampling.LANCZOS)
        img.paste(icon_img, (wx_x, y_wx), icon_img)
        # Vertically center the text relative to the icon
        text_y = y_wx + (icon_size - font_weather.size) // 2
        draw.text((wx_x+icon_size+8, text_y), f"{hour:02d}:00", font=font_weather, fill=(0,0,0))
        draw.text((wx_x+icon_size+70, text_y), f"{int(temp)}°C", font=font_weather, fill=(200,0,0))
        draw.text((wx_x+icon_size+140, text_y), f"{precip:.1f}mm", font=font_weather, fill=(0,0,0))
        draw.text((wx_x+icon_size+230, text_y), f"{wind:.1f}m/s", font=font_weather, fill=(0,0,0))
        y_wx += row_h
    # return PNG bytes
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()

def pil_to_waveshare_7in3f_raw(img):
    # Convert PIL image to 800x480, 7-color (3-bit per pixel) raw format
    palette = [
        (0, 0, 0),        # black
        (255, 255, 255),  # white
        (0, 255, 0),      # green
        (0, 0, 255),      # blue
        (255, 0, 0),      # red
        (255, 255, 0),    # yellow
        (255, 165, 0),    # orange
    ]
    img = img.convert('RGB').resize((800, 480))
    raw = bytearray()
    for y in range(480):
        for x in range(800):
            r, g, b = img.getpixel((x, y))
            idx = min(range(7), key=lambda i: (r-palette[i][0])**2 + (g-palette[i][1])**2 + (b-palette[i][2])**2)
            raw.append(idx)
    return bytes(raw)

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
