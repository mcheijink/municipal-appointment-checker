# appointment-checker

Automated appointment availability monitor for Dutch municipalities using JCC Software.

Polls JCC-powered appointment booking systems and sends notifications when slots open within your configured time window. Includes a web dashboard showing current availability and a change log.

---

## Quick Start

### Requirements
- Docker & Docker Compose
- 5-10 minutes for first setup

### 1. Start the containers

```bash
docker-compose up -d --build
```

This starts two services:
- **appointment-checker** - Polls appointments on a schedule, records history, sends notifications
- **dashboard** - Web UI showing availability and change log (port 8800)

### 2. Configure

Open the dashboard: `http://localhost:8800`

Go to **Settings** and configure:
1. **Appointment URL** - Your municipality's booking page (see table below)
2. **Notification Provider** - Choose how to be notified (ntfy.sh by default)
3. **Notification Endpoint** - Your ntfy URL or email address
4. **Check Interval** - How often to check (default: 60 minutes, minimum 5 minutes)

### 3. Watch for appointments

The checker runs in the background. View results on the dashboard:
- **Home** - Currently available appointment slots
- **Change Log** - When slots appeared/disappeared
- **Settings** - Adjust polling frequency and notifications

### Screenshots

**Home** — Current available appointment slots  
![Dashboard home showing available appointments](screenshots/01_home.png)

**Change Log** — Timeline of slot availability changes  
![Change log showing when slots opened/closed](screenshots/02_changelog.png)

**Settings** — Configure appointment URL, polling interval, and notifications  
![Settings page with configuration fields](screenshots/03_settings.png)

---

## Supported Municipalities

This tool works with any municipality using **JCC-Afspraken** (JCC's appointment system). Known municipalities:

- Gemeente Enschede — `https://enschede.mijnafspraakmaken.nl/?product=5`
- Gemeente Eindhoven — `https://eindhoven.mijnafspraakmaken.nl/?product=...`
- Gemeente Venlo
- Gemeente Midden-Groningen
- Stad Gent (Belgium)
- Stad Lier (Belgium)

**Not seeing your municipality?** Check if it's listed on [jccsoftware.nl/klantervaringen](https://jccsoftware.nl/klantervaringen/). Most JCC municipalities follow the pattern `https://{gemeente}.mijnafspraakmaken.nl`.

---

## How It Works

### Polling

The checker runs on a schedule (default: 60 minutes). For each run:

1. **Navigates** the appointment booking page using a headless browser (Playwright)
2. **Intercepts** the JSON API responses containing available slots
3. **Extracts** appointment datetimes and compares with the previous check
4. **Records** the slot history to `data/slot_history.jsonl`
5. **Notifies** if slots within your time window have changed

### Why Playwright?

The booking pages are modern JavaScript SPAs (Aurelia framework) that load appointment data dynamically. Using a headless browser:
- ✅ No API credentials needed (uses the public web interface)
- ✅ Works exactly like a citizen browsing the site
- ⚠️ Fragile to UI/SPA changes (if JCC redesigns, the tool may need updates)

### Why No Official API?

JCC provides a formal **WARP API** for integration partners (requires credentials). This tool instead uses the public-facing website to:
- Avoid partnership negotiations
- Work for any municipality without special access
- Be transparent about the approach

See `JCC_SOFTWARE.md` for technical details.

---

## Configuration

### Settings UI (Recommended)

Open `http://localhost:8800/settings` to configure everything visually:

- **Appointment URL** - Your municipality's booking page
- **Check Interval** - Base delay between checks in seconds (min: 300 = 5 min)
- **Days Ahead** - Look for slots within N days
- **Notification Provider** - ntfy, email (planned), or webhook (planned)
- **Notification Endpoint** - Your notification destination
  - **ntfy:** HTTPS URL (e.g., `https://ntfy.sh/my-topic`)
  - **email:** Email address (not yet implemented)
  - **webhook:** HTTPS endpoint (not yet implemented)

### Environment Variables

For Docker deployment:

```bash
LOG_LEVEL=INFO              # DEBUG for more logging
SCREENSHOT_ON_ERROR=true    # Save debug screenshot on errors
DATA_DIR=/data              # Where to store database & history
DASHBOARD_PORT=8800         # Dashboard port (inside container)
```

Set in `docker-compose.yml` or via `-e` flag.

---

## Notifications

### ntfy.sh (Recommended, Default)

Using the free public ntfy.sh service:

1. Pick a topic name (e.g., `my-enschede-appointments`)
2. Set **Notification Endpoint** to: `https://ntfy.sh/my-enschede-appointments`
3. Subscribe to notifications:
   - Web: `https://ntfy.sh/my-enschede-appointments`
   - Android: [ntfy app](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - iOS: [ntfy app](https://apps.apple.com/us/app/ntfy/id1625396347)
   - Webhook/Curl: Poll the same URL

### Self-Hosted ntfy

Run your own ntfy server:

```bash
docker run -d -p 8080:80 binwiederhier/ntfy serve
```

Set **Notification Endpoint** to your server and topic.

### Email & Webhook (Planned)

Infrastructure is ready for email and webhook providers. Contributions welcome!

---

## Data

### Slot History

All checks are recorded to `data/slot_history.jsonl` (one JSON object per line):

```json
{"checked_at": "2026-04-30T14:32:11", "slots": ["2026-05-02T09:00:00", "2026-05-03T10:30:00"]}
```

The dashboard reads this file to show:
- Current available slots
- Timeline of when slots appeared/disappeared

### Database

Settings and metadata stored in `data/dashboard.db` (SQLite):
- All configuration (appointment URL, check interval, etc.)
- Can be inspected with `sqlite3 data/dashboard.db`

### Logs

Docker logs show the checker's activity:

```bash
docker-compose logs -f appointment-checker
```

---

## Troubleshooting

### No appointments found

1. **Wrong appointment URL?** Verify in Settings. Try visiting it in a browser.
2. **All slots booked?** Check the actual website—the tool mirrors what's available.
3. **Wrong product ID?** Some municipalities have multiple products (e.g., `?product=5`). Try others.

### Notifications not arriving

1. **Endpoint empty?** Go to Settings → fill in notification endpoint.
2. **Endpoint wrong?** For ntfy, try accessing it in browser: `https://ntfy.sh/your-topic`
3. **Slot status unchanged?** Notifications only send when slots *change*. Same slots = no notification.

### Dashboard slow or crashes

- Reduce `SLOT_HISTORY_COUNT` if history file grows too large
- Restart: `docker-compose restart`

### Want to test without waiting?

```bash
docker-compose run --rm appointment-checker python check_appointments.py --once
```

This runs a single check immediately (doesn't wait for the schedule).

---

## Development

### Project Structure

```
.
├── check_appointments.py      # Scheduler & polling logic
├── notification.py            # Notification provider dispatcher
├── dashboard.py               # Flask web UI & settings API
├── database.py                # SQLite settings layer
├── docker-compose.yml         # Container setup
├── Dockerfile                 # Container definition
├── config.example.json        # Example config (for reference)
├── data/                      # Mounted volume (database, history)
└── docs/                      # Documentation & planning
```

### Running Locally (Without Docker)

```bash
# Install dependencies
pip install flask httpx playwright

# Install browser
playwright install

# Initialize database
python -c "from database import init_db; init_db()"

# Run checker once
python check_appointments.py --once

# Run dashboard
python dashboard.py
```

### Adding a New Notification Provider

1. Add provider case to `notification.py:send_notification()`
2. Implement `_send_provider()` function
3. Test in dashboard Settings
4. Commit

Example for email:

```python
def _send_email(endpoint: str, message: str, title: str) -> bool:
    """Send via SMTP"""
    # Implementation here
    pass
```

### Testing with a New Municipality

1. Find the municipality's booking URL (e.g., from jccsoftware.nl customers)
2. Change **Appointment URL** in Settings
3. Run: `docker-compose run --rm appointment-checker python check_appointments.py --once`
4. Check logs for errors or found slots
5. If it works, update this README's municipality table

---

## About JCC Software

**JCC Software** is a Dutch company providing municipal management solutions to ~500 municipalities across the Netherlands, Belgium, and Germany.

- Product: **JCC-Afspraken** (Appointment Scheduling)
- Website: [jccsoftware.nl](https://jccsoftware.nl)
- Supported Municipalities: [klantervaringen](https://jccsoftware.nl/klantervaringen/)

This tool is independent and not affiliated with JCC Software. It uses their public-facing web interfaces in the same way a citizen would.

---

## Limitations & Risks

⚠️ **Know Before Using**

- **SPA changes:** If JCC redesigns the appointment interface, this tool may break until updated
- **Rate limiting:** Don't set check interval below 5 minutes (respects the service)
- **No warranty:** This tool is provided as-is; use at your own risk
- **No login:** Works only with public appointment pages (not systems requiring login)

---

## License

MIT (See LICENSE file)

---

## Contributing

Found a bug? Want to add email or webhook notifications? Contributions welcome!

1. Test your changes locally
2. Create a pull request with a clear description
3. Include any new dependencies

---

## FAQ

**Q: Does this work offline?**  
A: No, it needs internet access to reach the appointment booking page.

**Q: Can I use this for other JCC products?**  
A: Currently only JCC-Afspraken (appointments) is supported.

**Q: Will this break my account or IP?**  
A: No. The checker uses normal browser requests, same as a citizen visiting the site. The default 60-minute interval is respectful.

**Q: Can I configure alerts (e.g., Slack)?**  
A: Not yet, but webhook support is planned. Currently: ntfy.sh, email (planned).

**Q: Why must I wait 60 minutes between checks?**  
A: To respect the service and avoid overload. You can change this in Settings (minimum 5 minutes).

---

## Support

For issues or questions:
- Check the troubleshooting section above
- Review dashboard logs: `docker-compose logs -f appointment-checker`
- Run a test check: `docker-compose run --rm appointment-checker python check_appointments.py --once`
