from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefreshToken(Base):
    """A rotated refresh token.

    Tokens are stored as sha256 hashes (the raw token only ever lives in the
    user's HttpOnly cookie). Each rotation creates a new row in the same
    `family_id`; presenting an already-replaced token revokes the whole family.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    # sha256 hex of the raw token. Looked up by hash on every refresh.
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # All tokens descended from the same initial sign-in share a family_id.
    # On reuse detection, every row with this family_id is revoked.
    family_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    # Set when this token has been rotated to a successor. A second presentation
    # of a replaced token is a reuse signal.
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set on logout, family-wide revocation, or manual invalidation.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
