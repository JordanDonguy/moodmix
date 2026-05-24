"""Re-derive mood_vector from features for every classified track.

Reusable maintenance script — committed long-term tool, not a one-shot.
Two main use cases:

1. **First-time backfill** — populate ``mood_vector`` on the existing
   classified catalog (the initial Essentia backfill never persisted it).
   Use ``--only-missing`` so the script only touches rows where
   ``mood_vector IS NULL``.

2. **Formula tuning sweep** — after any weight change in
   ``app/services/mood_vector.py``, re-derive every classified track so
   the catalog reflects the new formula. Default mode does this.

No Essentia, no network: just reads ``features`` JSONB, runs the pure
``derive()`` function, writes ``mood_vector``. Runs in 30-60s for ~75k
tracks against a local Postgres.

**Single-transaction** by design: every row update stays in one
transaction, committed only once at the end. Any failure (incl. Ctrl-C)
rolls back the whole pass — the catalog stays consistent with the
previous formula. Re-run safely.

Usage::

    cd backend
    # First-pass backfill of existing tracks with NULL mood_vector
    uv run python -m scripts.rederive_mood_vectors --only-missing

    # Full re-derive after tuning weights (default)
    uv run python -m scripts.rederive_mood_vectors

    # Smoke test
    uv run python -m scripts.rederive_mood_vectors --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.track import Track
from app.services.classification.mood_vector import derive

PROGRESS_EVERY = 5000
STREAM_CHUNK_SIZE = 500

log = logging.getLogger("rederive_mood_vectors")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N tracks (smoke testing).",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only re-derive rows where mood_vector IS NULL "
        "(use for first-pass backfill of existing tracks).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    stmt = select(Track).where(Track.features.is_not(None))
    if args.only_missing:
        stmt = stmt.where(Track.mood_vector.is_(None))
    if args.limit:
        stmt = stmt.limit(args.limit)
    # Stream rows so the 75k-row result doesn't all land in memory.
    stmt = stmt.execution_options(yield_per=STREAM_CHUNK_SIZE)

    async with async_session() as session:
        log.info(
            "starting re-derivation pass (only_missing=%s, limit=%s)",
            args.only_missing, args.limit,
        )
        updated = 0
        skipped = 0
        async for track in await session.stream_scalars(stmt):
            if not isinstance(track.features, dict):
                # Defensive: features should always be a dict if non-null,
                # but if a row has garbage data, skip rather than crash.
                skipped += 1
                continue
            track.mood_vector = list(derive(track.features))
            updated += 1
            if updated % PROGRESS_EVERY == 0:
                log.info("  processed %d tracks", updated)

        log.info(
            "committing %d updates in one transaction (skipped %d)...",
            updated, skipped,
        )
        await session.commit()
        log.info("done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(
            "\ninterrupted — all changes rolled back "
            "(single-transaction semantics)",
            file=sys.stderr,
        )
        sys.exit(130)
