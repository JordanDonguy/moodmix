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
