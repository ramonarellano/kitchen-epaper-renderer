#!/usr/bin/env bash
# Test, deploy and smoke-test the epaper Cloud Function.
# Deploys only if every test passes; fails loudly if the live function does not answer afterwards.
set -euo pipefail
cd "$(dirname "$0")"

URL="https://europe-north1-kitche-epaper-renderer.cloudfunctions.net/epaper"

# 1. Tests, in a local venv with the same requirements as the cloud runtime
if [ ! -x .venv/bin/python ]; then
  "${PYTHON:-python3}" -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -W ignore -m unittest discover -s tests -v

# 2. Deploy
gcloud functions deploy epaper --gen2 --runtime=python310 --trigger-http --allow-unauthenticated \
  --entry-point=epaper --region=europe-north1 \
  --set-env-vars=CALENDAR_ID=48otkcqvhjlqlogfkgic7labis@group.calendar.google.com,YR_LAT=59.91,YR_LON=10.75,SECRET_NAME=projects/14548432634/secrets/kitchen-epaper-renderer-google-calendar-secret

# 3. Smoke test the live function with the same request the ESP32 makes
size=$(curl -sf -o /dev/null -w '%{size_download}' "$URL?format=raw") || {
  echo "DEPLOY BROKEN: $URL?format=raw does not return 200 — roll back or fix now" >&2
  exit 1
}
if [ "$size" != "192000" ]; then
  echo "DEPLOY BROKEN: raw frame is $size bytes, expected 192000" >&2
  exit 1
fi
echo "Deploy OK: raw frame is 192000 bytes"
