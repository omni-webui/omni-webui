import importlib.metadata

try:
    __version__ = importlib.metadata.version("omni_webui")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"
