"""Runtime API probe harness for the SCPA gateway.

The script exercises high-risk gateway route groups and writes sanitized
evidence. It does not persist tokens, passwords, or full user payloads.
Run from the repository root while the Docker Compose stack is up.
"""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


UNSET = object()


@dataclass
class ProbeResponse:
    status: int | None
    body: Any
    raw: str
    headers: dict[str, str]
    elapsed_ms: float
    error: str | None = None


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def parse_json(raw: bytes) -> tuple[Any, str]:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text), text
    except json.JSONDecodeError:
        return None, text


def multipart_file(field: str, filename: str, content_type: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----scpa-api-probe-{secrets.token_hex(12)}"
    chunks = [
        f"--{boundary}\r\n".encode("ascii"),
        (
            f'Content-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\n'
        ).encode("ascii"),
        f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode("ascii"),
    ]
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def request_http(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: Any = UNSET,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 45.0,
) -> ProbeResponse:
    headers: dict[str, str] = {
        "User-Agent": "SCPA-Debug-API-Probe/1.0",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = body
    if json_body is not UNSET:
        data = json_bytes(json_body)
        headers["Content-Type"] = "application/json"
    elif content_type:
        headers["Content-Type"] = content_type

    req = request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method.upper(),
        headers=headers,
    )
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - local debug target
            raw = resp.read()
            body_obj, raw_text = parse_json(raw)
            return ProbeResponse(
                status=resp.status,
                body=body_obj,
                raw=raw_text,
                headers={k.lower(): v for k, v in resp.headers.items()},
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
    except error.HTTPError as exc:
        raw = exc.read()
        body_obj, raw_text = parse_json(raw)
        return ProbeResponse(
            status=exc.code,
            body=body_obj,
            raw=raw_text,
            headers={k.lower(): v for k, v in exc.headers.items()},
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # pragma: no cover - debug harness failure path
        return ProbeResponse(
            status=None,
            body=None,
            raw="",
            headers={},
            elapsed_ms=(time.perf_counter() - started) * 1000,
            error=f"{type(exc).__name__}: {exc}",
        )


def value_shape(value: Any) -> str:
    if isinstance(value, dict):
        return f"object[{len(value)}]"
    if isinstance(value, list):
        return f"array[{len(value)}]"
    if value is None:
        return "null"
    return type(value).__name__


def summarize_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"shape": value_shape(body)}

    sensitive_keys = {"access_token", "refresh_token", "token"}
    summary: dict[str, Any] = {
        "shape": "object",
        "keys": sorted(k for k in body.keys() if k not in sensitive_keys),
    }
    if "detail" in body:
        detail = body["detail"]
        if isinstance(detail, list):
            summary["detail"] = f"validation_errors[{len(detail)}]"
        else:
            summary["detail"] = str(detail)[:160]
    if "user" in body and isinstance(body["user"], dict):
        summary["user_keys"] = sorted(body["user"].keys())
        summary["user_role"] = body["user"].get("role")
    if "jobs" in body and isinstance(body["jobs"], list):
        summary["jobs_count"] = len(body["jobs"])
        summary["total"] = body.get("total")
    if "recommendations" in body and isinstance(body["recommendations"], list):
        summary["recommendations_count"] = len(body["recommendations"])
        summary["degraded"] = body.get("degraded")
        first = body["recommendations"][0] if body["recommendations"] else {}
        if isinstance(first, dict):
            summary["recommendation_keys"] = sorted(first.keys())
    if "alerts" in body and isinstance(body["alerts"], list):
        summary["alerts_count"] = len(body["alerts"])
        summary["total"] = body.get("total")
    if "applications" in body and isinstance(body["applications"], list):
        summary["applications_count"] = len(body["applications"])
    if "experiments" in body and isinstance(body["experiments"], list):
        summary["experiments_count"] = len(body["experiments"])
        summary["total"] = body.get("total")
    if "metrics" in body and isinstance(body["metrics"], dict):
        summary["metrics_keys"] = sorted(body["metrics"].keys())
    if "skills" in body and isinstance(body["skills"], list):
        summary["skills_count"] = len(body["skills"])
    if "steps" in body and isinstance(body["steps"], list):
        summary["steps_count"] = len(body["steps"])
    if "pipeline" in body and isinstance(body["pipeline"], dict):
        summary["pipeline_keys"] = sorted(body["pipeline"].keys())
    if "models" in body and isinstance(body["models"], dict):
        summary["models_keys"] = sorted(body["models"].keys())
    if "status" in body and not isinstance(body["status"], (dict, list)):
        summary["status_value"] = body["status"]
    return summary


class ApiProbe:
    def __init__(self, base_url: str, output_dir: Path, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir
        self.timeout = timeout
        self.results: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}
        self.normal_token: str | None = None
        self.admin_token: str | None = None
        self.invalid_token = "not-a-valid-jwt"

    def case(
        self,
        case_id: str,
        group: str,
        method: str,
        path: str,
        *,
        expected: set[int] | range,
        token: str | None = None,
        json_body: Any = UNSET,
        body: bytes | None = None,
        content_type: str | None = None,
        note: str = "",
    ) -> ProbeResponse:
        resp = request_http(
            self.base_url,
            method,
            path,
            token=token,
            json_body=json_body,
            body=body,
            content_type=content_type,
            timeout=self.timeout,
        )
        if isinstance(expected, range):
            passed = resp.status in expected
            expected_label = f"{expected.start}-{expected.stop - 1}"
        else:
            passed = resp.status in expected
            expected_label = sorted(expected)
        self.results.append(
            {
                "case_id": case_id,
                "group": group,
                "method": method.upper(),
                "path": path.split("?")[0],
                "query": "present" if "?" in path else "none",
                "auth": "yes" if token else "no",
                "expected": expected_label,
                "status": resp.status,
                "pass": passed,
                "elapsed_ms": round(resp.elapsed_ms, 2),
                "gateway_latency_ms": resp.headers.get("x-gateway-latency-ms"),
                "summary": summarize_body(resp.body),
                "transport_error": resp.error,
                "note": note,
            }
        )
        return resp

    def register_user(self, label: str) -> tuple[str, str, str]:
        email = f"codex-api-audit-{label}-{utc_stamp().lower()}-{secrets.token_hex(3)}@example.invalid"
        password = f"{secrets.token_urlsafe(18)}A1!"
        body = {"name": f"Codex API Audit {label}", "email": email, "password": password}
        resp = self.case(
            f"AUTH-REGISTER-{label.upper()}",
            "auth/profile",
            "POST",
            "/api/auth/register",
            expected={200},
            json_body=body,
            note="Generated probe user; token and password redacted from report.",
        )
        token = ""
        if isinstance(resp.body, dict):
            token = str(resp.body.get("access_token") or "")
        if not token:
            raise RuntimeError(f"failed to register probe user {label}: status={resp.status}")
        return email, password, token

    def login_user(self, email: str, password: str, label: str, expected: set[int] = {200}) -> str:
        resp = self.case(
            f"AUTH-LOGIN-{label.upper()}",
            "auth/profile",
            "POST",
            "/api/auth/login",
            expected=expected,
            json_body={"email": email, "password": password},
            note="Credentials redacted from report.",
        )
        if resp.status != 200 or not isinstance(resp.body, dict):
            return ""
        return str(resp.body.get("access_token") or "")

    def promote_to_admin(self, email: str) -> dict[str, Any]:
        safe_email = email.replace("'", "''")
        sql = f"UPDATE users SET role = 'admin' WHERE email = '{safe_email}';\n"
        cmd = [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "sh",
            "-lc",
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1',
        ]
        started = time.perf_counter()
        proc = subprocess.run(
            cmd,
            input=sql,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        result = {
            "case_id": "ADMIN-PROMOTE-PROBE-USER",
            "group": "admin/ops",
            "method": "SQL",
            "path": "users.role",
            "query": "none",
            "auth": "docker-postgres",
            "expected": [0],
            "status": proc.returncode,
            "pass": proc.returncode == 0,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "gateway_latency_ms": None,
            "summary": {"shape": "process", "stdout": proc.stdout.strip()[:80]},
            "transport_error": proc.stderr.strip()[:200] if proc.returncode else None,
            "note": "Promotes a generated audit-only user so admin success paths can be tested without seed credentials.",
        }
        self.results.append(result)
        if proc.returncode != 0:
            raise RuntimeError(f"admin promotion failed: {proc.stderr}")
        return result

    def run(self) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        started_at = datetime.now(timezone.utc).isoformat()

        normal_email, normal_password, self.normal_token = self.register_user("user")
        admin_email, admin_password, _admin_user_token = self.register_user("admin")
        self.context["normal_user_email_hash"] = uuid.uuid5(uuid.NAMESPACE_DNS, normal_email).hex
        self.context["admin_user_email_hash"] = uuid.uuid5(uuid.NAMESPACE_DNS, admin_email).hex

        self.login_user(normal_email, "wrong-password", "invalid-password", expected={401})
        self.case(
            "AUTH-REGISTER-EMPTY",
            "auth/profile",
            "POST",
            "/api/auth/register",
            expected={422},
            json_body={},
        )
        self.case(
            "AUTH-REGISTER-DUPLICATE",
            "auth/profile",
            "POST",
            "/api/auth/register",
            expected={409},
            json_body={"name": "Duplicate", "email": normal_email, "password": normal_password},
        )
        self.case(
            "AUTH-LOGIN-EMPTY",
            "auth/profile",
            "POST",
            "/api/auth/login",
            expected={422},
            json_body={},
        )

        self.probe_open_routes()
        self.probe_profile_routes()
        first_job_id = self.probe_jobs_routes()
        recommendation_context = self.probe_recommendation_routes(first_job_id)

        self.probe_admin_guards_before_promotion()
        self.probe_experiment_user_guards()
        self.promote_to_admin(admin_email)
        self.admin_token = self.login_user(admin_email, admin_password, "admin-promoted")
        self.probe_admin_routes()
        self.probe_experiment_admin_routes(first_job_id)

        summary = self.build_summary(started_at, recommendation_context)
        report_path = self.output_dir / f"gateway_runtime_probe_{utc_stamp()}.json"
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")

        log_path = self.output_dir / f"gateway_runtime_probe_{utc_stamp()}.log"
        self.capture_gateway_logs(started_at, log_path)
        summary["artifacts"] = {
            "report": str(report_path).replace("\\", "/"),
            "gateway_logs": str(log_path).replace("\\", "/"),
        }
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
        return summary

    def probe_open_routes(self) -> None:
        self.case("OPEN-ROOT", "open/health", "GET", "/", expected={200})
        self.case("OPEN-HEALTH", "open/health", "GET", "/health", expected={200})
        self.case("OPEN-READY", "open/health", "GET", "/ready", expected={200})
        self.case(
            "OPEN-LOGO-BLOCK-LOCALHOST",
            "open/health",
            "GET",
            "/api/company-logo?url=http%3A%2F%2F127.0.0.1%2Flogo.png&company=Probe",
            expected={400},
        )
        self.case(
            "OPEN-SKILLS-SEARCH",
            "open/health",
            "GET",
            "/api/skills/search?q=python&limit=5",
            expected={200},
        )
        long_q = parse.quote("x" * 129)
        self.case(
            "OPEN-SKILLS-SEARCH-INVALID",
            "open/health",
            "GET",
            f"/api/skills/search?q={long_q}",
            expected={422},
        )

    def probe_profile_routes(self) -> None:
        assert self.normal_token
        self.case("AUTH-ME-UNAUTH", "auth/profile", "GET", "/api/auth/me", expected={401})
        self.case("AUTH-ME-INVALID-TOKEN", "auth/profile", "GET", "/api/auth/me", expected={401}, token=self.invalid_token)
        self.case("AUTH-ME-VALID", "auth/profile", "GET", "/api/auth/me", expected={200}, token=self.normal_token)
        self.case("PROFILE-COMPLETE-UNAUTH", "auth/profile", "GET", "/api/profile/completeness", expected={401})
        self.case("PROFILE-COMPLETE-VALID", "auth/profile", "GET", "/api/profile/completeness", expected={200}, token=self.normal_token)
        self.case(
            "PROFILE-PUT-EMPTY",
            "auth/profile",
            "PUT",
            "/api/profile",
            expected={200},
            token=self.normal_token,
            json_body={},
        )
        self.case(
            "PROFILE-PUT-VALID",
            "auth/profile",
            "PUT",
            "/api/profile",
            expected={200},
            token=self.normal_token,
            json_body={
                "name": "Codex API Audit User",
                "program_studi": "Teknik Informatika",
                "university": "Universitas Probe",
                "skills": ["Python", "SQL", "English"],
            },
        )
        self.case(
            "PROFILE-PUT-INVALID-SKILLS",
            "auth/profile",
            "PUT",
            "/api/profile",
            expected={422},
            token=self.normal_token,
            json_body={"skills": "python"},
        )
        self.case(
            "PROFILE-ONBOARDING-VALID",
            "auth/profile",
            "PUT",
            "/api/profile/onboarding",
            expected={200},
            token=self.normal_token,
            json_body={"step": 2, "data": {"skills": ["Python", "SQL", "English"]}},
        )
        self.case(
            "PROFILE-ONBOARDING-INVALID",
            "auth/profile",
            "PUT",
            "/api/profile/onboarding",
            expected={422},
            token=self.normal_token,
            json_body={"step": 4, "data": {}},
        )
        file_body, content_type = multipart_file(
            "file",
            "api-probe-cv.txt",
            "text/plain",
            (
                "Saya mahasiswa Teknik Informatika dengan pengalaman Python, SQL, "
                "FastAPI, Docker, dan machine learning."
            ).encode("utf-8"),
        )
        self.case(
            "PROFILE-CV-VALID-TXT",
            "auth/profile",
            "POST",
            "/api/profile/cv",
            expected={200},
            token=self.normal_token,
            body=file_body,
            content_type=content_type,
        )
        self.case(
            "PROFILE-CV-EMPTY-MISSING-FILE",
            "auth/profile",
            "POST",
            "/api/profile/cv",
            expected={422},
            token=self.normal_token,
            body=b"",
            content_type="multipart/form-data; boundary=empty",
        )
        self.case(
            "PROFILE-CERT-MISSING-FILE",
            "auth/profile",
            "POST",
            "/api/profile/certificates",
            expected={422},
            token=self.normal_token,
            body=b"",
            content_type="multipart/form-data; boundary=empty",
        )

    def probe_jobs_routes(self) -> str | None:
        assert self.normal_token
        jobs_resp = self.case("JOBS-LIST", "jobs/user-actions", "GET", "/api/jobs?limit=3", expected={200})
        first_job_id = None
        if isinstance(jobs_resp.body, dict) and jobs_resp.body.get("jobs"):
            first_job = jobs_resp.body["jobs"][0]
            if isinstance(first_job, dict):
                first_job_id = str(first_job.get("id") or "")
        self.context["first_job_id_present"] = bool(first_job_id)
        self.case("JOBS-LIST-INVALID-PAGE", "jobs/user-actions", "GET", "/api/jobs?page=0", expected={422})
        if first_job_id:
            encoded_job = parse.quote(first_job_id)
            self.case("JOBS-DETAIL-VALID", "jobs/user-actions", "GET", f"/api/jobs/{encoded_job}", expected={200})
            self.case("JOBS-SAVE-UNAUTH", "jobs/user-actions", "POST", f"/api/jobs/{encoded_job}/save", expected={401})
            self.case("JOBS-SAVE-VALID", "jobs/user-actions", "POST", f"/api/jobs/{encoded_job}/save", expected={200}, token=self.normal_token)
            self.case("JOBS-UNSAVE-VALID", "jobs/user-actions", "DELETE", f"/api/jobs/{encoded_job}/save", expected={200}, token=self.normal_token)
            self.case("JOBS-SKIP-VALID", "jobs/user-actions", "POST", f"/api/jobs/{encoded_job}/skip", expected={200}, token=self.normal_token)
            self.case("JOBS-SKILL-GAP-VALID", "jobs/user-actions", "GET", f"/api/jobs/{encoded_job}/skill-gap", expected={200}, token=self.normal_token)
        self.case("JOBS-DETAIL-MISSING", "jobs/user-actions", "GET", f"/api/jobs/{uuid.uuid4()}", expected={404})
        self.case("JOBS-SAVED-UNAUTH", "jobs/user-actions", "GET", "/api/jobs/saved", expected={401})
        self.case("JOBS-SAVED-VALID", "jobs/user-actions", "GET", "/api/jobs/saved", expected={200}, token=self.normal_token)
        self.case("APPLICATIONS-LIST-UNAUTH", "jobs/user-actions", "GET", "/api/applications", expected={401})
        self.case("APPLICATIONS-LIST-VALID", "jobs/user-actions", "GET", "/api/applications", expected={200}, token=self.normal_token)
        if first_job_id:
            self.case(
                "APPLICATIONS-CREATE-VALID",
                "jobs/user-actions",
                "POST",
                "/api/applications",
                expected={200},
                token=self.normal_token,
                json_body={"job_ids": [first_job_id]},
            )
        self.case(
            "APPLICATIONS-CREATE-EMPTY",
            "jobs/user-actions",
            "POST",
            "/api/applications",
            expected={422},
            token=self.normal_token,
            json_body={},
        )
        self.case(
            "APPLICATIONS-CREATE-MISSING-JOB",
            "jobs/user-actions",
            "POST",
            "/api/applications",
            expected=range(400, 500),
            token=self.normal_token,
            json_body={"job_ids": [str(uuid.uuid4())]},
            note="Invalid foreign key should be a controlled 4xx, not an internal error.",
        )
        self.case("MARKET-DEMAND-UNAUTH", "jobs/user-actions", "GET", "/api/market-demand", expected={401})
        self.case("MARKET-DEMAND-VALID", "jobs/user-actions", "GET", "/api/market-demand?limit=5", expected={200}, token=self.normal_token)
        self.probe_job_alerts()
        return first_job_id

    def probe_job_alerts(self) -> None:
        assert self.normal_token
        self.case("JOB-ALERTS-LIST-UNAUTH", "jobs/user-actions", "GET", "/api/job-alerts", expected={401})
        self.case("JOB-ALERTS-LIST-VALID", "jobs/user-actions", "GET", "/api/job-alerts", expected={200}, token=self.normal_token)
        create = self.case(
            "JOB-ALERTS-CREATE-VALID",
            "jobs/user-actions",
            "POST",
            "/api/job-alerts",
            expected={200},
            token=self.normal_token,
            json_body={
                "name": "Codex API Probe",
                "query": "data analyst",
                "location": "Jakarta",
                "min_match_percent": 70,
                "frequency": "daily",
            },
        )
        alert_id = None
        if isinstance(create.body, dict):
            alert_id = create.body.get("id")
        self.case(
            "JOB-ALERTS-CREATE-INVALID-FREQUENCY",
            "jobs/user-actions",
            "POST",
            "/api/job-alerts",
            expected={400},
            token=self.normal_token,
            json_body={"name": "Bad frequency", "frequency": "hourly"},
        )
        if alert_id is not None:
            self.case(
                "JOB-ALERTS-UPDATE-VALID",
                "jobs/user-actions",
                "PUT",
                f"/api/job-alerts/{alert_id}",
                expected={200},
                token=self.normal_token,
                json_body={"name": "Codex API Probe Updated", "active": True},
            )
            self.case(
                "JOB-ALERTS-DELETE-VALID",
                "jobs/user-actions",
                "DELETE",
                f"/api/job-alerts/{alert_id}",
                expected={200},
                token=self.normal_token,
            )
        self.case("JOB-ALERTS-DELETE-MISSING", "jobs/user-actions", "DELETE", "/api/job-alerts/999999999", expected={404}, token=self.normal_token)

    def probe_recommendation_routes(self, first_job_id: str | None) -> dict[str, Any]:
        assert self.normal_token
        context: dict[str, Any] = {}
        self.case("RECS-UNAUTH", "recommendation/learning", "POST", "/api/recommendations", expected={401}, json_body={})
        self.case(
            "RECS-INVALID-LIMIT",
            "recommendation/learning",
            "POST",
            "/api/recommendations",
            expected={422},
            token=self.normal_token,
            json_body={"limit": 0},
        )
        recs = self.case(
            "RECS-VALID",
            "recommendation/learning",
            "POST",
            "/api/recommendations",
            expected={200},
            token=self.normal_token,
            json_body={
                "refresh_jobs": False,
                "limit": 2,
                "target_role": "Data Scientist",
            },
            note="Pipeline-backed recommendation smoke through gateway.",
        )
        if isinstance(recs.body, dict):
            context["recommendation_id"] = recs.body.get("recommendation_id")
            context["run_id"] = recs.body.get("run_id")
            rec_items = recs.body.get("recommendations") or []
            if isinstance(rec_items, list) and rec_items:
                first = rec_items[0]
                if isinstance(first, dict):
                    job = first.get("job") if isinstance(first.get("job"), dict) else {}
                    context["job_id"] = str(job.get("id") or first_job_id or "")
                    context["rank"] = int(first.get("rank") or 0)
                    context["slate_job_ids"] = [
                        str((item.get("job") or {}).get("id"))
                        for item in rec_items
                        if isinstance(item, dict) and isinstance(item.get("job"), dict)
                    ]
        self.case(
            "RECS-ALIAS-VALID",
            "recommendation/learning",
            "POST",
            "/recommendations",
            expected={200},
            token=self.normal_token,
            json_body={"limit": 1},
        )
        self.case("FEEDBACK-UNAUTH", "recommendation/learning", "POST", "/api/recommendations/feedback", expected={401}, json_body={})
        self.case("FEEDBACK-EMPTY", "recommendation/learning", "POST", "/api/recommendations/feedback", expected={422}, token=self.normal_token, json_body={})
        if context.get("job_id") and context.get("recommendation_id"):
            self.case(
                "FEEDBACK-VALID",
                "recommendation/learning",
                "POST",
                "/api/recommendations/feedback",
                expected={200},
                token=self.normal_token,
                json_body={
                    "job_id": context["job_id"],
                    "recommendation_id": context["recommendation_id"],
                    "served_slate_id": context["recommendation_id"],
                    "run_id": context.get("run_id"),
                    "event": "impression",
                    "rank": 0,
                    "dwell_ms": 0,
                    "slate_job_ids": context.get("slate_job_ids", []),
                },
            )
            self.case(
                "FEEDBACK-MISSING-SLATE",
                "recommendation/learning",
                "POST",
                "/api/recommendations/feedback",
                expected=range(400, 500),
                token=self.normal_token,
                json_body={
                    "job_id": context["job_id"],
                    "recommendation_id": str(uuid.uuid4()),
                    "served_slate_id": str(uuid.uuid4()),
                    "event": "impression",
                    "rank": 0,
                    "dwell_ms": 0,
                    "slate_job_ids": [context["job_id"]],
                },
                note="Invalid slate should be a controlled 4xx, not an internal error.",
            )
        self.case(
            "FEEDBACK-INVALID-EVENT",
            "recommendation/learning",
            "POST",
            "/api/recommendations/feedback",
            expected={422},
            token=self.normal_token,
            json_body={"job_id": first_job_id or str(uuid.uuid4()), "event": "bad", "rank": 0},
        )
        self.case("LEARNING-PATH-UNAUTH", "recommendation/learning", "POST", "/api/learning-path", expected={401}, json_body={})
        self.case("LEARNING-PATH-VALID", "recommendation/learning", "POST", "/api/learning-path", expected={200}, token=self.normal_token, json_body={})
        return context

    def probe_admin_guards_before_promotion(self) -> None:
        assert self.normal_token
        self.case("ADMIN-MODEL-HEALTH-UNAUTH", "admin/ops", "GET", "/api/admin/model-health", expected={401})
        self.case("ADMIN-MODEL-HEALTH-USER", "admin/ops", "GET", "/api/admin/model-health", expected={403}, token=self.normal_token)
        self.case("PIPELINE-RUN-UNAUTH", "admin/ops", "POST", "/pipeline/run", expected={401}, json_body={"limit": 1})
        self.case("PIPELINE-RUN-USER", "admin/ops", "POST", "/pipeline/run", expected={403}, token=self.normal_token, json_body={"limit": 1})

    def probe_admin_routes(self) -> None:
        if not self.admin_token:
            self.results.append(
                {
                    "case_id": "ADMIN-SUCCESS-SKIPPED",
                    "group": "admin/ops",
                    "method": "SKIP",
                    "path": "/api/admin/model-health",
                    "query": "none",
                    "auth": "admin",
                    "expected": [200],
                    "status": None,
                    "pass": False,
                    "elapsed_ms": 0,
                    "gateway_latency_ms": None,
                    "summary": {"shape": "skip"},
                    "transport_error": "admin token unavailable",
                    "note": "Admin success probes skipped.",
                }
            )
            return
        self.case("ADMIN-MODEL-HEALTH-ADMIN", "admin/ops", "GET", "/api/admin/model-health", expected={200}, token=self.admin_token)
        self.case(
            "PIPELINE-RUN-ADMIN",
            "admin/ops",
            "POST",
            "/pipeline/run",
            expected={200},
            token=self.admin_token,
            json_body={
                "user_id": "api-runtime-admin-probe",
                "limit": 1,
                "refresh_jobs": False,
                "target_role": "Data Scientist",
            },
        )

    def probe_experiment_user_guards(self) -> None:
        assert self.normal_token
        self.case("EXPERIMENTS-LIST-UNAUTH", "experiment/event", "GET", "/api/experiments", expected={401})
        self.case("EXPERIMENTS-LIST-USER", "experiment/event", "GET", "/api/experiments?limit=5", expected={200}, token=self.normal_token)
        self.case("EXPERIMENTS-CREATE-UNAUTH", "experiment/event", "POST", "/api/experiments", expected={401}, json_body={})
        self.case(
            "EXPERIMENTS-CREATE-USER",
            "experiment/event",
            "POST",
            "/api/experiments",
            expected={403},
            token=self.normal_token,
            json_body={
                "name": f"Codex API Probe {utc_stamp()}",
                "variants": [{"name": "control", "weight": 50}, {"name": "treatment", "weight": 50}],
            },
        )
        self.case("EXPERIMENTS-CREATE-EMPTY", "experiment/event", "POST", "/api/experiments", expected={422}, token=self.normal_token, json_body={})

    def probe_experiment_admin_routes(self, first_job_id: str | None) -> None:
        assert self.normal_token
        if not self.admin_token:
            return
        create = self.case(
            "EXPERIMENTS-CREATE-ADMIN",
            "experiment/event",
            "POST",
            "/api/experiments",
            expected={200},
            token=self.admin_token,
            json_body={
                "name": f"Codex API Probe {utc_stamp()}",
                "description": "Runtime API probe experiment",
                "variants": [
                    {"name": "control", "config": {"ranker": "hybrid"}, "weight": 50},
                    {"name": "treatment", "config": {"ranker": "hybrid_reason"}, "weight": 50},
                ],
                "target_metric": "click_through_rate",
            },
        )
        exp_id = None
        if isinstance(create.body, dict):
            exp_id = create.body.get("id")
        if not exp_id:
            return
        self.case("EXPERIMENTS-GET-VALID", "experiment/event", "GET", f"/api/experiments/{exp_id}", expected={200}, token=self.normal_token)
        self.case("EXPERIMENTS-START-ADMIN", "experiment/event", "POST", f"/api/experiments/{exp_id}/start", expected={200}, token=self.admin_token)
        self.case("EXPERIMENTS-ASSIGN-USER", "experiment/event", "POST", f"/api/experiments/{exp_id}/assign", expected={200}, token=self.normal_token)
        self.case("EXPERIMENTS-METRICS-USER", "experiment/event", "GET", f"/api/experiments/{exp_id}/metrics", expected={200}, token=self.normal_token)
        self.case(
            "EVENTS-TRACK-VALID",
            "experiment/event",
            "POST",
            "/api/events/track",
            expected={200},
            token=self.normal_token,
            json_body={
                "experiment_id": str(exp_id),
                "event_type": "impression",
                "job_id": first_job_id,
                "dwell_ms": 0,
                "metadata": {"source": "api-runtime-probe"},
            },
        )
        self.case(
            "EVENTS-TRACK-UNASSIGNED",
            "experiment/event",
            "POST",
            "/api/events/track",
            expected={400},
            token=self.normal_token,
            json_body={"experiment_id": str(uuid.uuid4()), "event_type": "impression"},
        )
        self.case("EXPERIMENTS-PAUSE-ADMIN", "experiment/event", "POST", f"/api/experiments/{exp_id}/pause", expected={200}, token=self.admin_token)
        self.case("EXPERIMENTS-COMPLETE-ADMIN", "experiment/event", "POST", f"/api/experiments/{exp_id}/complete", expected={200}, token=self.admin_token)

    def capture_gateway_logs(self, since: str, path: Path) -> None:
        cmd = ["docker", "compose", "logs", "gateway", "--since", since, "--tail", "400"]
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=30, check=False)
        content = proc.stdout if proc.returncode == 0 else proc.stderr
        path.write_text(content, encoding="utf-8")

    def build_summary(self, started_at: str, recommendation_context: dict[str, Any]) -> dict[str, Any]:
        failed = [r for r in self.results if not r.get("pass")]
        by_group: dict[str, dict[str, int]] = {}
        for row in self.results:
            group = row["group"]
            bucket = by_group.setdefault(group, {"total": 0, "passed": 0, "failed": 0})
            bucket["total"] += 1
            if row.get("pass"):
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
        return {
            "session": {
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "base_url": self.base_url,
                "secrets_recorded": False,
            },
            "context": {
                **self.context,
                "recommendation_context_present": bool(recommendation_context.get("recommendation_id")),
            },
            "summary": {
                "total": len(self.results),
                "passed": len(self.results) - len(failed),
                "failed": len(failed),
                "by_group": by_group,
                "failed_case_ids": [r["case_id"] for r in failed],
                "http_5xx_case_ids": [
                    r["case_id"]
                    for r in self.results
                    if isinstance(r.get("status"), int) and r["status"] >= 500
                ],
            },
            "results": self.results,
        }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run sanitized SCPA gateway API runtime probes.")
    parser.add_argument("--base-url", default="http://127.0.0.1:9000")
    parser.add_argument("--output-dir", default="reports/debug/api")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args(argv)

    summary = ApiProbe(args.base_url, Path(args.output_dir), args.timeout).run()
    print(json.dumps(summary["summary"], indent=2, ensure_ascii=True))
    return 1 if summary["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
