"""JWT token management shared across SCPA services."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


MIN_JWT_SECRET_BYTES = 32


class TokenError(Exception):
    """Raised when token creation or verification fails."""


def validate_jwt_secret(value: str | None, name: str = "JWT_SECRET") -> str:
    """Validate and return a JWT signing secret."""
    secret = (value or "").strip()
    if not secret:
        raise TokenError(f"{name} not configured")
    if len(secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
        raise TokenError(f"{name} must be at least {MIN_JWT_SECRET_BYTES} bytes")
    return secret


JWT_SECRET = validate_jwt_secret(os.getenv("JWT_SECRET", ""), "JWT_SECRET")
JWT_REFRESH_SECRET = validate_jwt_secret(
    os.getenv("JWT_REFRESH_SECRET", JWT_SECRET),
    "JWT_REFRESH_SECRET",
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


class TokenManager:
    """Small JWT manager with optional refresh-token rotation tracking."""

    def __init__(
        self,
        *,
        secret: str | None = None,
        refresh_secret: str | None = None,
        redis_client: Any | None = None,
        access_ttl_seconds: int = 24 * 60 * 60,
        refresh_ttl_seconds: int = 30 * 24 * 60 * 60,
    ) -> None:
        self.secret = validate_jwt_secret(
            secret if secret is not None else JWT_SECRET,
            "access token secret",
        )
        self.refresh_secret = validate_jwt_secret(
            refresh_secret if refresh_secret is not None else JWT_REFRESH_SECRET,
            "refresh token secret",
        )
        self.redis_client = redis_client
        self.access_ttl_seconds = access_ttl_seconds
        self.refresh_ttl_seconds = refresh_ttl_seconds

    def _ensure_secret(self, value: str | None, token_type: str) -> str:
        return validate_jwt_secret(value, f"{token_type} token secret")

    def _make_payload(
        self,
        subject: str,
        *,
        token_type: str,
        ttl_seconds: int,
        role: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": str(subject),
            "type": token_type,
            "iat": now,
            "exp": now + timedelta(seconds=ttl_seconds),
            "jti": str(uuid.uuid4()),
        }
        if role:
            payload["role"] = role
        if extra_claims:
            payload.update(extra_claims)
        return payload

    def create_access_token(
        self,
        subject: str,
        *,
        role: str = "user",
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        secret = self._ensure_secret(self.secret, "access")
        payload = self._make_payload(
            subject,
            token_type="access",
            ttl_seconds=self.access_ttl_seconds,
            role=role,
            extra_claims=extra_claims,
        )
        return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)

    def create_refresh_token(
        self,
        subject: str,
        *,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        secret = self._ensure_secret(self.refresh_secret, "refresh")
        payload = self._make_payload(
            subject,
            token_type="refresh",
            ttl_seconds=self.refresh_ttl_seconds,
            extra_claims=extra_claims,
        )
        return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)

    def _decode(self, token: str, secret: str, expected_type: str) -> dict[str, Any]:
        if not token:
            raise TokenError("Invalid token")
        try:
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("Token expired") from exc
        except jwt.InvalidTokenError as exc:
            try:
                unsafe_payload = jwt.decode(
                    token,
                    options={"verify_signature": False, "verify_exp": False},
                )
            except jwt.InvalidTokenError:
                unsafe_payload = {}
            if expected_type == "access" and unsafe_payload.get("type") == "refresh":
                raise TokenError("Invalid access token") from exc
            raise TokenError("Invalid token") from exc

        if payload.get("type") != expected_type:
            raise TokenError(f"Invalid {expected_type} token")
        return payload

    def verify_access_token(self, token: str) -> dict[str, Any]:
        secret = self._ensure_secret(self.secret, "access")
        return self._decode(token, secret, "access")

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        secret = self._ensure_secret(self.refresh_secret, "refresh")
        return self._decode(token, secret, "refresh")

    async def rotate_refresh_token(self, refresh_token: str) -> tuple[str, str]:
        payload = self.verify_refresh_token(refresh_token)
        jti = str(payload.get("jti") or "")

        if self.redis_client is not None and jti:
            key = f"jwt:refresh:used:{jti}"
            exists = await self.redis_client.get(key)
            if exists:
                raise TokenError("Invalid refresh token")
            await self.redis_client.setex(key, self.refresh_ttl_seconds, "1")

        subject = str(payload["sub"])
        role = str(payload.get("role") or "user")
        return (
            self.create_access_token(subject, role=role),
            self.create_refresh_token(subject),
        )
