from datetime import datetime, timezone


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code

    def to_dict(self) -> dict[str, str | int]:
        return {
            "error": self.message,
            "status": self.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class MixNotFoundException(AppException):
    def __init__(self, mix_id: str = ""):
        super().__init__(f"Mix not found: {mix_id}" if mix_id else "Mix not found", 404)


class ChannelAlreadyExistsException(AppException):
    def __init__(self, channel_id: str = ""):
        super().__init__(f"Channel already exists: {channel_id}" if channel_id else "Channel already exists", 409)


class ArtistAlreadyExistsException(AppException):
    def __init__(self, deezer_id: str = ""):
        msg = (
            f"Artist already exists with deezer_id={deezer_id}"
            if deezer_id else "Artist already exists"
        )
        super().__init__(msg, 409)


class ArtistNotFoundException(AppException):
    def __init__(self, identifier: str = ""):
        msg = f"Artist not found: {identifier}" if identifier else "Artist not found"
        super().__init__(msg, 404)


class RateLimitExceededException(AppException):
    def __init__(self):
        super().__init__("Rate limit exceeded. Please try again later.", 429)


class ClassificationError(AppException):
    def __init__(self, detail: str = ""):
        super().__init__(f"Classification failed: {detail}" if detail else "Classification failed", 500)


class ExternalAPIError(AppException):
    def __init__(self, service: str = "", detail: str = ""):
        msg = f"External API error ({service}): {detail}" if service else "External API error"
        super().__init__(msg, 502)


class InvalidCredentialsError(AppException):
    """Raised for malformed/invalid tokens or unknown users."""

    def __init__(self, detail: str = ""):
        msg = f"Invalid credentials: {detail}" if detail else "Invalid credentials"
        super().__init__(msg, 401)


class TokenExpiredError(AppException):
    """Raised when an access or refresh token has expired."""

    def __init__(self) -> None:
        super().__init__("Token expired", 401)


class RefreshReuseError(AppException):
    """Raised when a refresh token that has already been rotated is presented again.

    Indicates a possibly stolen token. Callers should revoke the entire token
    family in response.
    """

    def __init__(self) -> None:
        super().__init__("Refresh token reuse detected", 401)
