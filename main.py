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
    # yr.no compact JSON
    url = f'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={YR_LAT}&lon={YR_LON}'
    headers = {'User-Agent':'kitchen-epaper/1.0'}
    data = requests.get(url, headers=headers).json()
    # take first timeseries entry
    ts = data['properties']['timeseries'][0]
    temp = ts['data']['instant']['details']['air_temperature']
    # pick icon by symbol_code
    symbol = ts['data']['next_1_hours']['summary']['symbol_code' if 'next_1_hours' in ts['data'] else 'cloudy']
    # Map yr.no symbol_code to our icon keys
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
    return f"{int(temp)}°C", icon

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
    block_h = 40
    for date, summary in events:
        # green block
        draw.rectangle([margin, y, cal_w-margin, y+block_h], fill=(0,128,0))
        # white text inside
        draw.text((margin+5, y+8), f"{date}: {summary}",
                  font=font_cal, fill=(255,255,255))
        y += block_h + 5
        if y + block_h > H*0.8: break

    # --- Right: Weather ---
    wx_x = cal_w + margin
    draw.text((wx_x, margin), "Today's Weather:", font=font_header, fill=(0,0,0))
    wx_txt, wx_icon = weather
    icon_img = weather_icons[wx_icon].resize((60,60), Image.Resampling.LANCZOS)
    img.paste(icon_img, (wx_x, margin+40), icon_img)

    # temperature in red
    draw.text((wx_x+70, margin+50), wx_txt, font=font_weather, fill=(200,0,0))

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
