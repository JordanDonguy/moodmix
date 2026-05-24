"""Type stubs for the bits of yt-dlp we use directly.

yt-dlp's bundled stubs use TypedDicts (``_Params``, ``_InfoDict``) that
flag plain dicts as incompatible even when they're structurally fine,
and don't declare that ``extract_info`` can return ``None`` in practice
(with ``ignoreerrors=True``). This minimal override gives us clean
typing for our actual usage in ``app/services/streaming/link_finder.py``.

Extend as the project's yt-dlp surface grows.
"""

from types import TracebackType
from typing import Any

from . import utils as utils


class YoutubeDL:
    def __init__(self, params: dict[str, Any] | None = ...) -> None: ...

    def __enter__(self) -> YoutubeDL: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    def extract_info(
        self,
        url: str,
        download: bool = ...,
    ) -> dict[str, Any] | None: ...
