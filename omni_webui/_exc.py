class OmniWebUIError(Exception):
    """Base class for OmniWebUI exceptions."""

    detail: str = ""

    def __init__(self, detail: str):
        self.detail = detail


class OmniWebUIWarning(UserWarning): ...


class OmniWebUINotFoundError(OmniWebUIError):
    """Raised when a resource is not found."""


class EnvironmentVariableNotFound(OmniWebUINotFoundError):
    """Raised when an environment variable is not found."""

    def __init__(self, var_name: str) -> None:
        self.detail = f"Environment variable '{var_name}' not found."


class ModelNotFoundError(OmniWebUINotFoundError):
    """Raised when a model is not found."""

    def __init__(self, model_name: str) -> None:
        self.detail = f"Model '{model_name}' was not found."


class FileTooLargeError(OmniWebUIError):
    """Raised when the file size exceeds the limit."""

    def __init__(self, size: str) -> None:
        self.detail = f"Oops! The file you're trying to upload is too large. Please upload a file that is less than {size}."
