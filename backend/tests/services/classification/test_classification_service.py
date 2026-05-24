"""Unit tests for ClassificationService.

EssentiaClassifier and PreviewSource are mocked; the DB layer is the
real test fixture, so we verify both behavior and persisted state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.models.artist import Artist
from app.models.track import Track
from app.services.classification.classification_service import ClassificationService

# Avoid importing AsyncSession at runtime in tests — only used as a type
# hint in fixture signatures.
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002


def _mocks(
    *,
    preview_url: str | None = "https://example.com/preview.mp3",
    features: dict[str, Any] | None = None,
    embedding: list[float] | None = None,
    classify_raises: Exception | None = None,
    download_raises: Exception | None = None,
) -> tuple[MagicMock, AsyncMock]:
    """Build EssentiaClassifier + PreviewSource mocks for a single test."""
    essentia = MagicMock()
    essentia.classifier_version = "test-v1"
    if classify_raises is not None:
        essentia.classify = MagicMock(side_effect=classify_raises)
    else:
        essentia.classify = MagicMock(
            return_value=(
                features if features is not None else {"bpm": 120},
                embedding if embedding is not None else [0.1] * 1280,
            )
        )

    preview = AsyncMock()
    preview.get_preview_url = AsyncMock(return_value=preview_url)
    if download_raises is not None:
        preview.download = AsyncMock(side_effect=download_raises)
    else:
        preview.download = AsyncMock()
    return essentia, preview


async def _make_track(
    db: AsyncSession, *, classified: bool = False,
) -> Track:
    """Insert a minimal Artist + Track for the test, return the Track."""
    artist = Artist(name="Bonobo", resolution_tier="confirmed")
    db.add(artist)
    await db.flush()
    track = Track(artist_id=artist.id, title="Kong", deezer_id="12345")
    if classified:
        track.classified_at = datetime.now(UTC)
        track.classifier_version = "old-v0"
    db.add(track)
    await db.flush()
    return track


class TestClassifyTrack:
    async def test_persists_features_and_returns_true_on_success(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        essentia, preview = _mocks(
            features={"bpm": 128, "key": "C major"},
            embedding=[0.5] * 1280,
        )
        service = ClassificationService(db, essentia, preview)

        # ACT
        result = await service.classify_track(track.id)

        # ASSERT
        assert result is True
        await db.refresh(track)
        assert track.classified_at is not None
        assert track.classifier_version == "test-v1"
        assert track.features == {"bpm": 128, "key": "C major"}
        # pgvector reads embeddings back as numpy arrays — cast to list
        # for a clean equality comparison.
        assert track.embedding is not None
        assert list(track.embedding) == [0.5] * 1280
        # mood_vector is derived from features and persisted automatically.
        # We don't assert specific values here (that's MoodVectorService's
        # test surface); just that the wiring ran end-to-end.
        assert track.mood_vector is not None
        assert len(list(track.mood_vector)) == 3

    async def test_skips_already_classified_track(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db, classified=True)
        essentia, preview = _mocks()
        service = ClassificationService(db, essentia, preview)

        # ACT
        result = await service.classify_track(track.id)

        # ASSERT
        assert result is False
        preview.get_preview_url.assert_not_called()
        essentia.classify.assert_not_called()
        # Original classifier_version untouched
        await db.refresh(track)
        assert track.classifier_version == "old-v0"

    async def test_returns_false_when_no_preview_available(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        essentia, preview = _mocks(preview_url=None)
        service = ClassificationService(db, essentia, preview)

        # ACT
        result = await service.classify_track(track.id)

        # ASSERT
        assert result is False
        essentia.classify.assert_not_called()
        await db.refresh(track)
        assert track.classified_at is None

    async def test_returns_false_when_download_fails(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        essentia, preview = _mocks(
            download_raises=httpx.HTTPStatusError(
                "404",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(404),
            ),
        )
        service = ClassificationService(db, essentia, preview)

        # ACT
        result = await service.classify_track(track.id)

        # ASSERT
        assert result is False
        essentia.classify.assert_not_called()
        await db.refresh(track)
        assert track.classified_at is None
        assert track.features is None

    async def test_returns_false_when_essentia_fails(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        track = await _make_track(db)
        essentia, preview = _mocks(classify_raises=RuntimeError("essentia crash"))
        service = ClassificationService(db, essentia, preview)

        # ACT
        result = await service.classify_track(track.id)

        # ASSERT
        assert result is False
        await db.refresh(track)
        assert track.classified_at is None
        assert track.features is None

    async def test_returns_false_when_track_not_found(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        essentia, preview = _mocks()
        service = ClassificationService(db, essentia, preview)

        # ACT
        result = await service.classify_track(uuid.uuid4())

        # ASSERT
        assert result is False
        preview.get_preview_url.assert_not_called()
        essentia.classify.assert_not_called()


class TestClassifyArtist:
    async def test_classifies_only_unclassified_tracks(
        self, db: AsyncSession,
    ) -> None:
        # ARRANGE
        artist = Artist(name="Bonobo", resolution_tier="confirmed")
        db.add(artist)
        await db.flush()
        # Two unclassified + one already classified
        t1 = Track(artist_id=artist.id, title="Aaa", deezer_id="1")
        t2 = Track(artist_id=artist.id, title="Bbb", deezer_id="2")
        t3 = Track(
            artist_id=artist.id, title="Ccc", deezer_id="3",
            classified_at=datetime.now(UTC),
            classifier_version="old-v0",
        )
        db.add_all([t1, t2, t3])
        await db.flush()
        essentia, preview = _mocks()
        service = ClassificationService(db, essentia, preview)

        # ACT
        newly_classified, attempted = await service.classify_artist(artist.id)

        # ASSERT
        assert newly_classified == 2
        assert attempted == 2
        # The pre-classified track was skipped entirely
        await db.refresh(t3)
        assert t3.classifier_version == "old-v0"
