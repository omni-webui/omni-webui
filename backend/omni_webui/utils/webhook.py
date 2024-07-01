import json

import requests
from loguru import logger

from omni_webui import __version__
from omni_webui.config import settings


def post_webhook(url: str, message: str, event_data: dict) -> bool:
    try:
        payload = {}

        # Slack and Google Chat Webhooks
        if "https://hooks.slack.com" in url or "https://chat.googleapis.com" in url:
            payload["text"] = message
        # Discord Webhooks
        elif "https://discord.com/api/webhooks" in url:
            payload["content"] = message
        # Microsoft Teams Webhooks
        elif "webhook.office.com" in url:
            action = event_data.get("action", "undefined")
            facts = [
                {"name": name, "value": value}
                for name, value in json.loads(event_data.get("user", {})).items()
            ]
            payload: dict[str, str | dict[str, str | bool | list[dict[str, str]]]] = {  # type: ignore
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "0076D7",
                "summary": message,
                "sections": [
                    {
                        "activityTitle": message,
                        "activitySubtitle": f"{settings.name} ({__version__}) - {action}",
                        "activityImage": settings.favicon_url,
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
