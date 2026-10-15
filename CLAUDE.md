# kitchen-epaper-renderer

Google Cloud Function (`epaper`, europe-north1) that renders the 800×480 kitchen e-paper image.
The ESP32 fetches `?format=raw` once an hour; if the function errors, the display silently keeps its old image.
The firmware lives in the sibling repos `../kitchen-epaper-esp32` and `../kitchen-epaper-display`.

## Code map

| File | What it does |
|---|---|
| `main.py` | Entry point `epaper(request)`, data fetching (`get_events`, `get_weather`), parsing of calendar titles, the whole layout (`render_image` and the `_draw_*` helpers), and the raw encoder `pil_to_waveshare_7in3f_raw` |
| `sketch.py` | Hand-drawn drawing primitives (`Sketch`), `Font`, the 7-color `PALETTE`, weather icons drawn from met.no `symbol_code`s, small event icons |
| `seasonal.py` | Holidays (`special_days`), countdown (`next_countdown`), seasonal themes (`THEMES`), the season scene and the birthday scene |
| `tests/test_epaper.py` | End-to-end and layout tests |
| `deploy.sh` | Tests → deploy → smoke test. Holds the env vars, including the weather location |
| `design/` | Design spec (Norwegian), browser prototype, reference renders. Not deployed |

Data flow: `epaper()` → `get_events()` (Google Calendar, 14 days, via a service-account key in Secret Manager)
+ `get_weather()` (met.no locationforecast, today and tomorrow in Oslo time) → `render_image()` returns PNG bytes
→ converted to JPEG or raw if asked for.

## Where to change common things

- **Weather location:** `YR_LAT`/`YR_LON` in `deploy.sh` (now Kjelsås, 59.97/10.78). Takes effect on the next deploy.
- **Calendar:** `CALENDAR_ID` in `deploy.sh`. The calendar must be shared with the service account.
- **Family members:** `PEOPLE` (initial → ring colour) and `NAMES` (first name → initial) in `main.py`.
- **Title shortening:** `SHORT_TITLES` and `DANGLING` in `main.py`.
- **Icons for all-day events:** `EVENT_ICONS` (regex → icon function) in `main.py`; draw new icons in `sketch.py`.
- **Holidays and countdowns:** `special_days()` in `seasonal.py`; season scenes in `THEMES` and `theme_key()`.
- **Layout geometry:** the constants below `W, H` in `main.py` (column edges, row heights, `TOP`, `BOTTOM`) and the fonts at the top.

## Rules the output must keep

- Only the 7 exact palette colors, no grey and no dithering. `sketch.py` guarantees this; draw through `Sketch`, never with raw PIL on the final image.
- `PALETTE` in `sketch.py` and the palette in `pil_to_waveshare_7in3f_raw` must stay in the same order (it is the panel's colour index).
- The raw frame is rotated 180° (the panel hangs upside down) and must be exactly 192000 bytes; the ESP32 expects that.
- All text at least 22 px (initials in small rings: 18 px). The display is read from across the kitchen.
- `Sketch` is seeded with the date, so the same data on the same day gives a pixel-identical image (avoids ghosting). Use `sk.rng` for randomness, never `random` directly.
- All times and day boundaries use `OSLO_TZ`.
- Today's and tomorrow's events are always shown in full; later days are dropped before anything is cut.

## Design

The design spec is `design/DESIGN-kjokkentavle.md` (with a browser prototype and reference renders in `design/`).
When you change the layout, update the spec in the same commit; the code is the source of truth if they disagree.

## Previewing a render locally

`render_image(events, weather, now=None)` needs no network. Events are `(date, start, end, summary)` tuples as returned by `get_events()`,
weather is `{'now': hour_dict_or_None, 'hours': [...]}` as returned by `get_weather()`:

```bash
CALENDAR_ID=x YR_LAT=59.97 YR_LON=10.78 SECRET_NAME=x .venv/bin/python -c "
import main
open('/tmp/preview.png', 'wb').write(main.render_image([('', '2026-10-14T18:00:00+02:00', '2026-10-14T19:00:00+02:00', 'S: Piano')], {'now': None, 'hours': []}))"
```

Look at the PNG after layout changes; the tests check structure, not looks.

## Shipping changes

Ramon is the only one working in this repo: no branches, pull requests or reviews.
After every change, ask Ramon whether to ship it. On a yes, do all three without asking again:
commit to `main`, push `main` to `origin`, and deploy with `./deploy.sh`.

## Deploying

Always deploy with `./deploy.sh`. Never run `gcloud functions deploy` directly.
The script runs the tests, deploys only if they pass, then checks that the live function returns a valid raw frame.
Check what is live with:

```bash
gcloud functions describe epaper --gen2 --region=europe-north1 --format="yaml(serviceConfig.environmentVariables,updateTime)"
```

When changing `main.py`, keep `load_credentials`, `get_events` and `get_weather`: `epaper()` depends on them.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests fake only the external services (Secret Manager, Google Calendar, met.no) and run the real code path.
Add a case to `tests/test_epaper.py` when fixing a bug.

## Leftovers

Not used by the current code; don't build on them:
`icons/` (weather icons are drawn in `sketch.py`), `fonts/Roboto-Regular.ttf`, `convert_svg_to_png.py`, `fetch_missing_icons.py` and `copilot-instructions.md`.
The "Run epaper locally" task in `tasks.json` / `.vscode/tasks.json` points to an old key path and the Oslo centre coordinates.
