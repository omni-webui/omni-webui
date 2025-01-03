import importlib.metadata
import importlib.util
import logging
from functools import lru_cache
from pathlib import Path

from platformdirs import PlatformDirs

try:
    __version__ = importlib.metadata.version("omni_webui")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


@lru_cache
def get_package_dir(name: str) -> Path:
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise ImportError(f"{name} module not found")
    if spec.submodule_search_locations is None:
        raise ValueError(f"{name} module not installed correctly")
    return Path(spec.submodule_search_locations[0])


APP_NAME = "omni-webui"
D = PlatformDirs(appname=APP_NAME)
