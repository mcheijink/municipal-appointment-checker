import sqlite3
import json
from pathlib import Path
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

import os
_data_dir = os.getenv("DATA_DIR", "/data")
DB_PATH = Path(_data_dir) / "dashboard.db"
CONFIG_PATH = Path("config.json")

SETTINGS_DEFAULTS = {
    "appointment_url": ("https://enschede.mijnafspraakmaken.nl/?product=5", "string", "URL to appointment booking page"),
    "check_interval_seconds": (3600, "number", "Base interval between checks in seconds (minimum 300)"),
    "check_interval_seconds_min": (300, "number", "Minimum allowed interval (5 minutes, protects service)"),
    "interval_jitter_fraction": (0.30, "number", "Jitter spread (0-1)"),
    "check_days_ahead": (7, "number", "Days ahead to search for slots"),
    "notification_provider": ("ntfy", "string", "Notification provider (ntfy, email, webhook)"),
    "notification_endpoint": ("", "string", "Notification endpoint URL (required for ntfy provider)"),
    "notification_auth": ("", "string", "Optional auth credentials", 1),
    "dashboard_refresh_rate_seconds": (60, "number", "UI auto-refresh rate"),
}


def init_db():
    """Initialize database and seed defaults if empty."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            type TEXT,
            description TEXT,
            is_secret INTEGER DEFAULT 0
        )
    """)

    # Seed defaults if table is empty
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        for key, data in SETTINGS_DEFAULTS.items():
            value = data[0]
            setting_type = data[1]
            description = data[2]
            is_secret = data[3] if len(data) > 3 else 0

            cursor.execute("""
                INSERT INTO settings (key, value, type, description, is_secret)
                VALUES (?, ?, ?, ?, ?)
            """, (key, str(value), setting_type, description, is_secret))
        logger.info(f"Seeded {len(SETTINGS_DEFAULTS)} default settings")

    conn.commit()
    conn.close()


def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value, converting to appropriate type."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT value, type FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return default

    value, setting_type = row
    if setting_type == "number":
        return float(value) if "." in value else int(value)
    elif setting_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    else:
        return value


def validate_check_interval(value: int) -> tuple[bool, str]:
    """Validate check_interval_seconds is within acceptable range.

    Returns: (is_valid, error_message)
    """
    min_val = get_setting("check_interval_seconds_min", 300)
    if not isinstance(value, (int, float)):
        return False, f"check_interval_seconds must be a number, got {type(value).__name__}"
    if value < min_val:
        return False, f"check_interval_seconds must be at least {min_val}s (5 minutes), got {value}"
    return True, ""


def set_setting(key: str, value: Any) -> tuple[bool, str]:
    """Set a setting value. Returns (success, message)."""
    # Validate check_interval_seconds
    if key == "check_interval_seconds":
        try:
            interval_value = int(float(value))  # handles "300.0" too
        except (ValueError, TypeError):
            msg = f"check_interval_seconds must be a number, got {type(value).__name__}"
            logger.error(msg)
            return False, msg
        is_valid, error = validate_check_interval(interval_value)
        if not is_valid:
            logger.error(f"Invalid {key}: {error}")
            return False, error

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE settings SET value = ? WHERE key = ?
        """, (str(value), key))
        conn.commit()
        success = cursor.rowcount > 0
        if not success:
            return False, f"Setting '{key}' not found"
        return True, ""
    except Exception as e:
        logger.error(f"Failed to set {key}: {e}")
        return False, str(e)
    finally:
        conn.close()


def get_all_settings() -> dict:
    """Get all settings as dict."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT key, value, type, description, is_secret FROM settings")
    settings = {}
    for row in cursor.fetchall():
        key, value, setting_type, description, is_secret = row
        if setting_type == "number":
            value = float(value) if "." in str(value) else int(value)
        elif setting_type == "boolean":
            value = value.lower() in ("true", "1", "yes")

        settings[key] = {
            "value": value,
            "type": setting_type,
            "description": description,
            "is_secret": bool(is_secret),
        }

    conn.close()
    return settings
