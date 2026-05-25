"""STEP 5 — Security Tests.

Verifies JWT token validation, token expiry handling, signature
manipulation detection, and authorization enforcement.

NOTE: Rate limiting and file blocking tests require nginx (not testable
via ASGI transport). These are marked as integration tests.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.shared.auth import TokenManager, TokenError


VALID_ACCESS_SECRET = "test-secret-32-bytes-long-key!!!"
VALID_REFRESH_SECRET = "refresh-secret-32-bytes-long-key!!"
VALID_SECRET_ONE = "secret-key-one-32-bytes-long-key!!"
VALID_SECRET_TWO = "secret-key-two-32-bytes-long-key!!"


class TestJWTCreation:
    """Verify JWT token creation produces valid, signed tokens."""

    @pytest.fixture
    def tm(self):
        return TokenManager(
            secret=VALID_ACCESS_SECRET,
            refresh_secret=VALID_REFRESH_SECRET,
        )

    def test_access_token_created(self, tm) -> None:
        """Access token must be a non-empty string.

        Verifies the token is actually generated, not an empty response.
        """
        token = tm.create_access_token("user-001", role="user")
        assert isinstance(token, str)
        assert len(token) > 50  # JWTs are typically 100+ chars
        # JWT has 3 parts separated by dots
        assert token.count(".") == 2

    def test_access_token_contains_claims(self, tm) -> None:
        """Access token payload must contain sub, role, type, jti, exp.

        These claims are critical for authorization decisions.
        """
        token = tm.create_access_token("user-001", role="admin")
        payload = tm.verify_access_token(token)

        assert payload["sub"] == "user-001"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_refresh_token_created(self, tm) -> None:
        """Refresh token must be a valid JWT with type=refresh."""
        token = tm.create_refresh_token("user-001")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_extra_claims_included(self, tm) -> None:
        """Extra claims passed to create_access_token must appear in payload."""
        token = tm.create_access_token(
            "user-001",
            extra_claims={"department": "engineering", "level": 3},
        )
        payload = tm.verify_access_token(token)
        assert payload["department"] == "engineering"
        assert payload["level"] == 3

    def test_each_token_has_unique_jti(self, tm) -> None:
        """Every token must have a unique JTI (JWT ID).

        JTI uniqueness is critical for token revocation and replay prevention.
        """
        t1 = tm.create_access_token("user-001")
        t2 = tm.create_access_token("user-001")
        p1 = tm.verify_access_token(t1)
        p2 = tm.verify_access_token(t2)
        assert p1["jti"] != p2["jti"]


class TestJWTVerification:
    """Verify JWT token verification catches all invalid scenarios."""

    @pytest.fixture
    def tm(self):
        return TokenManager(
            secret=VALID_ACCESS_SECRET,
            refresh_secret=VALID_REFRESH_SECRET,
        )

    def test_valid_token_passes(self, tm) -> None:
        """A freshly created token must verify successfully."""
        token = tm.create_access_token("user-001")
        payload = tm.verify_access_token(token)
        assert payload["sub"] == "user-001"

    def test_expired_token_rejected(self, tm) -> None:
        """Expired token must raise TokenError.

        Simulated by creating a token with 0-second TTL.
        """
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-001",
            "type": "access",
            "exp": now - timedelta(seconds=1),  # Already expired
            "iat": now - timedelta(seconds=60),
            "jti": "test-jti",
        }
        token = pyjwt.encode(payload, tm.secret, algorithm="HS256")

        with pytest.raises(TokenError, match="expired"):
            tm.verify_access_token(token)

    def test_tampered_signature_rejected(self, tm) -> None:
        """Token with manipulated signature must be rejected.

        Simulates an attacker modifying the token payload without
        knowing the secret key.
        """
        token = tm.create_access_token("user-001")
        # Corrupt the signature (last part)
        parts = token.split(".")
        parts[2] = parts[2][:5] + "TAMPERED" + parts[2][13:]
        tampered = ".".join(parts)

        with pytest.raises(TokenError, match="Invalid"):
            tm.verify_access_token(tampered)

    def test_wrong_secret_rejected(self) -> None:
        """Token signed with different secret must be rejected.

        Simulates a token from a different environment/service.
        """
        tm1 = TokenManager(secret=VALID_SECRET_ONE)
        tm2 = TokenManager(secret=VALID_SECRET_TWO)

        token = tm1.create_access_token("user-001")
        with pytest.raises(TokenError, match="Invalid"):
            tm2.verify_access_token(token)

    def test_refresh_token_rejected_as_access(self, tm) -> None:
        """Refresh token must NOT be accepted as an access token.

        type=refresh must be rejected by verify_access_token().
        """
        refresh = tm.create_refresh_token("user-001")
        with pytest.raises(TokenError, match="Invalid access token"):
            tm.verify_access_token(refresh)

    def test_garbage_token_rejected(self, tm) -> None:
        """Completely invalid string must raise TokenError."""
        with pytest.raises(TokenError):
            tm.verify_access_token("not.a.valid.jwt")

    def test_empty_token_rejected(self, tm) -> None:
        """Empty string token must raise TokenError."""
        with pytest.raises(TokenError):
            tm.verify_access_token("")

    def test_no_secret_configured_raises(self, monkeypatch) -> None:
        """Creating a manager without secrets must fail during initialization."""
        import services.shared.auth as auth_module

        monkeypatch.setattr(auth_module, "JWT_SECRET", "")
        monkeypatch.setattr(auth_module, "JWT_REFRESH_SECRET", "")

        with pytest.raises(TokenError, match="not configured"):
            TokenManager(secret="", refresh_secret="")

    def test_missing_secret_rejected_before_token_creation(self) -> None:
        """JWT secret validation must fail before a token can be issued."""
        import services.shared.auth as auth_module

        with pytest.raises(TokenError, match="JWT_SECRET.*not configured"):
            auth_module.validate_jwt_secret("", "JWT_SECRET")

    def test_short_secret_rejected_before_token_creation(self) -> None:
        """Secrets shorter than 32 bytes must be rejected at configuration time."""
        import services.shared.auth as auth_module

        with pytest.raises(TokenError, match="JWT_SECRET.*at least 32 bytes"):
            auth_module.validate_jwt_secret("short-secret", "JWT_SECRET")

    def test_token_manager_rejects_short_access_secret_on_init(self) -> None:
        """TokenManager should fail fast instead of waiting until first use."""
        with pytest.raises(TokenError, match="access token secret.*at least 32 bytes"):
            TokenManager(secret="short-secret", refresh_secret=VALID_REFRESH_SECRET)

    def test_token_manager_rejects_short_refresh_secret_on_init(self) -> None:
        """Refresh-token signing must not silently accept weak configuration."""
        with pytest.raises(TokenError, match="refresh token secret.*at least 32 bytes"):
            TokenManager(secret=VALID_ACCESS_SECRET, refresh_secret="short-secret")


class TestJWTRefreshRotation:
    """Verify refresh token rotation with one-time-use semantics."""

    @pytest.fixture
    def tm(self):
        return TokenManager(
            secret=VALID_ACCESS_SECRET,
            refresh_secret=VALID_REFRESH_SECRET,
            redis_client=None,  # No Redis = no JTI tracking
        )

    @pytest.mark.anyio
    async def test_rotation_returns_new_pair(self, tm) -> None:
        """Token rotation must return a new (access, refresh) pair.

        Both tokens should be valid JWTs with correct types.
        """
        refresh = tm.create_refresh_token("user-001")
        new_access, new_refresh = await tm.rotate_refresh_token(refresh)

        assert isinstance(new_access, str)
        assert isinstance(new_refresh, str)

        # Verify new access token
        payload = tm.verify_access_token(new_access)
        assert payload["sub"] == "user-001"

    @pytest.mark.anyio
    async def test_rotation_preserves_user_id(self, tm) -> None:
        """Rotated tokens must maintain the same user_id (sub claim)."""
        refresh = tm.create_refresh_token("user-42")
        new_access, _ = await tm.rotate_refresh_token(refresh)

        payload = tm.verify_access_token(new_access)
        assert payload["sub"] == "user-42"

    @pytest.mark.anyio
    async def test_rotation_with_expired_refresh_fails(self, tm) -> None:
        """Attempting to rotate an expired refresh token must fail."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-001",
            "type": "refresh",
            "exp": now - timedelta(seconds=1),
            "iat": now - timedelta(days=31),
            "jti": "expired-jti",
        }
        expired_token = pyjwt.encode(payload, tm.refresh_secret, algorithm="HS256")

        with pytest.raises(TokenError, match="expired"):
            await tm.rotate_refresh_token(expired_token)
