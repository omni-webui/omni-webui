import hashlib
import re
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, TypedDict

from loguru import logger


def get_gravatar_url(email):
    # Trim leading and trailing whitespace from
    # an email address and force all characters
    # to lower case
    address = str(email).strip().lower()

    # Create a SHA256 hash of the final string
    hash_object = hashlib.sha256(address.encode())
    hash_hex = hash_object.hexdigest()

    # Grab the actual image URL
    return f"https://www.gravatar.com/avatar/{hash_hex}?d=mp"


def calculate_sha256(file):
    sha256 = hashlib.sha256()
    # Read the file in chunks to efficiently handle large files
    for chunk in iter(lambda: file.read(8192), b""):
        sha256.update(chunk)
    return sha256.hexdigest()


def calculate_sha256_string(string):
    # Create a new SHA-256 hash object
    sha256_hash = hashlib.sha256()
    # Update the hash object with the bytes of the input string
    sha256_hash.update(string.encode("utf-8"))
    # Get the hexadecimal representation of the hash
    hashed_string = sha256_hash.hexdigest()
    return hashed_string


def validate_email_format(email: str) -> bool:
    if email.endswith("@localhost"):
        return True

    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))


def sanitize_filename(file_name):
    # Convert to lowercase
    lower_case_file_name = file_name.lower()

    # Remove special characters using regular expression
    sanitized_file_name = re.sub(r"[^\w\s]", "", lower_case_file_name)

    # Replace spaces with dashes
    final_file_name = re.sub(r"\s+", "-", sanitized_file_name)

    return final_file_name


def extract_folders_after_data_docs(path):
    # Convert the path to a Path object if it's not already
    path = Path(path)

    # Extract parts of the path
    parts = path.parts

    # Find the index of '/data/docs' in the path
    try:
        index_data_docs = parts.index("data") + 1
        index_docs = parts.index("docs", index_data_docs) + 1
    except ValueError:
        return []

    # Exclude the filename and accumulate folder names
    tags = []

    folders = parts[index_docs:-1]
    for idx, part in enumerate(folders):
        tags.append("/".join(folders[: idx + 1]))

    return tags


def parse_duration(duration: str) -> timedelta | None:
    if duration == "-1" or duration == "0":
        return None

    # Regular expression to find number and unit pairs
    number_pattern = r"(?P<{}>-?\d+(?:\.\d+)?)"
    pattern = "".join(
        f"(?:{number_pattern.format(unit)}{unit[0]})?"
        for unit in ("weeks", "days", "hours", "minutes", "seconds")
    )
    pattern += f"(?:{number_pattern.format('milliseconds')}ms)?"
    mo = re.match(f"^{pattern}$", duration)
    if not mo:
        raise ValueError("Invalid duration string")
    return timedelta(
        **{
            key: float(value)
            for key, value in mo.groupdict().items()
            if value is not None
        }
    )


def parse_ollama_modelfile(model_text: str):
    parameters_meta: dict[str, type] = {
        "mirostat": int,
        "mirostat_eta": float,
        "mirostat_tau": float,
        "num_ctx": int,
        "repeat_last_n": int,
        "repeat_penalty": float,
        "temperature": float,
        "seed": int,
        "tfs_z": float,
        "num_predict": int,
        "top_k": int,
        "top_p": float,
        "num_keep": int,
        "typical_p": float,
        "presence_penalty": float,
        "frequency_penalty": float,
        "penalize_newline": bool,
        "numa": bool,
        "num_batch": int,
        "num_gpu": int,
        "main_gpu": int,
        "low_vram": bool,
        "f16_kv": bool,
        "vocab_only": bool,
        "use_mmap": bool,
        "use_mlock": bool,
        "num_thread": int,
    }

    class Data(TypedDict):
        base_model_id: Optional[str]
        params: dict[str, Any]

    data: Data = {"base_model_id": None, "params": {}}

    # Parse base model
    base_model_match = re.search(
        r"^FROM\s+(\w+)", model_text, re.MULTILINE | re.IGNORECASE
    )
    if base_model_match:
        data["base_model_id"] = base_model_match.group(1)

    # Parse template
    template_match = re.search(
        r'TEMPLATE\s+"""(.+?)"""', model_text, re.DOTALL | re.IGNORECASE
    )
    if template_match:
        data["params"] = {"template": template_match.group(1).strip()}

    # Parse stops
    stops = re.findall(r'PARAMETER stop "(.*?)"', model_text, re.IGNORECASE)
    if stops:
        data["params"]["stop"] = stops

    # Parse other parameters from the provided list
    for param, param_type in parameters_meta.items():
        param_match = re.search(rf"PARAMETER {param} (.+)", model_text, re.IGNORECASE)
        if param_match:
            value = param_match.group(1)

            try:
                if param_type is bool:
                    value = value.lower() == "true"
                else:
                    value = param_type(value)
            except Exception as e:
                logger.exception(e)
                continue

            data["params"][param] = value

    # Parse adapter
    adapter_match = re.search(r"ADAPTER (.+)", model_text, re.IGNORECASE)
    if adapter_match:
        data["params"]["adapter"] = adapter_match.group(1)

    # Parse system description
    system_desc_match = re.search(
        r'SYSTEM\s+"""(.+?)"""', model_text, re.DOTALL | re.IGNORECASE
    )
    if system_desc_match:
        data["params"]["system"] = system_desc_match.group(1).strip()

    # Parse messages
    messages = []
    message_matches = re.findall(r"MESSAGE (\w+) (.+)", model_text, re.IGNORECASE)
    for role, content in message_matches:
        messages.append({"role": role, "content": content})

    if messages:
        data["params"]["messages"] = messages

    return data
