import json

import requests
from loguru import logger

from omni_webui import __version__
from omni_webui.env import WEBUI_FAVICON_URL
from omni_webui.settings import SettingsDepends


def post_webhook(
    url: str, message: str, event_data: dict, settings: SettingsDepends
) -> bool:
    try:
        logger.debug(f"post_webhook: {url}, {message}, {event_data}")
        payload = {}

        # Slack and Google Chat Webhooks
        if "https://hooks.slack.com" in url or "https://chat.googleapis.com" in url:
            payload["text"] = message
        # Discord Webhooks
        elif "https://discord.com/api/webhooks" in url:
            payload["content"] = (
                message
                if len(message) < 2000
                else f"{message[: 2000 - 20]}... (truncated)"
            )
        # Microsoft Teams Webhooks
        elif "webhook.office.com" in url:
            action = event_data.get("action", "undefined")
            facts = [
                {"name": name, "value": value}
                for name, value in json.loads(event_data.get("user", {})).items()
            ]
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "0076D7",
                "summary": message,
                "sections": [
                    {
                        "activityTitle": message,
                        "activitySubtitle": f"{settings.title} ({__version__}) - {action}",
                        "activityImage": WEBUI_FAVICON_URL,
                        "facts": facts,
                        "markdown": True,
                    }
                ],
            }
        # Default Payload
        else:
            payload = {**event_data}

        logger.debug(f"payload: {payload}")
        r = requests.post(url, json=payload)
        r.raise_for_status()
        logger.debug(f"r.text: {r.text}")
        return True
    except Exception as e:
        logger.exception(e)
        return False
