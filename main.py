import os, io, datetime, json, requests
from PIL import Image, ImageDraw, ImageFont
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import secretmanager

# env vars (set these when deploying)
CALENDAR_ID = os.environ['CALENDAR_ID']
YR_LAT      = os.environ['YR_LAT']
YR_LON      = os.environ['YR_LON']
SECRET_NAME = os.environ['SECRET_NAME']  # e.g. "projects/12345/secrets/calendar-sa-key"

# Load icons & fonts once on cold start
ICON_DIR = 'icons/png'  # Use relative path for local dev
# Remove custom fonts for now, use default PIL font
from PIL import ImageFont
FONT_DIR = 'fonts'  # Not used, but kept for future
weather_icons = {
    'cloudy': Image.open(f'{ICON_DIR}/cloudy.png'),
    'partly_cloudy': Image.open(f'{ICON_DIR}/cloudy.png'),
    'sunny': Image.open(f'{ICON_DIR}/cloudy.png'),
    'clear_night': Image.open(f'{ICON_DIR}/cloudy.png'),
    'rain': Image.open(f'{ICON_DIR}/cloudy.png'),
    'showers': Image.open(f'{ICON_DIR}/cloudy.png'),
    'snow': Image.open(f'{ICON_DIR}/cloudy.png'),
    'fog': Image.open(f'{ICON_DIR}/cloudy.png'),
    'sleet': Image.open(f'{ICON_DIR}/cloudy.png'),
    'thunder': Image.open(f'{ICON_DIR}/cloudy.png'),
}
font_header = ImageFont.load_default()
font_cal    = ImageFont.load_default()
font_weather= ImageFont.load_default()

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
    then    = now + datetime.timedelta(days=3)
    items   = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat()+'Z',
        timeMax=then.isoformat()+'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items',[])
    # Return as list of (date-str, summary)
    return [
      (evt['start'].get('dateTime',evt['start'].get('date'))[:10],
       evt.get('summary','(No title)'))
      for evt in items
    ]

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
    # dimensions of your color e-paper
    W,H = 800,480
    img = Image.new('RGB',(W,H),(255,255,255))
    draw = ImageDraw.Draw(img)

    # --- Left: Calendar ---
    margin = 10
    cal_w = int(W*0.6)
    draw.text((margin, margin), "Next 3-day Agenda:", font=font_header, fill=(0,0,0))
    y = margin + 30
    block_h = 32
    max_days = 3
    max_events_per_day = 4
    # Group events by date
    from collections import defaultdict
    events_by_date = defaultdict(list)
    for date, summary in events:
        events_by_date[date].append(summary)
    # Only show up to max_days
    for i, (date, summaries) in enumerate(sorted(events_by_date.items())[:max_days]):
        # Date title
        draw.rectangle([margin, y, cal_w-margin, y+block_h], fill=(0,128,0))
        draw.text((margin+5, y+8), date, font=font_header, fill=(255,255,255))
        y += block_h + 2
        # Events for this day
        for j, summary in enumerate(summaries[:max_events_per_day]):
            draw.rectangle([margin+10, y, cal_w-margin-10, y+block_h], fill=(0,180,0))
            draw.text((margin+15, y+8), summary, font=font_cal, fill=(255,255,255))
            y += block_h + 2
        # If too many events, show ellipsis
        if len(summaries) > max_events_per_day:
            draw.text((margin+15, y), "...", font=font_cal, fill=(0,0,0))
            y += block_h//2
        # Add extra space between days
        y += 6
        if y + block_h > H*0.8:
            break

    # --- Right: Weather ---
    wx_x = int(W*0.5) + margin
    wx_w = int(W*0.5) - 2*margin
    draw.text((wx_x, margin), "Oslo Weather Today:", font=font_header, fill=(0,0,0))
    y_wx = margin + 30
    row_h = int((H - y_wx - margin) / 12)
    icon_size = min(row_h-4, 36)
    for period in weather:
        hour = period['hour']
        temp = period['temp']
        wind = period['wind']
        precip = period['precip']
        icon = period['icon']
        icon_img = weather_icons[icon].resize((icon_size,icon_size), Image.Resampling.LANCZOS)
        # Draw icon
        img.paste(icon_img, (wx_x, y_wx), icon_img)
        # Draw time
        draw.text((wx_x+icon_size+8, y_wx+4), f"{hour:02d}:00", font=font_cal, fill=(0,0,0))
        # Draw temp
        draw.text((wx_x+icon_size+70, y_wx+4), f"{int(temp)}°C", font=font_weather, fill=(200,0,0))
        # Draw precip
        draw.text((wx_x+icon_size+140, y_wx+4), f"{precip:.1f}mm", font=font_cal, fill=(0,0,0))
        # Draw wind
        draw.text((wx_x+icon_size+210, y_wx+4), f"{wind:.1f}m/s", font=font_cal, fill=(0,0,0))
        y_wx += row_h
    # return PNG bytes
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()

def epaper(request):
    # main HTTP entry point
    events = get_events()
    weather = get_weather()
    png = render_image(events, weather)
    return (
        png, 200,
        {
          'Content-Type':'image/png',
          'Cache-Control':'no-cache, max-age=0'
        }
    )
