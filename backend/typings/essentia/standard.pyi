"""Type stubs for the essentia.standard API surface we actually use.

essentia ships no type stubs. This file declares just what
``app/services/essentia_classifier.py`` calls so Pyright can type-check
the classifier without ``# type: ignore`` / ``Any`` noise.

Extend as more algorithms are wired in.
"""

from collections.abc import Iterable

import numpy as np


class MonoLoader:
    def __init__(
        self,
        *,
        filename: str,
        sampleRate: int = ...,
        resampleQuality: int = ...,
    ) -> None: ...
    def __call__(self) -> np.ndarray: ...


class RhythmExtractor2013:
    def __init__(self, *, method: str = ...) -> None: ...
    def __call__(
        self, audio: np.ndarray,
    ) -> tuple[float, np.ndarray, float, np.ndarray, np.ndarray]: ...


class KeyExtractor:
    def __init__(self) -> None: ...
    def __call__(self, audio: np.ndarray) -> tuple[str, str, float]: ...


class Loudness:
    def __init__(self) -> None: ...
    def __call__(self, audio: np.ndarray) -> float: ...


class Windowing:
    def __init__(self, *, type: str = ...) -> None: ...
    def __call__(self, frame: np.ndarray) -> np.ndarray: ...


class Spectrum:
    def __init__(self) -> None: ...
    def __call__(self, frame: np.ndarray) -> np.ndarray: ...


class Centroid:
    def __init__(self, *, range: float = ...) -> None: ...
    def __call__(self, spectrum: np.ndarray) -> float: ...


def FrameGenerator(
    audio: np.ndarray,
    *,
    frameSize: int = ...,
    hopSize: int = ...,
) -> Iterable[np.ndarray]: ...


class TensorflowPredict2D:
    def __init__(
        self,
        *,
        graphFilename: str,
        input: str = ...,
        output: str = ...,
    ) -> None: ...
    def __call__(self, embeddings: np.ndarray) -> np.ndarray: ...


class TensorflowPredictEffnetDiscogs:
    def __init__(
        self,
        *,
        graphFilename: str,
        output: str = ...,
    ) -> None: ...
    def __call__(self, audio: np.ndarray) -> np.ndarray: ...


class TensorflowPredictMusiCNN:
    def __init__(
        self,
        *,
        graphFilename: str,
        output: str = ...,
    ) -> None: ...
    def __call__(self, audio: np.ndarray) -> np.ndarray: ...
