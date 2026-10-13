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


class PeoplePrefixTest(unittest.TestCase):
    CASES = {
        'S: piano Ekeberg': ('S', 'piano Ekeberg'),
        'K Øvelseskjøring med Solveig': ('K', 'Øvelseskjøring med Solveig'),
        'K&R&E: 9A1 Høsttreff': ('KRE', '9A1 Høsttreff'),
        'R og S:Tusenfryd': ('RS', 'Tusenfryd'),
        'R og S og E: Kino': ('RSE', 'Kino'),
        'K, M: Middag': ('KM', 'Middag'),
        'E6 stengt': (None, None),
        'Tannlege': (None, None),
    }

    def test_cases(self):
        for title, (who, rest) in self.CASES.items():
            with self.subTest(title=title):
                m = main.PEOPLE_PREFIX.match(title)
                if who is None:
                    self.assertIsNone(m)
                else:
                    self.assertIsNotNone(m)
                    self.assertEqual(''.join(c for c in m.group(1) if c.isupper()), who)
                    self.assertEqual(m.group(2), rest)


if __name__ == '__main__':
    unittest.main()
