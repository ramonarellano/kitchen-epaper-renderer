# kitchen-epaper-renderer

This project renders an image for a Waveshare 7.3" e-paper display, showing:
- **Weather for Oslo** (from yr.no/Met.no) in 8 two-hour periods (icon, time, temp, precip, wind)
- **Google Calendar agenda** (multi-day, green event boxes, Norwegian date titles)
- Modern layout using Roboto font and attractive icons
- Output formats: PNG, JPEG, or raw 7-color e-paper format (selectable via endpoint query param)

---

## How it works
- Fetches weather data from [Met.no Locationforecast API](https://api.met.no/weatherapi/locationforecast/2.0/documentation)
- Fetches events from a Google Calendar using a service account
- Renders the image using Pillow (PIL), with robust handling of icons and fonts
- Exposes a single endpoint (`epaper`) that returns the image in the requested format

---

## Google Cloud Setup

### 1. Create a Google Cloud Project
- Go to [Google Cloud Console Projects](https://console.cloud.google.com/cloud-resource-manager)
- Click "Create Project"

### 2. Enable APIs
- Enable the [Google Calendar API](https://console.cloud.google.com/apis/library/calendar.googleapis.com) for your project
- Enable the [Secret Manager API](https://console.cloud.google.com/apis/library/secretmanager.googleapis.com)

### 3. Create a Service Account
- Go to [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
- Click "Create Service Account"
- Give it a name (e.g. `calendar-epaper`)
- Grant the following roles:
  - **Secret Manager Secret Accessor** (`roles/secretmanager.secretAccessor`)
  - **Service Account Token Creator** (`roles/iam.serviceAccountTokenCreator`)
  - **Viewer** (`roles/viewer`) (optional, for debugging)
- Click "Done"

### 4. Create and Download Service Account Key
- Click the service account you just created
- Go to the "Keys" tab
- Click "Add Key" > "Create new key" > JSON
- Download the JSON key file

### 5. Store the Service Account Key in Secret Manager
- Go to [Secret Manager](https://console.cloud.google.com/security/secret-manager)
- Click "Create Secret"
- Name it (e.g. `calendar-sa-key`)
- Upload the JSON key file

### 6. Share Your Google Calendar with the Service Account
- Open your Google Calendar in a browser
- Go to "Settings and sharing" for the calendar you want to use
- Under "Share with specific people", add the service account's email (from the JSON key file)
- Give it "Make changes to events" or at least "See all event details"

### 7. Set Environment Variables
Set the following environment variables for your deployment (Cloud Function, local, etc):
- `CALENDAR_ID` — The calendar's ID (can be found in calendar settings)
- `YR_LAT` and `YR_LON` — Latitude and longitude for weather (Oslo: 59.9139, 10.7522)
- `SECRET_NAME` — The full resource name of your secret, e.g. `projects/<project-id>/secrets/calendar-sa-key`

---

## Local Development
- All assets (icons, fonts) are tracked in git
- Run locally with the correct environment variables set (see above)
- Use the `tasks.json` or run your preferred dev server

---

## Rendering Details
- **Left side:** Agenda, with Norwegian date titles (e.g. "Mandag 25. januar"), green event boxes, truncated titles
- **Right side:** Weather, 8 periods, large icons, time/temp/precip/wind
- **Fonts:** Roboto (in `fonts/`)
- **Icons:** PNGs (in `icons/png/`), mapped to Met.no symbol codes
- **Output:** PNG, JPEG, or raw 7-color (Waveshare format)

---

## Endpoint Usage
- `/epaper?format=png` — PNG image (default)
- `/epaper?format=jpeg` — JPEG image
- `/epaper?format=raw` — Raw 7-color format for e-paper

---

## Troubleshooting
- Ensure all environment variables are set
- Make sure the service account has access to the calendar and secret
- Norwegian locale (`nb_NO.UTF-8`) should be available for date formatting (fallbacks are handled)
- All icons and fonts must be present and tracked in git

---

## References
- [Google Cloud Console](https://console.cloud.google.com/)
- [Met.no Weather API](https://api.met.no/weatherapi/locationforecast/2.0/documentation)
- [Google Calendar API docs](https://developers.google.com/calendar/api)
- [Pillow (PIL)](https://pillow.readthedocs.io/en/stable/)

---

*This README is intended for developers maintaining or extending this project.*
