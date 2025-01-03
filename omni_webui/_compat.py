"""Compatibility layer for Open WebUI"""

import re
from pathlib import Path


def save_secret_key(secret_key: str, dotenv: Path | None = None) -> None:
    """Save secret key to .env file"""
    if dotenv is None:
        dotenv = Path.cwd() / ".env"
    content = dotenv.read_text() if dotenv.exists() else ""
    if re.search(r"^OMNI_WEBUI_SECRET_KEY=\S{12,18}", content, re.MULTILINE) is None:
        content += f"\nOMNI_WEBUI_SECRET_KEY={secret_key}\n"
        dotenv.write_text(content)
