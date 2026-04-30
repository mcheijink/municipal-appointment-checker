#!/usr/bin/env python3
"""
Check for available appointments at Gemeente Enschede within the next week.
Navigates the Aurelia SPA with Playwright and intercepts the availability API response.
Sends an NTFY notification when slots open up within CHECK_DAYS_AHEAD days.
"""

import asyncio
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")

import httpx
from playwright.async_api import async_playwright
from database import init_db, get_setting
from notification import send_notification

# ---------------------------------------------------------------------------
# Configuration
# Most settings come from database; these are static or env-only
# ---------------------------------------------------------------------------
APPOINTMENT_URL = None  # Will be read from database in main()
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8800/")
NTFY_URL = None  # Will be read from database in main()
CHECK_INTERVAL = None  # Will be read from database in main()
CHECK_DAYS_AHEAD = None  # Will be read from database in main()
SCREENSHOT_ON_ERROR = os.getenv("SCREENSHOT_ON_ERROR", "true").lower() == "true"
SCREENSHOT_PATH = os.getenv("SCREENSHOT_PATH", "/tmp/enschede_debug.png")
SLOT_HISTORY_FILE = "/data/slot_history.jsonl"  # Not configurable; fixed path
INTERVAL_JITTER = None  # Will be read from database in main()

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def human_wait(page, base_ms: int, jitter: float = 0.40) -> None:
    """Sleep for base_ms ± jitter fraction to mimic human pacing."""
    lo = int(base_ms * (1 - jitter))
    hi = int(base_ms * (1 + jitter))
    await page.wait_for_timeout(random.randint(lo, hi))


def get_last_slots() -> list[str] | None:
    """Get the slots from the last history entry, or None if no history exists."""
    try:
        path = Path(SLOT_HISTORY_FILE)
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as fh:
            last_line = None
            for line in fh:
                last_line = line

            if last_line:
                record = json.loads(last_line)
                return record.get("slots", [])
    except Exception as exc:
        log.warning("Could not read last slot history: %s", exc)

    return None


def record_slot_history(slots: list[str]) -> bool:
    """Append slots to history only if they changed from the last check.

    Returns True if recorded (slots changed), False if no change.
    """
    # Check if slots changed
    last_slots = get_last_slots()
    if last_slots is not None:
        if set(slots) == set(last_slots):
            log.debug("Slots unchanged, skipping history record")
            return False

    record = {
        "checked_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "slots": slots,
    }
    try:
        path = Path(SLOT_HISTORY_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        log.debug("Slot history written to %s", SLOT_HISTORY_FILE)
        return True
    except Exception as exc:
        log.warning("Could not write slot history: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
async def send_notification_async(provider: str, endpoint: str, message: str, title: str = "Appointment Available") -> bool:
    """Send notification via dispatcher (wrapper for async context)."""
    return send_notification(provider, endpoint, message, title)


# ---------------------------------------------------------------------------
# Appointment fetching (exported for use by test endpoints)
# ---------------------------------------------------------------------------
async def fetch_slots(url: str) -> list[str]:
    """
    Fetch available slots from Gemeente Enschede booking page.

    Navigates the booking page with Playwright, intercepts API responses,
    and extracts available appointment slots.

    Args:
        url: URL of the booking page (e.g., https://enschede.mijnafspraakmaken.nl/?product=5)

    Returns:
        List of slot datetime strings in ISO format (e.g., ["2026-04-22T10:30:00", ...]),
        or empty list if none found or on error.
    """
    raw_times: list[str] = []   # all datetime strings collected from API

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="nl-NL",
            timezone_id="Europe/Amsterdam",
        )
        page = await context.new_page()

        # ------------------------------------------------------------------ #
        # Intercept API responses — only harvest from availability endpoints  #
        # ------------------------------------------------------------------ #
        AVAILABILITY_KEYWORDS = ("availabletimelist", "firstavailableappointmenttime")

        async def on_response(response):
            url_str = response.url
            url_lower = url_str.lower()
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            if not any(kw in url_lower for kw in AVAILABILITY_KEYWORDS):
                return
            try:
                body = await response.json()
            except Exception:
                return

            log.debug("Availability API ← %s  (%s)", url_str, str(body)[:200])
            _harvest_times(body, raw_times)

        page.on("response", on_response)

        try:
            # ---------------------------------------------------------------- #
            # 1. Load the page                                                  #
            # ---------------------------------------------------------------- #
            log.info("Loading %s", url)
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            await human_wait(page, 3_000)

            # ---------------------------------------------------------------- #
            # 2. Dismiss cookie / privacy banner if present                     #
            # ---------------------------------------------------------------- #
            for sel in [
                "button:has-text('Akkoord')",
                "button:has-text('Accepteer')",
                "button:has-text('Sluiten')",
                "#cookieConsentAccept",
                ".cookie-accept",
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1_500):
                        await btn.click()
                        await human_wait(page, 800)
                        log.debug("Dismissed cookie banner via: %s", sel)
                        break
                except Exception:
                    pass

            # ---------------------------------------------------------------- #
            # 3. Walk through booking steps until we see a calendar             #
            #    or until the availability API call fires (step 2 triggers it)  #
            # ---------------------------------------------------------------- #
            CALENDAR_SELECTORS = [
                ".datepicker",
                "[class*='calendar']",
                "[class*='datepicker']",
                "table.month",
                "[data-date]",
            ]

            NEXT_BUTTON_SELECTORS = [
                "button:has-text('Volgende')",
                "button:has-text('Verder')",
                "button:has-text('Ga verder')",
                "a:has-text('Volgende')",
                "button[type='submit']:visible",
                "button.btn-primary:visible",
            ]

            for step in range(8):
                # Stop as soon as we have availability data from the API
                if raw_times:
                    log.info("Availability data received after step %d, stopping navigation", step)
                    break

                # Check if calendar is visible
                for cal_sel in CALENDAR_SELECTORS:
                    if await page.locator(cal_sel).count() > 0:
                        log.info("Calendar found at step %d (selector: %s)", step, cal_sel)
                        # Give it extra time to load availability API
                        await human_wait(page, 3_000)
                        break

                if raw_times:
                    break

                # Advance to next step
                clicked = False
                for sel in NEXT_BUTTON_SELECTORS:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=1_000) and await btn.is_enabled(timeout=500):
                            log.info("Step %d → clicking '%s'", step + 1, sel)
                            await btn.click()
                            await human_wait(page, 2_000)
                            clicked = True
                            break
                    except Exception:
                        pass

                if not clicked:
                    log.debug("No next button at step %d, stopping", step)
                    break

            # Final settle in case last click triggered delayed API call
            if not raw_times:
                await human_wait(page, 3_000)

        except Exception as exc:
            log.error("Error navigating page: %s", exc, exc_info=True)
            if SCREENSHOT_ON_ERROR:
                try:
                    await page.screenshot(path=SCREENSHOT_PATH, full_page=True)
                    log.info("Debug screenshot saved to %s", SCREENSHOT_PATH)
                except Exception:
                    pass
        finally:
            await browser.close()

    # De-duplicate and sort
    unique = sorted(set(raw_times))
    return unique


# ---------------------------------------------------------------------------
# Appointment checker
# ---------------------------------------------------------------------------
async def check_appointments() -> tuple[list[str], list[str]]:
    """
    Navigate the booking page, walk through the flow, and return:
      (nearby_slots, all_slots)
    where nearby_slots are ISO datetime strings within CHECK_DAYS_AHEAD days,
    and all_slots are every available slot found.

    The JCC API base URL is discovered at runtime from appsettings.json.
    Key response patterns intercepted:
      - availabletimelist → data.availableTimesList: ["2026-04-24T08:35:00", ...]
      - firstAvailableAppointmentTime → data: [{"firstAvailableTime": "..."}]
    """
    today = datetime.now(TZ).date()
    cutoff = today + timedelta(days=CHECK_DAYS_AHEAD)

    all_slots = await fetch_slots(APPOINTMENT_URL)
    nearby = [t for t in all_slots if today <= _parse_dt(t).date() <= cutoff]
    return nearby, all_slots


def _parse_dt(value: str) -> datetime:
    """Parse an ISO-like datetime string."""
    return datetime.fromisoformat(value[:19])


def _harvest_times(body, out: list[str]) -> None:
    """
    Recursively pull datetime strings out of a JCC API response body.

    Handles:
      - data.availableTimesList: ["2026-04-24T08:35:00", ...]
      - data[].firstAvailableTime: "2026-04-24T08:35:00"
      - Generic dicts with startDateTime / date / startTime / startDate keys
    """
    if isinstance(body, list):
        for item in body:
            _harvest_times(item, out)
    elif isinstance(body, dict):
        # Pattern: {"data": {"availableTimesList": [...]}, "success": true}
        if "availableTimesList" in body:
            for t in body["availableTimesList"]:
                if isinstance(t, str) and "T" in t:
                    out.append(t)
            return

        # Pattern: {"data": [{"locationId": ..., "firstAvailableTime": "..."}], ...}
        if "firstAvailableTime" in body:
            t = body["firstAvailableTime"]
            if isinstance(t, str) and "T" in t:
                out.append(t)
            return

        # Generic slot-like dict
        for key in ("startDateTime", "startTime", "startDate", "date"):
            if key in body:
                v = body[key]
                if isinstance(v, str) and len(v) >= 10:
                    out.append(v)
                return

        # Recurse into nested values
        for v in body.values():
            if isinstance(v, (list, dict)):
                _harvest_times(v, out)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def main() -> None:
    global APPOINTMENT_URL, NTFY_URL, CHECK_INTERVAL, CHECK_DAYS_AHEAD, INTERVAL_JITTER

    # Initialize database and load settings
    init_db()
    APPOINTMENT_URL = get_setting("appointment_url", "")
    NTFY_URL = get_setting("notification_endpoint", "")
    CHECK_INTERVAL = get_setting("check_interval_seconds", 3600)
    CHECK_DAYS_AHEAD = get_setting("check_days_ahead", 7)
    INTERVAL_JITTER = get_setting("interval_jitter_fraction", 0.30)

    once = "--once" in sys.argv

    if once:
        log.info("Running single check (--once mode)")
    else:
        log.info(
            "Appointment checker started — interval %ds, window %d days",
            CHECK_INTERVAL,
            CHECK_DAYS_AHEAD,
        )

    while True:
        log.info("Checking for available appointments in the next %d days…", CHECK_DAYS_AHEAD)
        try:
            nearby, all_slots = await check_appointments()
        except Exception as exc:
            log.error("check_appointments() raised: %s", exc, exc_info=True)
            nearby, all_slots = [], []

        # Record history and only send notification if slots changed
        slots_changed = record_slot_history(all_slots)

        if all_slots:
            first = all_slots[0]
            log.info("First available slot overall: %s", first)

        # Send notification only if slots changed AND there are nearby slots
        if slots_changed and nearby:
            log.info("Found %d slot(s) within %d days: %s", len(nearby), CHECK_DAYS_AHEAD, nearby[:5])
            msg = (
                f"Er {'is' if len(nearby) == 1 else 'zijn'} {len(nearby)} "
                f"afspraakslot{'s' if len(nearby) > 1 else ''} beschikbaar "
                f"in de komende {CHECK_DAYS_AHEAD} dagen!\n\n"
                f"Eerste: {nearby[0]}\n\n"
                f"{APPOINTMENT_URL}"
            )
            provider = get_setting("notification_provider", "ntfy")
            endpoint = get_setting("notification_endpoint", "")
            title = "Afspraak beschikbaar - Enschede"
            if await send_notification_async(provider, endpoint, msg, title):
                log.info("Notification sent via %s", provider)
            else:
                log.warning("Failed to send %s notification", provider)
        elif not slots_changed:
            log.debug("Slots unchanged, skipping notification")
        else:
            if all_slots:
                log.info(
                    "No slots in the next %d days. First available: %s",
                    CHECK_DAYS_AHEAD,
                    all_slots[0],
                )
            else:
                log.info("No available slots found at all.")

        if once:
            break

        lo = CHECK_INTERVAL * (1 - INTERVAL_JITTER)
        hi = CHECK_INTERVAL * (1 + INTERVAL_JITTER)
        sleep_secs = random.uniform(lo, hi)
        log.info("Sleeping %.0f seconds until next check (±%.0f%% jitter)…", sleep_secs, INTERVAL_JITTER * 100)
        await asyncio.sleep(sleep_secs)


if __name__ == "__main__":
    asyncio.run(main())
