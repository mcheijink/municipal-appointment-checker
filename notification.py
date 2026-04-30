import logging
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
TZ = ZoneInfo("Europe/Amsterdam")


def send_notification(provider: str, endpoint: str, message: str, title: str = "Appointment Available") -> bool:
    """Route notification based on provider setting.

    Args:
        provider: "ntfy", "email", or "webhook"
        endpoint: URL or email address (depends on provider)
        message: Notification body
        title: Notification title

    Returns: True if successful, False otherwise
    """

    if not endpoint:
        logger.error(f"Cannot send {provider} notification: endpoint is empty")
        return False

    if provider == "ntfy":
        return _send_ntfy(endpoint, message, title)
    elif provider == "email":
        logger.warning("Email provider not yet implemented")
        return False
    elif provider == "webhook":
        logger.warning("Webhook provider not yet implemented")
        return False
    else:
        logger.error(f"Unknown notification provider: {provider}")
        return False


def _send_ntfy(endpoint: str, message: str, title: str) -> bool:
    """Send notification via ntfy.sh"""
    try:
        headers = {
            "Title": title,
            "Tags": "alarm",
        }
        response = httpx.post(endpoint, data=message, headers=headers, timeout=5.0)
        if response.status_code == 200:
            logger.info(f"Sent ntfy notification to {endpoint}")
            return True
        else:
            logger.error(f"ntfy returned {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send ntfy notification: {e}")
        return False
