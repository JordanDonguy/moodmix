"""Unit tests for the ContactRequest schema sanitization."""

import pytest
from pydantic import ValidationError

from app.schemas.contact import ContactRequest


class TestContactRequestSanitization:
    def test_valid_payload_passes_through(self):
        # ACT
        req = ContactRequest(
            name="John Doe",
            email="johndoe@example.com",
            message="Hello there!",
        )

        # ASSERT
        assert req.name == "John Doe"
        assert req.email == "johndoe@example.com"
        assert req.message == "Hello there!"
        assert req.website == ""

    def test_strips_html_tags_from_name(self):
        # ACT
        req = ContactRequest(
            name="<script>alert(1)</script>John",
            email="johndoe@example.com",
            message="hi",
        )

        # ASSERT
        assert req.name == "alert(1)John"

    def test_strips_html_tags_from_message(self):
        # ACT
        req = ContactRequest(
            name="John",
            email="johndoe@example.com",
            message="<img src=x onerror=alert(1)>hello<div>world</div>",
        )

        # ASSERT
        assert "<" not in req.message
        assert ">" not in req.message
        assert "hello" in req.message
        assert "world" in req.message

    def test_strips_control_chars(self):
        # ACT
        req = ContactRequest(
            name="John\x00\x07",
            email="johndoe@example.com",
            message="hi\x00there\x1f",
        )

        # ASSERT
        assert req.name == "John"
        assert req.message == "hithere"

    def test_preserves_newlines_in_message(self):
        # ACT
        req = ContactRequest(
            name="John",
            email="johndoe@example.com",
            message="line one\nline two\n\nline four",
        )

        # ASSERT
        assert req.message == "line one\nline two\n\nline four"

    def test_email_is_lowercased(self):
        # ACT
        req = ContactRequest(
            name="John",
            email="JOHNDOE@Example.COM",
            message="hi",
        )

        # ASSERT
        assert req.email == "johndoe@example.com"

    def test_invalid_email_rejected(self):
        # ACT & ASSERT
        with pytest.raises(ValidationError):
            ContactRequest(
                name="John",
                email="not-an-email",
                message="hi",
            )

    def test_blank_after_sanitization_rejected(self):
        """An input made entirely of tags/whitespace must be rejected."""
        # ACT & ASSERT
        with pytest.raises(ValidationError):
            ContactRequest(
                name="<script></script>",
                email="johndoe@example.com",
                message="hi",
            )

    def test_message_too_long_rejected(self):
        # ACT & ASSERT
        with pytest.raises(ValidationError):
            ContactRequest(
                name="John",
                email="johndoe@example.com",
                message="a" * 2001,
            )

    def test_name_too_long_rejected(self):
        # ACT & ASSERT
        with pytest.raises(ValidationError):
            ContactRequest(
                name="a" * 101,
                email="johndoe@example.com",
                message="hi",
            )

    def test_honeypot_optional_and_defaults_empty(self):
        # ACT
        req = ContactRequest(
            name="John",
            email="johndoe@example.com",
            message="hi",
        )

        # ASSERT
        assert req.website == ""

    def test_trims_surrounding_whitespace(self):
        # ACT
        req = ContactRequest(
            name="  John  ",
            email="  johndoe@example.com  ",
            message="  hello  ",
        )

        # ASSERT
        assert req.name == "John"
        assert req.email == "johndoe@example.com"
        assert req.message == "hello"
