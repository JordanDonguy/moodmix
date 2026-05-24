"""Resolve playback URLs for every unresolved track in the catalog.

Iterates tracks where ``streaming_resolved_at IS NULL``, calling
``StreamingResolutionService.resolve_track`` for each. Rate-limit
handling: detect throttling, sleep, retry once, stop cleanly if it
persists. Re-runs pick up where previous ones left off.

Usage::

    cd backend
    uv run python -m scripts.resolve_streaming                # full run
    uv run python -m scripts.resolve_streaming --limit 5      # smoke test
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import traceback

from sqlalchemy import func, select

from app.database import async_session
from app.models.artist import Artist
from app.models.track import Track
from app.services.streaming.link_finder import LinkFinder, RateLimitedError
from app.services.streaming.streaming_resolution_service import (
    StreamingResolutionService,
)

PROGRESS_EVERY = 10
RATE_LIMIT_RETRY_DELAY_SEC = 10

log = logging.getLogger("resolve_streaming")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N tracks (useful for smoke testing).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    # Step 1: pull the work-list IDs. Ordered alphabetically by artist
    # name so the queue marches in a predictable, resumable order.
    async with async_session() as session:
        stmt = (
            select(Track.id)
            .join(Artist, Track.artist_id == Artist.id)
            .where(Track.streaming_resolved_at.is_(None))
            .order_by(func.lower(Artist.name), Track.title)
        )
        if args.limit:
            stmt = stmt.limit(args.limit)
        result = await session.execute(stmt)
        track_ids = list(result.scalars().all())

    total = len(track_ids)
    log.info("found %d tracks needing streaming resolution", total)
    if total == 0:
        return

    # Step 2: process. One LinkFinder + AsyncSession reused across the
    # whole loop — the service commits per call so progress is preserved
    # on Ctrl-C / failure.
    link_finder = LinkFinder()
    ok = fail = 0
    stopped_early = False

    async with async_session() as session:
        service = StreamingResolutionService(session, link_finder)

        for i, track_id in enumerate(track_ids, start=1):
            try:
                success = await service.resolve_track(track_id)
            except RateLimitedError as e:
                log.warning(
                    "rate limited on track %s: %s — waiting %ds and retrying once",
                    track_id, e, RATE_LIMIT_RETRY_DELAY_SEC,
                )
                await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SEC)
                try:
                    success = await service.resolve_track(track_id)
                except RateLimitedError as e2:
                    log.error(
                        "rate limited again on track %s after retry: %s",
                        track_id, e2,
                    )
                    log.error(
                        "stopping at track %d/%d — re-run later when "
                        "the rate limit clears",
                        i, total,
                    )
                    stopped_early = True
                    break
            except Exception:  # noqa: BLE001 — log and continue on per-track failure
                log.error(
                    "track %s: unhandled error\n%s",
                    track_id,
                    traceback.format_exc(),
                )
                success = False

            if success:
                ok += 1
            else:
                fail += 1
            if i % PROGRESS_EVERY == 0:
                log.info(
                    "progress %d/%d  ok=%d fail=%d", i, total, ok, fail,
                )

    if stopped_early:
        log.info("stopped early due to rate limiting: ok=%d fail=%d", ok, fail)
        sys.exit(2)
    log.info("done: ok=%d fail=%d total=%d", ok, fail, total)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(
            "\ninterrupted — progress saved up to the last completed track",
            file=sys.stderr,
        )
        sys.exit(130)
