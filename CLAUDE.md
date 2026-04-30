# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this does

Polls JCC Software-powered appointment booking systems (e.g., `https://gemeente.mijnafspraakmaken.nl`) and sends notifications when slots open up within a configured time window. A web dashboard shows current availability and a change log.

This tool is designed for Dutch municipalities using JCC-Afspraken (appointment module). The checker uses Playwright to automate the citizen-facing web interface and intercept availability data, requiring no API credentials.

## Architecture

Two containers share a `./data` bind-mount:

- **`appointment-checker`** runs `check_appointments.py` in a loop. It uses **Playwright** to drive a headless Chromium browser through the municipality's appointment booking SPA (JS execution required), intercepts JSON responses from the JCC Software API backend (`online3.jccsoftware.nl`, identified via CSP header), and appends available slots to `/data/appointments.db` after each check. Sends notifications via the configured provider when new slots become available. Sleep between runs is randomised ±30% around the configured interval to mimic human timing; navigation step delays use `human_wait()` with ±40% jitter.

- **`appointment-dashboard`** runs `dashboard.py` (Flask, port 8800). Reads from `/data/appointments.db` (SQLite), shows the current slots as cards, and displays a change log (slots added/removed). All configuration is managed through the dashboard UI. The database is the source of truth for both state and settings.

## Build & run

```bash
# Build and start both containers
docker compose up -d --build

# Test a single check without waiting
docker compose run --rm appointment-checker python check_appointments.py --once

# View logs
docker compose logs -f
docker compose logs -f appointment-dashboard
```

## Configuration

All settings are managed through the SQLite database via the Dashboard UI:

### Settings (configured in Dashboard)
- **appointment_url** — URL to municipality's appointment booking page (required)
- **check_interval_seconds** — Seconds between checks (default: 3600, minimum: 300)
- **check_days_ahead** — Days ahead to look for available slots (default: 7)
- **notification_provider** — ntfy (default), email (planned), webhook (planned)
- **notification_endpoint** — NTFY URL or email address (required for notifications)

### Environment Variables (Docker)
- `LOG_LEVEL` — INFO (default) or DEBUG for verbose logging
- `SCREENSHOT_ON_ERROR` — true/false, save screenshot on errors
- `DATA_DIR` — /data (where database and history are stored)

## Database schema

The SQLite database (`/data/appointments.db`) stores:

- **settings** table — Configuration (appointment_url, check_interval_seconds, check_days_ahead, notification_provider, notification_endpoint)
- **appointments** table — Available appointment slots (slot_datetime, checked_at)
- **notifications** table — Sent notifications log (slot_datetime, sent_at)

The dashboard diffs consecutive appointment sets to detect and display changes in availability.

## Debugging

### No appointments found

1. Check the Change Log page in the dashboard—recent checks show "no available slots"
2. Verify the appointment_url is correct in Settings
3. Try visiting the URL in a browser to confirm it works
4. Set LOG_LEVEL=DEBUG to see intercepted API calls

### Notifications not arriving

1. Check Settings → is the notification_endpoint configured?
2. For ntfy, test the endpoint directly: `https://your-ntfy-endpoint`
3. Check if slots actually changed (same slots = no notification)

### Docker issues

1. View logs: `docker-compose logs -f`
2. Run single check: `docker-compose run --rm appointment-checker python check_appointments.py --once`
3. Set `SCREENSHOT_ON_ERROR=true` and mount `./screenshots:/tmp` in `docker-compose.yml` to inspect browser state
4. The script logs every intercepted API URL at DEBUG level; set `LOG_LEVEL=DEBUG` to see them
5. Key interception keywords: `availabletimelist`, `firstavailableappointmenttime`
