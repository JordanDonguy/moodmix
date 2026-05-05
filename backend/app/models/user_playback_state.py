from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserPlaybackState(Base):
    """Resume-playback pointer — one row per user.

    Tracks the most-recently-played mix and how far into it the user got, so
    a returning session can offer to pick up where they left off. The row is
    upserted on every throttled write (every ~30s while playing, plus on mix
    change and pagehide) so cross-device handoff is last-write-wins.
    """

    __tablename__ = "user_playback_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
    )
    # ON DELETE SET NULL so a removed mix doesn't cascade-delete the user's
    # row; the read path treats null mix_id as "nothing to resume".
    mix_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mixes.id", ondelete="SET NULL"),
    )
    seconds_listened: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
