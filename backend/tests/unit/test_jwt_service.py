# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
"""Unit tests for JwtService.

Pure crypto — no DB. Secret/TTL are injected so each test runs in isolation.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from app.exceptions import InvalidCredentialsError, TokenExpiredError
from app.services.jwt_service import JwtService


_TEST_SECRET = "test-secret-at-least-32-bytes-long-for-hs256-x"


def make_service(
    secret: str = _TEST_SECRET,
    access_ttl_minutes: int = 15,
) -> JwtService:
    return JwtService(
        secret=secret,
        algorithm="HS256",
        access_ttl_minutes=access_ttl_minutes,
    )


class TestCreateAccessToken:
    def test_returns_decodable_jwt_with_expected_claims(self):
        # ARRANGE
        service = make_service()
        user_id = uuid4()

        # ACT
        token = service.create_access_token(user_id)

        # ASSERT
        decoded = jwt.decode(token, _TEST_SECRET, algorithms=["HS256"])
        assert decoded["sub"] == str(user_id)
        assert decoded["type"] == "access"
        assert decoded["iat"] <= int(datetime.now(timezone.utc).timestamp())
        assert decoded["exp"] > decoded["iat"]

    def test_exp_respects_configured_ttl(self):
        # ARRANGE
        service = make_service(access_ttl_minutes=5)
        user_id = uuid4()

        # ACT
        token = service.create_access_token(user_id)

        # ASSERT - exp ≈ iat + 5*60 (allow small drift)
        decoded = jwt.decode(token, _TEST_SECRET, algorithms=["HS256"])
        assert 4 * 60 < decoded["exp"] - decoded["iat"] <= 5 * 60

    def test_raises_when_secret_not_configured(self):
        # ARRANGE
        service = make_service(secret="")

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            service.create_access_token(uuid4())


class TestDecodeAccessToken:
    def test_round_trip_returns_original_subject(self):
        # ARRANGE
        service = make_service()
        user_id = uuid4()
        token = service.create_access_token(user_id)

        # ACT
        claims = service.decode_access_token(token)

        # ASSERT
        assert claims.sub == str(user_id)
        assert claims.type == "access"

    def test_expired_token_raises_token_expired(self):
        # ARRANGE
        service = make_service(access_ttl_minutes=15)
        # Forge an already-expired token without time-traveling the service.
        now = datetime.now(timezone.utc) - timedelta(hours=1)
        expired = jwt.encode(
            {
                "sub": str(uuid4()),
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=15)).timestamp()),
                "type": "access",
            },
            _TEST_SECRET,
            algorithm="HS256",
        )

        # ACT & ASSERT
        with pytest.raises(TokenExpiredError):
            service.decode_access_token(expired)

    def test_wrong_signature_raises_invalid_credentials(self):
        # ARRANGE
        service = make_service(secret=_TEST_SECRET)
        # Token signed with a different key.
        forged = jwt.encode(
            {
                "sub": str(uuid4()),
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
                "type": "access",
            },
            "another-secret-also-32-bytes-long-but-different-x",
            algorithm="HS256",
        )

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            service.decode_access_token(forged)

    def test_garbage_token_raises_invalid_credentials(self):
        # ARRANGE
        service = make_service()

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            service.decode_access_token("not-a-jwt")

    def test_wrong_token_type_rejected(self):
        """A refresh-typed JWT must not be accepted as an access token."""
        # ARRANGE
        service = make_service()
        now = datetime.now(timezone.utc)
        wrong_type = jwt.encode(
            {
                "sub": str(uuid4()),
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=15)).timestamp()),
                "type": "refresh",
            },
            _TEST_SECRET,
            algorithm="HS256",
        )

        # ACT & ASSERT
        with pytest.raises(InvalidCredentialsError):
            service.decode_access_token(wrong_type)
