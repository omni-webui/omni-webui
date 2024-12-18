"""Compatibility layer for Open WebUI"""

import re
from pathlib import Path


def find_case_path(dir_path: Path, file_name: str, case_sensitive: bool) -> Path | None:
    """Open WebUI save webui_secret_key with leading dot, so I make a compatible function to read dot file"""
    for f in dir_path.iterdir():
        if f.name == file_name or f.name == "." + file_name:
            return f
        elif not case_sensitive and (
            f.name.lower() == file_name.lower()
            or f.name.lower() == "." + file_name.lower()
        ):
            return f
    return None


def save_secret_key(secret_key: str, dotenv: Path | None = None) -> None:
    """Save secret key to .env file"""
    if dotenv is None:
        dotenv = Path.cwd() / ".env"
    content = dotenv.read_text() if dotenv.exists() else ""
    if re.match(r"^OMNI_WEBUI_SECRET_KEY=", content, re.MULTILINE) is None:
        content += f"\nOMNI_WEBUI_SECRET_KEY={secret_key}\n"
        dotenv.write_text(content)
