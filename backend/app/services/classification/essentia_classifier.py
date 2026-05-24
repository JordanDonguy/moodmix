"""Audio classification via Essentia + TensorFlow.

Encapsulates the full inference chain — two backbones (Effnet-Discogs and
MusiCNN), all classifier heads (genre / mood / voice / danceability / etc.),
the A/V regression heads, and classic DSP features (BPM / key / centroid).

Designed to be the single audio-analysis dependency of
``ClassificationService`` — the service does the DB work, this class does
the audio work. Mockable in unit tests by swapping the instance.

Runtime notes
-------------
- ``essentia-tensorflow`` ships linux/amd64 wheels only. On Apple Silicon
  hosts this class can only be instantiated inside the Docker image —
  hence the lazy import in ``__init__``: the module stays importable
  everywhere, so the rest of the app can reference it for typing /
  dependency wiring without forcing essentia onto every dev machine.
- Type checking sees the API via ``backend/typings/essentia/standard.pyi``;
  the runtime import only happens when the class is actually instantiated.
- Model files are loaded once per instance and reused across ``classify``
  calls. TensorFlow predictor construction is multi-hundred-millisecond
  work; reusing the instance is what makes per-track classification fast.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

EFFNET_BACKBONE_FILE = "discogs-effnet-bs64-1.pb"
MUSICNN_BACKBONE_FILE = "msd-musicnn-1.pb"
CLASSIFIER_VERSION = "v0.1-essentia-effnet"

# Multi-label tag-soup heads on the cached Effnet embedding.
TAG_HEADS: dict[str, str] = {
    "genre": "genre_discogs400-discogs-effnet-1",
    "mood_theme": "mtg_jamendo_moodtheme-discogs-effnet-1",
}

# Binary / multi-class probability heads on the Effnet embedding.
BINARY_HEADS: dict[str, str] = {
    "voice_instrumental": "voice_instrumental-discogs-effnet-1",
    "danceability": "danceability-discogs-effnet-1",
    "mood_happy": "mood_happy-discogs-effnet-1",
    "mood_sad": "mood_sad-discogs-effnet-1",
    "mood_aggressive": "mood_aggressive-discogs-effnet-1",
    "mood_relaxed": "mood_relaxed-discogs-effnet-1",
    "mood_party": "mood_party-discogs-effnet-1",
    "mood_electronic": "mood_electronic-discogs-effnet-1",
    "mood_acoustic": "mood_acoustic-discogs-effnet-1",
    "acoustic_electronic": "nsynth_acoustic_electronic-discogs-effnet-1",
    "bright_dark": "nsynth_bright_dark-discogs-effnet-1",
    "timbre": "timbre-discogs-effnet-1",
    "engagement": "engagement_3c-discogs-effnet-1",
    "approachability": "approachability_3c-discogs-effnet-1",
}

# Valence / arousal regressors — ride the MusiCNN backbone, output on a
# DEAM-style 1-9 scale.
REGRESSION_HEADS: dict[str, str] = {
    "av_deam": "deam-msd-musicnn-2",
    "av_emomusic": "emomusic-msd-musicnn-2",
    "av_muse": "muse-msd-musicnn-2",
}


def top_k(
    probs: np.ndarray, labels: list[str], k: int,
) -> list[tuple[str, float]]:
    """Mean-pool per-frame probabilities, return the k highest tags."""
    mean = probs.mean(axis=0)
    idx = np.argsort(-mean)[:k]
    return [(labels[i], float(mean[i])) for i in idx]


class EssentiaClassifier:
    """Stateful Essentia + TensorFlow audio classifier.

    Construct once per process (model loading is expensive), call
    :meth:`classify` per audio file.
    """

    def __init__(self, models_dir: Path) -> None:
        # Lazy import so this module can be imported on machines without
        # essentia-tensorflow installed (Apple Silicon dev, CI, etc.).
        # Types come from backend/typings/essentia/standard.pyi; the
        # `reportMissingModuleSource` ignore acknowledges that the runtime
        # package is intentionally Docker-only.
        from essentia.standard import (  # pyright: ignore[reportMissingModuleSource]
            Centroid,
            FrameGenerator,
            KeyExtractor,
            Loudness,
            MonoLoader,
            RhythmExtractor2013,
            Spectrum,
            TensorflowPredict2D,
            TensorflowPredictEffnetDiscogs,
            TensorflowPredictMusiCNN,
            Windowing,
        )

        self.models_dir = models_dir
        self._classifier_version = CLASSIFIER_VERSION

        # Hold algorithm classes so per-track calls don't re-import the module.
        self._MonoLoader = MonoLoader
        self._KeyExtractor = KeyExtractor
        self._Loudness = Loudness
        self._RhythmExtractor2013 = RhythmExtractor2013
        self._Windowing = Windowing
        self._Spectrum = Spectrum
        self._Centroid = Centroid
        self._FrameGenerator = FrameGenerator
        self._TensorflowPredict2D = TensorflowPredict2D

        # Backbone predictor instances — loaded once, reused per track.
        # These are the expensive ones (a few hundred MB of TF graph each).
        self._effnet_backbone = TensorflowPredictEffnetDiscogs(
            graphFilename=str(self.models_dir / EFFNET_BACKBONE_FILE),
            output="PartitionedCall:1",
        )
        self._musicnn_backbone = TensorflowPredictMusiCNN(
            graphFilename=str(self.models_dir / MUSICNN_BACKBONE_FILE),
            output="model/dense/BiasAdd",
        )

        # Head predictor instances — small linear layers on the cached
        # embedding. Loaded eagerly so per-track latency is just inference.
        self._tag_heads = {
            name: self._build_head(stem) for name, stem in TAG_HEADS.items()
        }
        self._binary_heads = {
            name: self._build_head(stem) for name, stem in BINARY_HEADS.items()
        }
        self._regression_heads = {
            name: self._build_head(stem) for name, stem in REGRESSION_HEADS.items()
        }

    @property
    def classifier_version(self) -> str:
        """Version string to stamp into ``tracks.classifier_version``."""
        return self._classifier_version

    def classify(self, audio_path: Path) -> tuple[dict[str, Any], list[float]]:
        """Run the full chain on a single audio file.

        Returns ``(features, embedding)``:

        - ``features`` — JSON-serializable dict matching the schema of the
          ``tracks.features`` JSONB column. Includes raw classifier
          outputs, A/V regressions, BPM, key, spectral centroid, etc.
        - ``embedding`` — mean-pooled Effnet-Discogs vector (1280-d) ready
          for ``tracks.embedding`` (pgvector).
        """
        # Effnet expects 16 kHz mono; DSP wants 44.1 kHz.
        audio_16k = self._MonoLoader(
            filename=str(audio_path), sampleRate=16000, resampleQuality=4,
        )()
        audio_44k = self._MonoLoader(
            filename=str(audio_path), sampleRate=44100,
        )()

        # Compute both backbone embeddings once.
        effnet_embeddings = self._effnet_backbone(audio_16k)
        musicnn_embeddings = self._musicnn_backbone(audio_16k)

        # Fan out each head on its matching backbone.
        tags = {
            name: top_k(
                predictor(effnet_embeddings), self._labels_for(TAG_HEADS[name]),
                k=8,
            )
            for name, predictor in self._tag_heads.items()
        }
        binary = {
            name: dict(zip(
                self._labels_for(BINARY_HEADS[name]),
                predictor(effnet_embeddings).mean(axis=0).tolist(),
            ))
            for name, predictor in self._binary_heads.items()
        }
        regression = {
            name: dict(zip(
                self._labels_for(REGRESSION_HEADS[name]),
                predictor(musicnn_embeddings).mean(axis=0).tolist(),
            ))
            for name, predictor in self._regression_heads.items()
        }

        # Classic DSP.
        bpm, _beats, beats_conf, _, _ = self._RhythmExtractor2013(
            method="multifeature",
        )(audio_44k)
        key, scale, key_strength = self._KeyExtractor()(audio_44k)
        loudness = self._Loudness()(audio_44k)
        centroid_hz, centroid_norm = self._spectral_centroid(audio_44k)

        features: dict[str, Any] = {
            "tags": tags,
            "binary": binary,
            "regression": regression,
            "bpm": float(bpm),
            "bpm_confidence": float(beats_conf),
            "key": f"{key} {scale}",
            "scale": scale,
            "key_strength": float(key_strength),
            "loudness": float(loudness),
            "spectral_centroid_hz": centroid_hz,
            "spectral_centroid_norm": centroid_norm,
        }

        # Mean-pool per-frame Effnet embeddings into a single 1280-d vector.
        embedding: list[float] = effnet_embeddings.mean(axis=0).tolist()

        return features, embedding

    # ---------- internal helpers ----------

    def _build_head(self, stem: str) -> Any:
        input_name, output_name = self._tensor_names(stem)
        return self._TensorflowPredict2D(
            graphFilename=str(self.models_dir / f"{stem}.pb"),
            input=input_name,
            output=output_name,
        )

    def _load_metadata(self, stem: str) -> dict[str, Any]:
        with (self.models_dir / f"{stem}.json").open() as f:
            data: dict[str, Any] = json.load(f)
            return data

    def _labels_for(self, stem: str) -> list[str]:
        classes: list[str] = self._load_metadata(stem)["classes"]
        return classes

    def _tensor_names(self, stem: str) -> tuple[str, str]:
        """Return ``(input_name, output_name)`` from the model's schema.

        Different MTG heads were exported with different naming conventions
        (``serving_default_*`` vs. ``model/*``), so we read the schema rather
        than hardcoding. The first output marked ``output_purpose:
        predictions`` is the right one — others (e.g. penultimate layer) are
        extras.
        """
        schema = self._load_metadata(stem)["schema"]
        input_name: str = schema["inputs"][0]["name"]
        outputs: list[dict[str, Any]] = schema["outputs"]
        prediction = next(
            (o for o in outputs if o.get("output_purpose") == "predictions"),
            outputs[0],
        )
        return input_name, str(prediction["name"])

    def _spectral_centroid(self, audio_44k: np.ndarray) -> tuple[float, float]:
        """Per-frame STFT centroid, mean-pooled and normalized.

        Returns ``(raw_hz, normalized_0_1)``. Normalization is over a
        music-typical range (500-4000 Hz, clamped) so it can drop straight
        into the mood-vector formula.
        """
        window = self._Windowing(type="hann")
        spectrum = self._Spectrum()
        centroid_op = self._Centroid(range=22050.0)  # Nyquist @ 44.1k
        frames = self._FrameGenerator(
            audio_44k, frameSize=2048, hopSize=1024,
        )
        centroids = [
            centroid_op(spectrum(window(frame))) for frame in frames
        ]
        raw_hz = float(np.mean(centroids)) if centroids else 0.0
        normalized = float(np.clip((raw_hz - 500.0) / 3500.0, 0.0, 1.0))
        return raw_hz, normalized
