"""Discord webhook notifications manager."""

import json
import urllib.request
import urllib.error
from typing import Dict, Any


class DiscordNotifier:
    """Delivers real-time status and alert notifications to Discord channel webhooks."""

    def __init__(self, rules: Dict[str, Any]) -> None:
        self.webhook_url = rules.get("security.discord_webhook", "").strip()
        self.enabled = bool(self.webhook_url)

    def send_notification(self, message: str, level: str = "INFO") -> bool:
        """Post a styled alert message to the Discord webhook."""
        if not self.enabled or not self.webhook_url:
            return False

        # Set color markers based on severity levels
        color = 0x3498db  # Blue for INFO
        if level == "WARNING":
            color = 0xf1c40f  # Yellow
        elif level == "CRITICAL" or level == "ERROR":
            color = 0xe74c3c  # Red

        payload = {
            "embeds": [
                {
                    "title": f"Midgard Bot Alert — [{level}]",
                    "description": message,
                    "color": color,
                    "footer": {"text": "Project Midgard Sentinel Protection"},
                }
            ]
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "MidgardStudio/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5.0) as response:
                return response.status in (200, 204)
        except urllib.error.URLError:
            # Silence network request failures to prevent blocking main thread
            return False
        except Exception:
            return False
