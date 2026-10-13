import os, io, re, datetime, json, requests
from PIL import Image
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import secretmanager
import logging
import pytz

from sketch import (Sketch, Font, weather_icon, ellipse_pts, bin_icon, tooth_icon, plane_icon, star_icon,
                    wind_icon, drop_icon, BLACK, RED, BLUE, GREEN, ORANGE)
from seasonal import scene, birthday_scene, balloon, special_days, next_countdown

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
font_now_temp = Font(KALAM_BOLD, 36)     # current temperature
font_date     = Font(KALAM_BOLD, 32)     # header date
font_countdown = Font(KALAM_BOLD, 34)    # "19 dager"
font_wx_temp  = Font(KALAM_BOLD, 30)     # temperature in the weather cells
font_title    = Font(KALAM_REGULAR, 29)  # event titles today / tomorrow
font_later    = Font(KALAM_REGULAR, 27)  # comma-separated events on later days
font_ongoing  = Font(KALAM_REGULAR, 26)  # ongoing multi-day events
font_section  = Font(KALAM_BOLD, 28)     # "I morgen"
font_time     = Font(KALAM_BOLD, 26)     # event start time / weekday
font_wx_head  = Font(KALAM_BOLD, 24)     # "Været i dag"
font_small    = Font(KALAM_REGULAR, 22)  # wind, "til Halloween"
font_small_b  = Font(KALAM_BOLD, 22)     # weather cell hours, precipitation
font_badge    = Font(KALAM_BOLD, 21)     # person initials
font_badge_s  = Font(KALAM_BOLD, 18)     # person initials on later days

# Norwegian names, independent of which locales the runtime has installed
WEEKDAYS = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag', 'lørdag', 'søndag']
WEEKDAYS_SHORT = ['man', 'tir', 'ons', 'tor', 'fre', 'lør', 'søn']
MONTHS = ['januar', 'februar', 'mars', 'april', 'mai', 'juni', 'juli',
          'august', 'september', 'oktober', 'november', 'desember']

# Family members become coloured rings with their initial instead of text.
# Sources: an initials prefix ("S: Piano", "K&R&E: Høsttreff", "R og S: Tusenfryd", "A: Middag", "Alle: Middag")
# and first names anywhere in the title ("Fotballtrening Emilie", "Øvelseskjøring med Solveig", "Middag Alle").
# A (Alle, the whole family) gets a black ring.
PEOPLE = {'A': BLACK, 'K': RED, 'S': BLUE, 'R': GREEN, 'E': ORANGE}
NAMES = {'Alle': 'A', 'Kari': 'K', 'Ramon': 'R', 'Solveig': 'S', 'Emilie': 'E'}
_P = ''.join(PEOPLE)
_WHO = rf'(?:Alle|[{_P}])'
PEOPLE_PREFIX = re.compile(rf'^({_WHO}(?:(?:\s*[&+,/]\s*|\s+og\s+){_WHO})*)(?::\s*|\s+)(\S.*)$')
# A name, together with a preceding "med", "hos" or "og"
NAME_PATTERNS = [(re.compile(rf'\s*(?:\b(?:med|hos|og)\s+)?\b{name}\b'), letter) for name, letter in NAMES.items()]

# Calendar title -> short display title (lower-case keys)
# Words a shortened title should not end on
DANGLING = {'i', 'på', 'med', 'og', 'om', 'til', 'fra', 'for', 'hos', 'av', 'en', 'et', 'ei', 'the'}

SHORT_TITLES = {
    'levere i barnehagen': 'Barnehagen',
}

# Birthdays are all-day events with "bursdag" in the title and no person prefix ("E: Bursdag Sileih" is an
# invitation). "Thomas Seeberg Torjussen sin bursdag", "Bursdag Ingrid", "Magdalena bursdag 85" -> the name.
BIRTHDAY = re.compile(r'\b(?:bursdag|birthday)\b', re.I)
BIRTHDAY_WORDS = re.compile(r"\s+sin\s+bursdag\b|'s?\s+(?:bursdag|birthday)\b|\bbursdag\b|\bbirthday\b"
                            r"|\bgratulerer med dagen\b|\b\d+(?:\s*år)?(?!\S)", re.I)

# Keyword -> icon for all-day events (shown after the date / "I morgen" instead of a row)
EVENT_ICONS = [
    (re.compile(r'søppel|avfall|papir|plast|glass', re.I), bin_icon),
    (re.compile(r'tannlege', re.I), tooth_icon),
    (re.compile(r'\bfly\b|flyplass|gardermoen|reise', re.I), plane_icon),
]

W, H = 800, 480
LX, LW = 26, 496      # left column (agenda)
RX, RE = 522, 776     # right column (weather + season)
ROW = 33              # agenda row height (today, tomorrow, ongoing)
LROW = 32             # line height for later days
BOTTOM = 452          # lowest agenda baseline
TOP = 98              # first baseline below the header line


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


def fit(text, font, max_w):
    """Full text if it fits, otherwise cut with '…' at the end."""
    if font.width(text) <= max_w:
        return text
    while text and font.width(text + '…') > max_w:
        text = text[:-1]
    return text.rstrip() + '…'


def fit_words(text, font, max_w):
    """Drop whole words from the end until the text fits; '…' only if a single word is still too long."""
    words = text.split()
    if font.width(text) <= max_w:
        return text
    while len(words) > 1 and font.width(' '.join(words)) > max_w:
        words.pop()
    # Don't end on a dangling little word ("Lunsj med kolleger fra jobben i")
    while len(words) > 1 and words[-1].lower() in DANGLING:
        words.pop()
    return fit(' '.join(words), font, max_w)


def short_title(summary):
    """Calendar title -> (people initials, short title)."""
    title = summary.strip()
    title = SHORT_TITLES.get(title.lower(), title)
    who = ''
    m = PEOPLE_PREFIX.match(title)
    if m:
        who, title = re.sub(r'[^A-Z]', '', m.group(1)), m.group(2)
    for rx, letter in NAME_PATTERNS:
        if rx.search(title):
            title = rx.sub('', title)
            if letter not in who:
                who += letter
    title = re.split(r'\s+[–-]\s+', title, maxsplit=1)[0]
    # Leftovers after removing names: "Ramon og Solveig: Tog" -> ": Tog"
    return who, re.sub(r'\s{2,}', ' ', title).strip(' :,&+/–-')


def birthday_name(summary):
    """Birthday event title -> the person's name."""
    name = re.sub(r'\s{2,}', ' ', BIRTHDAY_WORDS.sub(' ', summary)).strip(' :,!–-') or summary.strip()
    # "Karis bursdag" -> Kari, for the family's own names
    return name[:-1] if name.endswith('s') and name[:-1] in NAMES else name


def parse_events(events):
    """Calendar tuples -> dicts with Oslo-local first/last day, start time (None if all-day), people and title."""
    out = []
    for _date, start, end, summary in events:
        who, title = short_title(summary)
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
        birthday = st is None and bool(BIRTHDAY.search(summary)) and not PEOPLE_PREFIX.match(summary.strip())
        icon = balloon if birthday else next((fn for rx, fn in EVENT_ICONS if rx.search(summary)), star_icon)
        out.append({'first': first, 'last': max(first, last), 'start': st, 'who': who,
                    'title': title, 'icon': icon, 'birthday': birthday,
                    'name': birthday_name(summary) if birthday else None})
    out.sort(key=lambda e: (e['first'], e['start'] is not None, e['start'] or 0))
    return out


def is_ongoing(e, today):
    """Multi-day events that have started and last through today, or start today and last longer."""
    return e['first'] <= today <= e['last'] and (e['first'] < today or e['last'] > e['first'])


def day_rows(evs, d, today):
    """Timed events starting on d (except those shown among the ongoing ones)."""
    return [e for e in evs if e['start'] is not None and e['first'] == d and not is_ongoing(e, today)]


def day_icons(evs, d, today, limit=3):
    """Icons for all-day events starting on d (not ongoing ones), plus the day's holiday icon."""
    icons = [e['icon'] for e in evs if e['start'] is None and e['first'] == d and not is_ongoing(e, today)]
    icons += [icon for day, _, icon, _ in special_days(d.year) if day == d and icon]
    unique = []
    for ic in icons:
        if ic not in unique:
            unique.append(ic)
    return unique[:limit]


def _badges(sk, x, y, who, scale=1.0):
    """Coloured rings with the initial inside, baseline y; returns the width used."""
    d, step = 29 * scale, 31 * scale
    font = font_badge if scale >= 1 else font_badge_s
    for i, letter in enumerate(who):
        cx = x + d / 2 + i * step
        sk.stroke(ellipse_pts(cx, y - 9 * scale, d / 2, d / 2, n=28, start=sk.rng.uniform(0, 6)),
                  width=3.2, amp=0.3, closed=True, color=PEOPLE.get(letter))
        sk.text((cx, y - 1 * scale), letter, font, anchor='ms')
    return len(who) * step + 6 * scale if who else 0


def _badges_width(who, scale=1.0):
    return len(who) * 31 * scale + 6 * scale if who else 0


def _row(sk, x, y, ev):
    """HH:MM, person rings, short title; baseline y."""
    sk.text((x, y), ev['start'].strftime('%H:%M'), font_time)
    cx = x + 80
    cx += _badges(sk, cx, y, ev['who'])
    sk.text((cx, y), fit_words(ev['title'], font_title, LW - cx), font_title)


def _wrap(items, x0, x1, font, scale=0.85):
    """Lay out 'A, (K) B, C' with line breaks between items: list of lines of (item, text, x)."""
    lines, cx = [[]], x0
    for i, it in enumerate(items):
        txt = it['title'] + (',' if i < len(items) - 1 else '')
        w = _badges_width(it['who'], scale) + font.width(txt) + 10
        if cx + w > x1 and cx > x0:
            lines.append([])
            cx = x0
        lines[-1].append((it, txt, cx))
        cx += w
    return lines


def _draw_wrapped(sk, lines, y, font, line_h, x1, scale=0.85):
    for li, line in enumerate(lines):
        yy = y + li * line_h
        for it, txt, x in line:
            cx = x + _badges(sk, x, yy, it['who'], scale)
            sk.text((cx, yy), fit(txt, font, x1 - cx), font)


def _icons(sk, x, y, icons, size=32):
    for ic in icons:
        ic(sk, x, y, size)
        x += size + 8
    return x


def _temp(t):
    return f"{round(t)}°".replace('-', '−')


def _draw_header(sk, today):
    date = f"{WEEKDAYS[today.weekday()].capitalize()} {today.day}. {MONTHS[today.month - 1]}"
    box = sk.text((28, 47), date, font_date)
    return box[2] + 12


def _draw_now(sk, current):
    if not current:
        return
    temp = _temp(current['temp'])
    sk.text((RE - 4, 48), temp, font_now_temp, anchor='rs')
    weather_icon(sk, current['icon'], RE - 4 - font_now_temp.width(temp) - 50, 14, 42)


def _until(d):
    return f"til {d.day}/{d.month}"


def _draw_agenda(sk, evs, today):
    """Draw the agenda column; returns what was shown (for tests): counts and the lowest baseline."""
    tomorrow = today + datetime.timedelta(days=1)
    ongoing = [e for e in evs if is_ongoing(e, today)]
    today_rows = day_rows(evs, today, today)
    tom_rows = day_rows(evs, tomorrow, today)

    # Today and tomorrow are always shown in full. When they don't fit: tighter rows, then tomorrow
    # listed compactly ("18:30 Øvelseskjøring, 19:00 Piano") like the later days, then today as well.
    def timed_items(rows):
        return [dict(ev, title=f"{ev['start'].strftime('%H:%M')} {ev['title']}") for ev in rows]

    def block_height(rows, row, compact):
        if compact:
            return len(_wrap(timed_items(rows), LX + 6, LW, font_later)) * LROW
        return len(rows) * row

    def layout_end(row, compact_today, compact_tom):
        y = TOP + (len(ongoing) * row + 10 if ongoing else 0)
        y += block_height(today_rows, row, compact_today) + 6
        if not tom_rows:
            return y
        return y + row + 2 + block_height(tom_rows, row, compact_tom) - (LROW if compact_tom else row)

    for row, compact_today, compact_tomorrow in ((ROW, False, False), (30, False, False),
                                                  (30, False, True), (30, True, True)):
        if layout_end(row, compact_today, compact_tomorrow) <= BOTTOM:
            break

    def draw_block(rows, y, compact):
        if compact:
            lines = _wrap(timed_items(rows), LX + 6, LW, font_later)
            lines = lines[:max(1, (BOTTOM - y) // LROW + 1)]  # never draw past the bottom
            _draw_wrapped(sk, lines, y, font_later, LROW, LW)
            return y + len(lines) * LROW, y + (len(lines) - 1) * LROW
        for ev in rows:
            _row(sk, LX + 6, y, ev)
            y += row
        return y, y - row

    y = TOP
    if ongoing:
        sk.rect(LX, y - 27, LW, y - 27 + len(ongoing) * row + 6, width=1.8, amp=0.8)
        for e in ongoing:
            cx = LX + 10 + _badges(sk, LX + 10, y, e['who'])
            until = _until(e['last'])
            uw = font_time.width(until)
            box = sk.text((cx, y), fit_words(e['title'], font_ongoing, LW - cx - uw - 16), font_ongoing)
            sk.text((box[2] + 8 if e['title'] else cx, y), until, font_time)
            y += row
        y += 10

    y, last = draw_block(today_rows, y, compact_today)
    y += 6

    tom_icons = day_icons(evs, tomorrow, today)
    if tom_rows or tom_icons:
        label = sk.text((LX + 8, y), "I morgen", font_section)
        _icons(sk, label[2] + 10, y - 27, tom_icons)
        last = y
        y += row + 2
        if tom_rows:
            y, last = draw_block(tom_rows, y, compact_tomorrow)

    # Later days (0-3): a day is shown only if all of its events fit
    later = {}
    for e in evs:
        if e['first'] > tomorrow:
            later.setdefault(e['first'], []).append(e)
    ly, shown = y + 16, 0
    for d, items in sorted(later.items())[:3]:
        lines = _wrap(items, LX + 74, LW, font_later)
        if ly + (len(lines) - 1) * LROW > BOTTOM:
            break
        dn = WEEKDAYS_SHORT[d.weekday()] if (d - today).days < 7 else f"{d.day}/{d.month}"
        sk.text((LX + 6, ly), dn, font_time)
        _draw_wrapped(sk, lines, ly, font_later, LROW, LW)
        last = ly + (len(lines) - 1) * LROW
        ly += len(lines) * LROW + 2
        shown += 1
    if shown:
        sk.dashed((LX + 4, y - 18), (LW, y - 17), dash=8, gap=7, width=1.8, amp=0.6)
    return {'ongoing': len(ongoing), 'today': len(today_rows), 'tomorrow': len(tom_rows),
            'tomorrow_heading': bool(tom_rows or tom_icons),
            'compact_today': compact_today, 'compact_tomorrow': compact_tomorrow,
            'later_days': shown, 'last_baseline': last}


def _wx_at(hours, d, hour):
    """Forecast entry for date d nearest to hour, plus precipitation summed over the 4 hours from it."""
    day = [h for h in hours if h['date'] == d]
    if not day:
        return None, 0
    h = min(day, key=lambda h: abs(h['hour'] - hour))
    precip = sum(x['precip'] for x in day if hour <= x['hour'] < hour + 4)
    return h, precip


def _draw_weather(sk, hours, now):
    """Four cells (08, 12, 16, 20) for today; from 16:00 for tomorrow. Past cells show only the hour."""
    day = now.date()
    title = "Været i dag"
    if now.hour >= 16:
        day += datetime.timedelta(days=1)
        title = "Været i morgen"
    sk.text((RX + 4, TOP), title, font_wx_head)
    cw = (RE - RX) / 4
    for i, hour in enumerate((8, 12, 16, 20)):
        cx = RX + cw * i + cw / 2
        sk.text((cx, TOP + 30), f"{hour:02d}", font_small_b, anchor='ms')
        h, precip = _wx_at(hours, day, hour)
        if not h or abs(h['hour'] - hour) > 1:
            # No forecast for an hour that has passed
            sk.line((cx - 10, TOP + 82), (cx + 10, TOP + 81), width=2.2, amp=0.4)
            continue
        weather_icon(sk, h['icon'], cx - 21, TOP + 36, 42)
        sk.text((cx, TOP + 100), _temp(h['temp']), font_wx_temp, anchor='ms')
        wind_icon(sk, cx - 24, TOP + 115, 21)
        sk.text((cx + 2, TOP + 130), str(round(h['wind'])), font_small)
        if precip >= 0.1:
            drop_icon(sk, cx - 20, TOP + 141, 14)
            sk.text((cx - 2, TOP + 156), '<1' if precip < 1 else str(round(precip)), font_small_b, color=BLUE)
    sk.dashed((RX + 6, TOP + 168), (RE - 4, TOP + 169), dash=8, gap=7, width=1.6, amp=0.6)


def _birthday_lines(names, max_w):
    """Names for the big text: full names if they fit, else first + last name, else first names; max 2 lines."""
    def variants(n):
        parts = n.split()
        return [n, f"{parts[0]} {parts[-1]}", parts[0]] if len(parts) > 2 else [n, parts[0]]

    fits = lambda t: font_countdown.width(t) <= max_w
    best = lambda n, suffix='': next((v + suffix for v in variants(n) if fits(v + suffix)),
                                     fit(n.split()[0] + suffix, font_countdown, max_w))
    if len(names) == 1:
        return [best(names[0])]
    if len(names) == 2:
        return [best(names[0], ' og'), best(names[1])]
    # Several people: first names, comma separated over two lines
    firsts = [n.split()[0] for n in names]
    joined = ', '.join(firsts[:-1]) + ' og ' + firsts[-1]
    lines = [[]]
    for word in joined.split(' '):
        if lines[-1] and not fits(' '.join(lines[-1] + [word])) and len(lines) < 2:
            lines.append([])
        lines[-1].append(word)
    return [fit(' '.join(words), font_countdown, max_w) for words in lines]


def _draw_birthday(sk, names):
    """Balloons and the names of today's birthday people, in place of the season field."""
    x, y, w = RX + 8, TOP + 182, RE - RX - 8
    balloon(sk, x + 2, y - 2, 46)
    lines = _birthday_lines(names, RE - x - 50)
    for i, line in enumerate(lines):
        sk.text((x + 50, y + 30 + i * 34), line, font_countdown)
    y += 30 + (len(lines) - 1) * 34
    sk.text((x + 50, y + 28), "har bursdag!", font_small)
    y += 42
    birthday_scene(sk, x, y, w, 462 - y)


def _draw_season(sk, today):
    x, y, w = RX + 8, TOP + 182, RE - RX - 8
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
    # Today's birthdays get the season field; tomorrow's a balloon by "I morgen"; later ones are left out
    birthdays = [e['name'] for e in evs if e['birthday'] and e['first'] == today]
    evs = [e for e in evs if not e['birthday'] or e['first'] == tomorrow]
    # Seed by date so the hand-drawn wobble stays put between refreshes in a day (no ghosting)
    sk = Sketch(W, H, seed=today.toordinal())

    sk.wave_border(11, 11, 789, 469)

    hx = _draw_header(sk, today)
    _icons(sk, hx, 20, day_icons(evs, today, today), size=30)
    _draw_now(sk, weather.get('now'))
    sk.stroke([(24, 62), (400, 63), (776, 64)], width=2.4, amp=0.8)

    _draw_agenda(sk, evs, today)
    sk.stroke([(509, TOP - 22), (509.5, 280), (510, 458)], width=1.6, amp=1.2)  # column divider
    _draw_weather(sk, weather.get('hours', []), now)
    if birthdays:
        _draw_birthday(sk, birthdays)
    else:
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
