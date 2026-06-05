"""SCPA Auth HTTP endpoint tests — end-to-end through the FastAPI app.

Covers:
    - POST /api/auth/register   (success, duplicate, validation)
    - POST /api/auth/login      (success, wrong password, unknown email)
    - GET  /api/auth/me         (header parsing, token validity, lookup)
    - PUT  /api/profile         (partial updates, skill replace)
    - PUT  /api/profile/onboarding (step 1/2/3, completion monotonicity)
    - Security invariants       (bcrypt hash, no plaintext leak, JTI)

Tests run against the real gateway routes via ``httpx.ASGITransport``
backed by a clean ``db_scpa_test`` PostgreSQL database. Each test
starts from an empty schema thanks to the per-test TRUNCATE fixture
defined in ``conftest.py``.

The tests deliberately exercise the live Postgres path because the
gateway hand-writes SQL via ``sqlalchemy.text`` — mocking the database
would hide bugs in column names, ENUM bindings, and parameter passing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import services.gateway.main as gateway_module


pytestmark = [pytest.mark.anyio, pytest.mark.auth, pytest.mark.db]


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════

DEFAULT_PASSWORD = "Str0ng-Pass!word"


async def _register(client, *, name: str = "Ibnu Test",
                    email: str = "ibnu@example.com",
                    password: str = DEFAULT_PASSWORD) -> dict[str, Any]:
    """Helper that registers a user and returns the JSON response."""
    resp = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ════════════════════════════════════════════════════════════════
# Sanity / health
# ════════════════════════════════════════════════════════════════

class TestHealth:
    """Smoke-test the app wiring is intact before exercising auth."""

    async def test_health_endpoint_returns_200(self, client) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"status": "healthy", "service": "gateway"}


# ════════════════════════════════════════════════════════════════
# Registration
# ════════════════════════════════════════════════════════════════

class TestRegister:
    """POST /api/auth/register — account creation flow."""

    async def test_register_creates_user_and_returns_token(
        self, client, db_session: AsyncSession
    ) -> None:
        """A fresh registration must persist the row and issue a JWT."""
        body = await _register(client)

        # Response shape
        assert "access_token" in body
        assert body["access_token"].count(".") == 2  # JWT structure
        user = body["user"]
        assert user["email"] == "ibnu@example.com"
        assert user["name"] == "Ibnu Test"
        assert user["role"] == "user"
        assert user["completion_percent"] == 10
        assert user["program_studi"] is None
        assert user["university"] is None

        # Persistence — the row must exist and have a bcrypt hash
        row = (await db_session.execute(
            text("SELECT id, email, password_hash, role, completion_percent "
                 "FROM users WHERE email = :e"),
            {"e": "ibnu@example.com"},
        )).mappings().first()
        assert row is not None
        assert row["email"] == "ibnu@example.com"
        assert row["role"] == "user"
        assert row["completion_percent"] == 10

    async def test_register_password_is_bcrypt_hashed(
        self, client, db_session: AsyncSession
    ) -> None:
        """Password must be stored as a bcrypt hash, never plaintext."""
        await _register(client, password="Plain-Text-1234")

        row = (await db_session.execute(
            text("SELECT password_hash FROM users WHERE email = :e"),
            {"e": "ibnu@example.com"},
        )).mappings().first()
        ph: str = row["password_hash"]

        # bcrypt hashes start with one of these prefixes
        assert ph.startswith(("$2a$", "$2b$", "$2y$"))
        # And must NOT contain the original password substring anywhere
        assert "Plain-Text-1234" not in ph

    async def test_register_duplicate_email_returns_409(
        self, client
    ) -> None:
        """Re-registering the same email must produce HTTP 409."""
        await _register(client)
        resp = await client.post(
            "/api/auth/register",
            json={
                "name": "Different Name",
                "email": "ibnu@example.com",
                "password": "another-pass",
            },
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Email sudah terdaftar"

    @pytest.mark.parametrize(
        "missing",
        ["name", "email", "password"],
        ids=["no-name", "no-email", "no-password"],
    )
    async def test_register_missing_field_returns_422(
        self, client, missing: str
    ) -> None:
        """Pydantic must reject payloads missing required fields."""
        payload = {
            "name": "X",
            "email": "x@example.com",
            "password": DEFAULT_PASSWORD,
        }
        del payload[missing]
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422

    async def test_register_token_payload_has_expected_claims(
        self, client
    ) -> None:
        """The returned access token must encode sub, role, type=access."""
        body = await _register(client)
        payload = pyjwt.decode(
            body["access_token"],
            gateway_module.JWT_SECRET,
            algorithms=[gateway_module.JWT_ALGORITHM],
        )
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert payload["sub"] == body["user"]["id"]
        # exp ~24h from now
        now_ts = datetime.now(timezone.utc).timestamp()
        assert payload["exp"] > now_ts + 23 * 3600


# ════════════════════════════════════════════════════════════════
# Login
# ════════════════════════════════════════════════════════════════

class TestLogin:
    """POST /api/auth/login — credential verification flow."""

    async def test_login_with_correct_credentials(
        self, client, db_session: AsyncSession
    ) -> None:
        reg = await _register(client)

        resp = await client.post(
            "/api/auth/login",
            json={"email": "ibnu@example.com", "password": DEFAULT_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["id"] == reg["user"]["id"]
        assert body["user"]["email"] == "ibnu@example.com"
        assert "access_token" in body

    async def test_login_updates_last_login_at(
        self, client, db_session: AsyncSession
    ) -> None:
        """The login flow updates ``users.last_login_at`` to NOW().

        The gateway stores ``last_login_at`` as ``TIMESTAMP WITHOUT
        TIME ZONE`` and writes via PostgreSQL ``NOW()``, which records
        the server's local clock time. We deliberately compare against
        the database's own clock (``NOW()``) rather than Python's
        ``datetime.utcnow()`` so the test is robust to server timezone
        configuration (the local cluster runs on Asia/Jakarta, UTC+7).
        """
        await _register(client)

        # Before login: last_login_at is NULL
        before = (await db_session.execute(
            text("SELECT last_login_at FROM users WHERE email = :e"),
            {"e": "ibnu@example.com"},
        )).scalar_one()
        assert before is None

        await client.post(
            "/api/auth/login",
            json={"email": "ibnu@example.com", "password": DEFAULT_PASSWORD},
        )

        # After: it is populated and within the last 60 seconds *of the
        # database server's own clock*, sidestepping any client/server
        # timezone skew.
        await db_session.commit()  # refresh visibility on this session
        row = (await db_session.execute(
            text(
                "SELECT last_login_at, "
                "       EXTRACT(EPOCH FROM (NOW() - last_login_at)) AS age_sec "
                "FROM users WHERE email = :e"
            ),
            {"e": "ibnu@example.com"},
        )).mappings().first()
        assert row["last_login_at"] is not None
        assert 0 <= float(row["age_sec"]) < 60, (
            f"last_login_at age {row['age_sec']}s outside [0, 60)"
        )

    async def test_login_wrong_password_returns_401(self, client) -> None:
        await _register(client)
        resp = await client.post(
            "/api/auth/login",
            json={"email": "ibnu@example.com", "password": "wrong-pass"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Password salah"

    async def test_login_unknown_email_returns_401(self, client) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Email tidak ditemukan"

    @pytest.mark.parametrize(
        "missing",
        ["email", "password"],
        ids=["no-email", "no-password"],
    )
    async def test_login_missing_field_returns_422(
        self, client, missing: str
    ) -> None:
        payload = {"email": "x@example.com", "password": DEFAULT_PASSWORD}
        del payload[missing]
        resp = await client.post("/api/auth/login", json=payload)
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════
# /api/auth/me  — current user
# ════════════════════════════════════════════════════════════════

class TestMe:
    """GET /api/auth/me — Bearer-protected current-user endpoint."""

    async def test_me_without_authorization_returns_401(
        self, client
    ) -> None:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing authorization header"

    async def test_me_with_non_bearer_scheme_returns_401(
        self, client
    ) -> None:
        resp = await client.get(
            "/api/auth/me", headers={"Authorization": "Basic abc"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing authorization header"

    async def test_me_with_invalid_token_returns_401(self, client) -> None:
        resp = await client.get(
            "/api/auth/me",
            headers=_auth_header("not.a.real.jwt"),
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    async def test_me_with_expired_token_returns_401(self, client) -> None:
        now = datetime.now(timezone.utc)
        expired = pyjwt.encode(
            {
                "sub": "00000000-0000-0000-0000-000000000000",
                "role": "user",
                "iat": now - timedelta(hours=25),
                "exp": now - timedelta(seconds=1),
                "type": "access",
            },
            gateway_module.JWT_SECRET,
            algorithm=gateway_module.JWT_ALGORITHM,
        )
        resp = await client.get(
            "/api/auth/me", headers=_auth_header(expired)
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Token expired"

    async def test_me_with_wrong_secret_returns_401(self, client) -> None:
        """Tokens signed with a foreign secret must be rejected."""
        forged = pyjwt.encode(
            {
                "sub": "00000000-0000-0000-0000-000000000000",
                "role": "user",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "type": "access",
            },
            "wrong-secret",
            algorithm="HS256",
        )
        resp = await client.get(
            "/api/auth/me", headers=_auth_header(forged)
        )
        assert resp.status_code == 401

    async def test_me_returns_profile_with_skills(
        self, client
    ) -> None:
        """A registered user's /me payload includes their skills array."""
        reg = await _register(client)
        token = reg["access_token"]

        # Push 2 skills via onboarding step 2
        await client.put(
            "/api/profile/onboarding",
            json={"step": 2, "data": {"skills": ["Python", "SQL"]}},
            headers=_auth_header(token),
        )

        resp = await client.get(
            "/api/auth/me", headers=_auth_header(token)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["email"] == "ibnu@example.com"
        assert body["role"] == "user"
        assert isinstance(body["skills"], list)
        assert {s["skill"] for s in body["skills"]} == {"Python", "SQL"}

    async def test_me_password_hash_never_returned(
        self, client
    ) -> None:
        """The /me payload must not leak the password hash."""
        reg = await _register(client)
        resp = await client.get(
            "/api/auth/me", headers=_auth_header(reg["access_token"])
        )
        body = resp.json()
        assert "password_hash" not in body
        assert "password" not in body

    async def test_me_with_token_for_deleted_user_returns_404(
        self, client, db_session: AsyncSession
    ) -> None:
        """A valid token referencing a removed user must yield 404.

        Tokens are stateless JWTs — they remain syntactically valid
        until expiry even after the underlying user row is deleted.
        ``/api/auth/me`` must surface this as ``404 User not found``
        rather than returning stale data or a 500.
        """
        reg = await _register(client)
        token = reg["access_token"]

        # Hard-delete the user, leaving the token intact and unexpired
        await db_session.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": reg["user"]["id"]},
        )
        await db_session.commit()

        resp = await client.get(
            "/api/auth/me", headers=_auth_header(token)
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "User not found"


# ════════════════════════════════════════════════════════════════
# Profile update
# ════════════════════════════════════════════════════════════════

class TestProfileUpdate:
    """PUT /api/profile — partial profile updates."""

    async def test_profile_requires_auth(self, client) -> None:
        resp = await client.put("/api/profile", json={"name": "X"})
        assert resp.status_code == 401

    async def test_profile_updates_name(
        self, client, db_session: AsyncSession
    ) -> None:
        reg = await _register(client)
        resp = await client.put(
            "/api/profile",
            json={"name": "Updated Name"},
            headers=_auth_header(reg["access_token"]),
        )
        assert resp.status_code == 200

        row = (await db_session.execute(
            text("SELECT name FROM users WHERE id = :id"),
            {"id": reg["user"]["id"]},
        )).mappings().first()
        assert row["name"] == "Updated Name"

    async def test_profile_updates_program_and_university(
        self, client, db_session: AsyncSession
    ) -> None:
        reg = await _register(client)
        resp = await client.put(
            "/api/profile",
            json={
                "program_studi": "Teknik Informatika",
                "university": "Universitas Bina Sarana Informatika",
            },
            headers=_auth_header(reg["access_token"]),
        )
        assert resp.status_code == 200

        row = (await db_session.execute(
            text("SELECT program_studi, university FROM users "
                 "WHERE id = :id"),
            {"id": reg["user"]["id"]},
        )).mappings().first()
        assert row["program_studi"] == "Teknik Informatika"
        assert row["university"] == "Universitas Bina Sarana Informatika"

    async def test_profile_skills_replace_semantics(
        self, client, db_session: AsyncSession
    ) -> None:
        """Submitting ``skills`` replaces the user's skill set entirely.

        The route deletes every existing user_skills row, then re-inserts
        the provided list. After two updates we expect only the latest
        set to remain.
        """
        reg = await _register(client)
        uid = reg["user"]["id"]
        headers = _auth_header(reg["access_token"])

        await client.put(
            "/api/profile",
            json={"skills": ["Python", "Pandas", "PostgreSQL"]},
            headers=headers,
        )
        await client.put(
            "/api/profile",
            json={"skills": ["TypeScript", "Next.js"]},
            headers=headers,
        )

        rows = (await db_session.execute(
            text("SELECT skill FROM user_skills WHERE user_id = :id"),
            {"id": uid},
        )).mappings().all()
        assert {r["skill"] for r in rows} == {"TypeScript", "Next.js"}

    async def test_profile_rejects_skill_outside_taxonomy(
        self, client
    ) -> None:
        reg = await _register(client)

        resp = await client.put(
            "/api/profile",
            json={"skills": ["Pythoon"]},
            headers=_auth_header(reg["access_token"]),
        )

        assert resp.status_code == 422
        body = resp.json()
        assert body["detail"]["invalid_skill"] == "Pythoon"
        assert body["detail"]["suggestion"] == "Python"

    async def test_profile_partial_update_only_touches_supplied_fields(
        self, client, db_session: AsyncSession
    ) -> None:
        reg = await _register(client)
        uid = reg["user"]["id"]
        headers = _auth_header(reg["access_token"])

        # Seed program_studi + university
        await client.put(
            "/api/profile",
            json={
                "program_studi": "Teknik Informatika",
                "university": "BSI",
            },
            headers=headers,
        )
        # Now update name only
        await client.put(
            "/api/profile",
            json={"name": "Ibnu Updated"},
            headers=headers,
        )

        row = (await db_session.execute(
            text("SELECT name, program_studi, university FROM users "
                 "WHERE id = :id"),
            {"id": uid},
        )).mappings().first()
        assert row["name"] == "Ibnu Updated"
        assert row["program_studi"] == "Teknik Informatika"
        assert row["university"] == "BSI"


class TestSkillTaxonomySearch:
    """GET /api/skills/search — controlled vocabulary lookup."""

    async def test_skill_search_returns_canonical_matches(self, client) -> None:
        resp = await client.get("/api/skills/search", params={"q": "py"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["skills"][0]["id"] == "Python"
        assert body["skills"][0]["name"] == "Python"
        assert body["skills"][0]["category"] == "technical"
        assert "py" in body["skills"][0]["aliases"]


# ════════════════════════════════════════════════════════════════
# Onboarding — the "fillout" flow
# ════════════════════════════════════════════════════════════════

class TestOnboardingFillout:
    """PUT /api/profile/onboarding — multi-step profile completion.

    Maps to the dashboard onboarding wizard. The route is idempotent:
    completion_percent uses ``GREATEST`` so resending an earlier step
    never reduces progress.
    """

    async def test_onboarding_requires_auth(self, client) -> None:
        resp = await client.put(
            "/api/profile/onboarding",
            json={"step": 1, "data": {}},
        )
        assert resp.status_code == 401

    async def test_step1_sets_program_and_university_and_bumps_completion(
        self, client, db_session: AsyncSession
    ) -> None:
        reg = await _register(client)
        uid = reg["user"]["id"]

        resp = await client.put(
            "/api/profile/onboarding",
            json={
                "step": 1,
                "data": {
                    "program_studi": "Sistem Informasi",
                    "university": "Universitas Indonesia",
                },
            },
            headers=_auth_header(reg["access_token"]),
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "saved", "step": 1}

        row = (await db_session.execute(
            text("SELECT program_studi, university, completion_percent "
                 "FROM users WHERE id = :id"),
            {"id": uid},
        )).mappings().first()
        assert row["program_studi"] == "Sistem Informasi"
        assert row["university"] == "Universitas Indonesia"
        assert row["completion_percent"] >= 30

    async def test_step2_inserts_skills_and_bumps_completion(
        self, client, db_session: AsyncSession
    ) -> None:
        reg = await _register(client)
        uid = reg["user"]["id"]

        resp = await client.put(
            "/api/profile/onboarding",
            json={
                "step": 2,
                "data": {"skills": ["Python", "FastAPI", "PostgreSQL"]},
            },
            headers=_auth_header(reg["access_token"]),
        )
        assert resp.status_code == 200

        skills = (await db_session.execute(
            text("SELECT skill, category, proficiency_level "
                 "FROM user_skills WHERE user_id = :id"),
            {"id": uid},
        )).mappings().all()
        assert {s["skill"] for s in skills} == {
            "Python", "FastAPI", "PostgreSQL"
        }
        # Default route inserts as technical/intermediate
        assert all(s["category"] == "technical" for s in skills)
        assert all(s["proficiency_level"] == "intermediate" for s in skills)

        pct = (await db_session.execute(
            text("SELECT completion_percent FROM users WHERE id = :id"),
            {"id": uid},
        )).scalar_one()
        assert pct >= 60

    async def test_step2_is_idempotent_for_duplicate_skills(
        self, client, db_session: AsyncSession
    ) -> None:
        """Submitting the same skill twice must not raise — ON CONFLICT."""
        reg = await _register(client)
        uid = reg["user"]["id"]
        headers = _auth_header(reg["access_token"])

        await client.put(
            "/api/profile/onboarding",
            json={"step": 2, "data": {"skills": ["Python"]}},
            headers=headers,
        )
        resp = await client.put(
            "/api/profile/onboarding",
            json={"step": 2, "data": {"skills": ["Python", "SQL"]}},
            headers=headers,
        )
        assert resp.status_code == 200

        rows = (await db_session.execute(
            text("SELECT skill FROM user_skills WHERE user_id = :id"),
            {"id": uid},
        )).mappings().all()
        # Python deduplicated, SQL added
        assert {r["skill"] for r in rows} == {"Python", "SQL"}

    async def test_step3_marks_completion_at_85(
        self, client, db_session: AsyncSession
    ) -> None:
        reg = await _register(client)
        uid = reg["user"]["id"]

        resp = await client.put(
            "/api/profile/onboarding",
            json={"step": 3, "data": {}},
            headers=_auth_header(reg["access_token"]),
        )
        assert resp.status_code == 200

        pct = (await db_session.execute(
            text("SELECT completion_percent FROM users WHERE id = :id"),
            {"id": uid},
        )).scalar_one()
        assert pct >= 85

    async def test_completion_is_monotonic_across_steps(
        self, client, db_session: AsyncSession
    ) -> None:
        """Replaying earlier steps must not decrease completion_percent."""
        reg = await _register(client)
        uid = reg["user"]["id"]
        headers = _auth_header(reg["access_token"])

        await client.put(
            "/api/profile/onboarding",
            json={"step": 3, "data": {}},
            headers=headers,
        )
        # Now replay step 1 with minimal data
        await client.put(
            "/api/profile/onboarding",
            json={"step": 1, "data": {
                "program_studi": "Teknik Informatika",
                "university": "BSI",
            }},
            headers=headers,
        )

        pct = (await db_session.execute(
            text("SELECT completion_percent FROM users WHERE id = :id"),
            {"id": uid},
        )).scalar_one()
        assert pct >= 85  # Never dropped to 30

    async def test_full_fillout_flow_end_to_end(
        self, client, db_session: AsyncSession
    ) -> None:
        """End-to-end: register → step1 → step2 → step3, then /me reflects everything."""
        reg = await _register(client)
        token = reg["access_token"]
        uid = reg["user"]["id"]
        headers = _auth_header(token)

        await client.put(
            "/api/profile/onboarding",
            json={"step": 1, "data": {
                "program_studi": "Sistem Informasi",
                "university": "BSI Jakarta",
            }},
            headers=headers,
        )
        await client.put(
            "/api/profile/onboarding",
            json={"step": 2, "data": {
                "skills": ["Python", "SQL", "TensorFlow"],
            }},
            headers=headers,
        )
        await client.put(
            "/api/profile/onboarding",
            json={"step": 3, "data": {}},
            headers=headers,
        )

        me = await client.get("/api/auth/me", headers=headers)
        body = me.json()
        assert body["id"] == uid
        assert body["program_studi"] == "Sistem Informasi"
        assert body["university"] == "BSI Jakarta"
        assert body["completion_percent"] >= 85
        assert {s["skill"] for s in body["skills"]} == {
            "Python", "SQL", "TensorFlow"
        }


# ════════════════════════════════════════════════════════════════
# Security invariants — verifying the auth surface as a whole
# ════════════════════════════════════════════════════════════════

class TestAuthSecurityInvariants:
    """Cross-cutting security checks that span multiple endpoints."""

    async def test_no_endpoint_returns_password_hash_in_payload(
        self, client
    ) -> None:
        """Across register, login, and /me, password_hash never appears."""
        reg = await _register(client)
        login = await client.post(
            "/api/auth/login",
            json={"email": "ibnu@example.com", "password": DEFAULT_PASSWORD},
        )
        me = await client.get(
            "/api/auth/me",
            headers=_auth_header(reg["access_token"]),
        )

        for resp in (reg, login.json(), me.json()):
            blob = str(resp).lower()
            assert "password_hash" not in blob
            assert "$2b$" not in blob  # bcrypt prefix
            assert "$2a$" not in blob

    async def test_each_register_produces_a_unique_jti(
        self, client
    ) -> None:
        """Repeated registrations must yield unique JWT JTIs (if present).

        The lightweight gateway token currently omits ``jti`` — this test
        is therefore a soft check: it merely asserts that two tokens are
        not byte-identical for two different users.
        """
        a = await _register(
            client, email="a@example.com", name="A"
        )
        b = await _register(
            client, email="b@example.com", name="B"
        )
        assert a["access_token"] != b["access_token"]

    async def test_sql_injection_attempt_in_email_field_is_safe(
        self, client, db_session: AsyncSession
    ) -> None:
        """Email lookup is parameterised — an SQLi payload must not drop rows.

        We attempt to log in with a classic ``' OR '1'='1`` payload. The
        gateway uses ``text(...)`` with a bound ``:email`` parameter so
        the payload is treated as a literal string, not as SQL.
        """
        await _register(client)
        evil = "' OR '1'='1"
        resp = await client.post(
            "/api/auth/login",
            json={"email": evil, "password": "anything"},
        )
        # Must NOT log us in; must be a clean 401 not a 500
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Email tidak ditemukan"

        # And the legitimate row is still there
        row = (await db_session.execute(
            text("SELECT id FROM users WHERE email = :e"),
            {"e": "ibnu@example.com"},
        )).first()
        assert row is not None
