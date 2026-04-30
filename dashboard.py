import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from database import init_db, get_all_settings, get_setting, set_setting
import httpx
from notification import send_notification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", static_url_path="/static")
SLOT_HISTORY_FILE = Path("/data/slot_history.jsonl")

init_db()


@app.route("/")
def index():
    """Serve Available Slots page."""
    return render_template("available_slots.html")


@app.route("/changelog")
def changelog():
    """Serve Change Log page."""
    return render_template("changelog.html")


@app.route("/settings")
def settings_page():
    """Serve Settings page."""
    settings = get_all_settings()
    return render_template("settings.html", settings=settings)


# Settings API
@app.route("/api/settings", methods=["GET"])
def get_settings_api():
    """Get all settings as JSON."""
    return jsonify(get_all_settings())


@app.route("/api/settings/<key>", methods=["PUT"])
def update_setting_api(key):
    """Update a single setting."""
    data = request.get_json()
    if not data or "value" not in data:
        return jsonify({"success": False, "message": "Missing value"}), 400

    success, message = set_setting(key, data["value"])
    if success:
        return jsonify({"success": True, "value": data["value"]})
    else:
        return jsonify({"success": False, "message": message}), 400


@app.route("/api/test/notification", methods=["POST"])
def test_notification():
    """Test notification provider."""
    try:
        endpoint = get_setting("notification_endpoint")
        provider = get_setting("notification_provider", "ntfy")
        test_message = f"Test notification from dashboard at {datetime.now().isoformat()}"

        if send_notification(provider, endpoint, test_message, "Test Notification"):
            return jsonify({"success": True, "message": "Notification sent successfully"})
        else:
            return jsonify({"success": False, "message": "Failed to send notification"}), 500
    except Exception as e:
        msg = "Notification test failed: {}".format(str(e))
        logger.error(msg)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/settings/notification-status")
def notification_status():
    """Return current notification provider and endpoint status."""
    provider = get_setting("notification_provider", "ntfy")
    endpoint = get_setting("notification_endpoint", "")

    status = {
        "provider": provider,
        "endpoint": endpoint,
        "is_configured": bool(endpoint),
        "warning": "Endpoint not configured" if not endpoint else None
    }
    return jsonify(status)


@app.route("/api/test/data-retrieval", methods=["POST"])
def test_data_retrieval():
    """Test fetching slots from Gemeente Enschede."""
    try:
        from check_appointments import fetch_slots
        url = get_setting("appointment_url")
        slots = asyncio.run(fetch_slots(url))
        if slots:
            msg = "Retrieved {} available slots".format(len(slots))
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": True, "message": "No slots available (site returned empty)"})
    except Exception as e:
        msg = "Data retrieval test failed: {}".format(str(e))
        logger.error(msg)
        return jsonify({"success": False, "message": "Failed to fetch: {}".format(str(e))}), 500


@app.route("/api/slot-history")
def get_slot_history():
    """Get slot history file for rendering pages."""
    if not SLOT_HISTORY_FILE.exists():
        return jsonify({"entries": []})

    entries = []
    try:
        with open(SLOT_HISTORY_FILE, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except Exception as e:
        msg = "Failed to read slot history: {}".format(str(e))
        logger.error(msg)

    return jsonify({"entries": entries})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8800, debug=False)
