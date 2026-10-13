"""End-to-end tests for the epaper Cloud Function. Run before every deploy:

    python -m unittest discover -s tests -v

Only the outside world is faked (Secret Manager, Google Calendar API, met.no);
everything in main.py runs for real, so a missing function or a crash anywhere
in fetching, rendering or encoding fails the test.
"""
import datetime
import io
import json
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)  # fonts are loaded with relative paths
sys.path.insert(0, ROOT)
os.environ.setdefault('CALENDAR_ID', 'test-calendar')
os.environ.setdefault('YR_LAT', '59.91')
os.environ.setdefault('YR_LON', '10.75')
os.environ.setdefault('SECRET_NAME', 'projects/test/secrets/test')

# The Google client libraries are faked in the tests anyway; stub them if not installed locally
try:
    import googleapiclient.discovery  # noqa: F401
    import google.oauth2.service_account  # noqa: F401
    import google.cloud.secretmanager  # noqa: F401
except ImportError:
    for name in ['googleapiclient', 'googleapiclient.discovery', 'google', 'google.oauth2',
                 'google.oauth2.service_account', 'google.cloud', 'google.cloud.secretmanager']:
        sys.modules[name] = types.ModuleType(name)
    sys.modules['googleapiclient.discovery'].build = None
    sys.modules['google.oauth2'].service_account = types.SimpleNamespace()
    sys.modules['google.cloud'].secretmanager = types.SimpleNamespace()

from PIL import Image  # noqa: E402

import main  # noqa: E402
from sketch import PALETTE  # noqa: E402

NS = types.SimpleNamespace


def _calendar_items(today):
    iso = lambda days: (today + datetime.timedelta(days=days)).isoformat()
    at = lambda days, hm: f"{iso(days)}T{hm}:00+02:00"
    return [
        {'start': {'date': iso(-3)}, 'end': {'date': iso(2)}, 'summary': 'Kari Kanariøyene '},
        {'start': {'dateTime': at(0, '08:30')}, 'end': {'dateTime': at(0, '09:00')}, 'summary': 'Levere i barnehagen'},
        {'start': {'dateTime': at(0, '17:00')}, 'end': {'dateTime': at(0, '18:30')}, 'summary': 'E: Fotballtrening'},
        {'start': {'date': iso(1)}, 'end': {'date': iso(2)}, 'summary': 'Søppeltømming'},
        {'start': {'dateTime': at(1, '19:00')}, 'end': {'dateTime': at(1, '20:00')}, 'summary': 'S: piano Ekeberg'},
        {'start': {'dateTime': at(2, '10:00')}, 'end': {'dateTime': at(2, '11:00')}, 'summary': 'Tannlege'},
        {'start': {'dateTime': at(3, '16:30')}, 'end': {'dateTime': at(3, '18:30')}, 'summary': 'K&R&E: 9A1 Høsttreff'},
        {'start': {'dateTime': at(4, '12:00')}, 'end': {'dateTime': at(6, '12:00')}, 'summary': 'R og S:Tusenfryd'},
        {'start': {'dateTime': at(5, '09:00')}, 'end': {'dateTime': at(5, '10:00')}},  # no title
    ]


def _metno_forecast():
    """Hourly met.no 'compact' forecast for the next 60 hours."""
    start = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    symbols = ['clearsky_day', 'fair_night', 'partlycloudy_day', 'cloudy', 'lightrain', 'heavyrainandthunder',
               'sleet', 'snowshowers_day', 'fog']
    series = []
    for i in range(60):
        series.append({
            'time': (start + datetime.timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'data': {
                'instant': {'details': {'air_temperature': -3 + (i % 15), 'wind_speed': (i % 9) * 0.9}},
                'next_1_hours': {'summary': {'symbol_code': symbols[i % len(symbols)]},
                                 'details': {'precipitation_amount': [0, 0, 0.4, 2.3][i % 4]}},
            },
        })
    return {'properties': {'timeseries': series}}


def _fake_build(name, version, credentials=None):
    today = datetime.datetime.now(main.OSLO_TZ).date()
    listing = NS(execute=lambda: {'items': _calendar_items(today)})
    return NS(events=lambda: NS(list=lambda **kwargs: listing))


def _fake_secretmanager():
    payload = NS(data=json.dumps({'type': 'service_account'}).encode())
    client = NS(access_secret_version=lambda name: NS(payload=payload))
    return NS(SecretManagerServiceClient=lambda: client)


class EpaperEndpointTest(unittest.TestCase):
    """Calls the real Cloud Function entry point with faked external services."""

    def setUp(self):
        patches = [
            mock.patch.object(main, 'secretmanager', _fake_secretmanager()),
            mock.patch.object(main, 'service_account', NS(Credentials=NS(
                from_service_account_info=lambda info, scopes=None: object()))),
            mock.patch.object(main, 'build', _fake_build),
            mock.patch.object(main.requests, 'get', lambda url, headers=None, **kw: NS(json=_metno_forecast)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def call(self, fmt):
        body, status, headers = main.epaper(NS(args={'format': fmt}))
        self.assertEqual(status, 200)
        return body, headers

    def test_png_is_800x480_with_panel_colors_only(self):
        body, headers = self.call('png')
        self.assertEqual(headers['Content-Type'], 'image/png')
        img = Image.open(io.BytesIO(body)).convert('RGB')
        self.assertEqual(img.size, (800, 480))
        colors = {c for _, c in img.getcolors(1 << 16)}
        self.assertTrue(colors <= set(PALETTE), f"non-palette colors: {colors - set(PALETTE)}")

    def test_raw_is_packed_7_color_frame(self):
        body, headers = self.call('raw')
        self.assertEqual(headers['Content-Type'], 'application/octet-stream')
        self.assertEqual(len(body), 800 * 480 // 2)
        self.assertTrue(all((b >> 4) < 7 and (b & 0xF) < 7 for b in body), "palette index out of range")

    def test_jpeg(self):
        body, headers = self.call('jpeg')
        self.assertEqual(headers['Content-Type'], 'image/jpeg')
        self.assertEqual(Image.open(io.BytesIO(body)).size, (800, 480))


class RenderAcrossTheYearTest(unittest.TestCase):
    """Every seasonal theme and holiday countdown must render without errors."""

    DATES = ['2026-01-01', '2026-02-08', '2026-02-14', '2026-03-10', '2026-04-04', '2026-05-17', '2026-06-23',
             '2026-07-15', '2026-09-10', '2026-10-31', '2026-11-08', '2026-11-25', '2026-12-13', '2026-12-24',
             '2026-12-31']

    def test_dates(self):
        for date in self.DATES:
            for hm in ('06:30', '13:00', '23:30'):
                with self.subTest(date=date, time=hm):
                    now = main.OSLO_TZ.localize(datetime.datetime.strptime(f"{date} {hm}", '%Y-%m-%d %H:%M'))
                    events = [(e['start'].get('date', e['start'].get('dateTime', ''))[:10],
                               e['start'].get('dateTime', e['start'].get('date')),
                               e['end'].get('dateTime', e['end'].get('date')), e.get('summary', '(No title)'))
                              for e in _calendar_items(now.date())]
                    hours = [{'time': now + datetime.timedelta(hours=i), 'date': (now + datetime.timedelta(hours=i)).date(),
                              'hour': (now + datetime.timedelta(hours=i)).hour, 'temp': -2 + i % 10, 'wind': 3,
                              'precip': 0.5 if i % 3 == 0 else 0, 'icon': 'rain' if i % 3 == 0 else 'fair_day'}
                             for i in range(48)]
                    png = main.render_image(events, {'now': hours[0], 'hours': hours}, now=now)
                    self.assertEqual(Image.open(io.BytesIO(png)).size, (800, 480))

    def test_empty_calendar_and_weather(self):
        png = main.render_image([], {'now': None, 'hours': []})
        self.assertEqual(Image.open(io.BytesIO(png)).size, (800, 480))


class ShortTitleTest(unittest.TestCase):
    """Calendar title -> (people, short title), spec §4.3 and §5."""
    CASES = {
        'S: piano Ekeberg': ('S', 'piano Ekeberg'),
        'K Øvelseskjøring': ('K', 'Øvelseskjøring'),
        'K&R&E: 9A1 Høsttreff': ('KRE', '9A1 Høsttreff'),
        'R og S:Tusenfryd': ('RS', 'Tusenfryd'),
        'R og S og E: Kino': ('RSE', 'Kino'),
        'Fotballtrening Emilie': ('E', 'Fotballtrening'),
        'K: Øvelseskjøring med Solveig': ('KS', 'Øvelseskjøring'),
        'Luciatog Solveig og Emilie': ('SE', 'Luciatog'),
        'Ramon og Solveig: Tidlig tog': ('RS', 'Tidlig tog'),
        'Middag hos Solveig': ('S', 'Middag'),
        'Middag hos Maria': ('', 'Middag hos Maria'),
        'Foreldremøte – klasse 9A': ('', 'Foreldremøte'),
        'Levere i barnehagen': ('', 'Barnehagen'),
        'E6 stengt': ('', 'E6 stengt'),
        'Karis bursdag': ('', 'Karis bursdag'),
        'A: Middag': ('A', 'Middag'),
        'Alle: Middag': ('A', 'Middag'),
        'Alle og K: Kino': ('AK', 'Kino'),
        'Middag Alle': ('A', 'Middag'),
        'Foreldremøte for alle': ('', 'Foreldremøte for alle'),
        'A-hus': ('', 'A-hus'),
    }

    def test_cases(self):
        for title, expected in self.CASES.items():
            with self.subTest(title=title):
                self.assertEqual(main.short_title(title), expected)

    def test_fit_words_does_not_end_on_little_word(self):
        cut = main.fit_words('Lunsj med kolleger fra jobben i byen', main.font_title, 300)
        self.assertFalse(cut.split()[-1] in main.DANGLING, cut)


class AgendaLayoutTest(unittest.TestCase):
    """Spec §4.2: today and tomorrow always complete, later days whole or not at all, nothing below y=452."""
    NOW = main.OSLO_TZ.localize(datetime.datetime(2026, 10, 12, 7, 30))

    def agenda(self, events):
        sk = main.Sketch(main.W, main.H, seed=1)
        return main._draw_agenda(sk, main.parse_events(events), self.NOW.date())

    @staticmethod
    def timed(day_offset, hm, title, minutes=60):
        hour, minute = (int(v) for v in hm.split(':'))
        st = datetime.datetime(2026, 10, 12 + day_offset, hour, minute)
        et = st + datetime.timedelta(minutes=minutes)
        return (st.date().isoformat(), st.strftime('%Y-%m-%dT%H:%M:00+02:00'), et.strftime('%Y-%m-%dT%H:%M:00+02:00'), title)

    @staticmethod
    def allday(day_offset, title, days=1):
        d = datetime.date(2026, 10, 12) + datetime.timedelta(days=day_offset)
        return (d.isoformat(), d.isoformat(), (d + datetime.timedelta(days=days)).isoformat(), title)

    def test_ongoing_count(self):
        for n in (0, 1, 2):
            with self.subTest(ongoing=n):
                events = [self.allday(-1, f'Reise {i}', 4) for i in range(n)] + [self.timed(0, '08:30', 'Barnehagen')]
                self.assertEqual(self.agenda(events)['ongoing'], n)

    def test_busy_tomorrow_is_complete_and_later_days_dropped(self):
        events = [self.timed(0, '08:30', 'Barnehagen'), self.timed(0, '17:00', 'Fotball')]
        events += [self.timed(1, f'{8 + i}:00', f'Avtale {i}') for i in range(6)]
        events += [self.timed(2, '10:00', 'Tannlege'), self.timed(3, '10:00', 'Lunsj')]
        shown = self.agenda(events)
        self.assertEqual((shown['today'], shown['tomorrow']), (2, 6))
        self.assertLessEqual(shown['last_baseline'], main.BOTTOM)

    def test_very_busy_days_still_complete(self):
        events = [self.allday(-1, 'Reise', 4), self.allday(-1, 'Kari i Bergen', 4)]
        events += [self.timed(0, f'{7 + i}:00', f'I dag {i}') for i in range(5)]
        events += [self.timed(1, f'{7 + i}:00', f'I morgen {i}') for i in range(7)]
        shown = self.agenda(events)
        self.assertEqual((shown['today'], shown['tomorrow']), (5, 7))
        self.assertTrue(shown['compact_tomorrow'])
        self.assertLessEqual(shown['last_baseline'], main.BOTTOM)

    def test_later_day_whole_or_not_at_all(self):
        events = [self.timed(0, '08:30', 'Barnehagen'), self.timed(1, '18:30', 'Skvåsj')]
        events += [self.timed(2, '10:00', 'Tannlege')]
        events += [self.timed(3, f'{8 + i}:00', f'Langt navn på avtale nummer {i}') for i in range(12)]
        shown = self.agenda(events)
        self.assertEqual(shown['later_days'], 1)  # the long day does not fit and is dropped entirely
        self.assertLessEqual(shown['last_baseline'], main.BOTTOM)

    def test_no_tomorrow_heading_without_events(self):
        self.assertFalse(self.agenda([self.timed(0, '08:30', 'Barnehagen'), self.timed(2, '10:00', 'Tannlege')])['tomorrow_heading'])
        self.assertTrue(self.agenda([self.allday(1, 'Søppeltømming')])['tomorrow_heading'])
        self.assertTrue(self.agenda([self.timed(1, '10:00', 'Tannlege')])['tomorrow_heading'])

    def test_same_data_gives_identical_image(self):
        events = [self.timed(0, '08:30', 'Barnehagen'), self.allday(1, 'Søppeltømming')]
        weather = {'now': None, 'hours': []}
        self.assertEqual(main.render_image(events, weather, now=self.NOW), main.render_image(events, weather, now=self.NOW))


if __name__ == '__main__':
    unittest.main()
