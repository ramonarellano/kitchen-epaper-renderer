# kitchen-epaper-renderer

Google Cloud Function (`epaper`, europe-north1) that renders the 800×480 kitchen e-paper image.
The ESP32 fetches `?format=raw` once an hour; if the function errors, the display silently keeps its old image.

## Deploying

Always deploy with `./deploy.sh`. Never run `gcloud functions deploy` directly.
The script runs the tests, deploys only if they pass, then checks that the live function returns a valid raw frame.

When changing `main.py`, keep `load_credentials`, `get_events` and `get_weather`: `epaper()` depends on them.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests fake only the external services (Secret Manager, Google Calendar, met.no) and run the real code path.
Add a case to `tests/test_epaper.py` when fixing a bug.
