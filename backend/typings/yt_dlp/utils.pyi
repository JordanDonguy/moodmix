"""yt-dlp's error classes — typed as plain Exception subclasses."""


class DownloadError(Exception):
    def __init__(self, msg: str = ...) -> None: ...


class ExtractorError(Exception):
    def __init__(self, msg: str = ...) -> None: ...
