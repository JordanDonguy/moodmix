from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
TAG_RE = re.compile(r"<[^>]*>")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_text(value: str) -> str:
    """Strip HTML tags and control chars from a free-text field.

    Leaves tab/newline/carriage-return intact so message formatting survives.
    HTML output is still escaped at render time - this is defense in depth.
    """
    cleaned = TAG_RE.sub("", value)
    cleaned = CONTROL_CHARS_RE.sub("", cleaned)
    return cleaned.strip()


class ContactRequest(BaseModel):
    """Inbound payload from the contact form.

    `website` is a honeypot field — humans leave it empty, bots fill it in.
    """

    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    website: str = Field(default="", max_length=200)

    @field_validator("name", "message", mode="after")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        cleaned = _sanitize_text(value)
        if not cleaned:
            raise ValueError("must not be blank after sanitization")
        return cleaned

    @field_validator("email", mode="after")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        cleaned = _sanitize_text(value).lower()
        if not EMAIL_RE.match(cleaned):
            raise ValueError("invalid email address")
        return cleaned


class ContactResponse(BaseModel):
    """Acknowledgement returned to the client."""

    sent: bool
