#!/usr/bin/env python3
"""SCPA concurrent swarm test — parallel health + POST waves across all services."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

CONCURRENCY = 15
TIMEOUT = 30.0
WAVE4_SECONDS = 0  # set via --wave4


@dataclass
class Target:
    name: str
    port: int
    health_path: str = "/health"
    post_path: Optional[str] = None
    valid_body: Optional[dict] = None
    malformed_body: Optional[dict] = None
    gateway_prefix: Optional[str] = None  # via nginx :8000
    use_asgi: bool = False
    asgi_app: Any = None


@dataclass
class WaveResult:
    ok: int = 0
    total: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    status_counts: dict[int, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def record(self, status: int, latency_ms: float, err: Optional[str] = None) -> None:
        self.total += 1
        self.latencies_ms.append(latency_ms)
        self.status_counts[status] = self.status_counts.get(status, 0) + 1
        if err:
            self.errors.append(err)

    @property
    def success_pct(self) -> float:
        return (100.0 * self.ok / self.total) if self.total else 0.0

    def p50(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0

    def p95(self) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        idx = max(0, int(len(s) * 0.95) - 1)
        return s[idx]


def _load_asgi_targets() -> list[Target]:
    """Import FastAPI apps for in-process ASGI when HTTP stack is down."""
    targets: list[Target] = []
    try:
        from services.ncf.main import app as ncf_app

        targets.append(
            Target(
                name="NCF",
                port=8001,
                post_path="/recommend/ncf",
                valid_body={"user_id": "swarm-user", "n_items": 5},
                malformed_body={},
                use_asgi=True,
                asgi_app=ncf_app,
            )
        )
    except Exception as e:
        print(f"[asgi] skip NCF: {e}", file=sys.stderr)

    try:
        from services.sbert.main import app as sbert_app

        targets.append(
            Target(
                name="SBERT",
                port=8002,
                post_path="/match/semantic",
                valid_body={
                    "user_profile_text": "Python developer",
                    "job_descriptions": ["ML Engineer", "Frontend Dev"],
                },
                malformed_body={"user_profile_text": "x"},
                use_asgi=True,
                asgi_app=sbert_app,
            )
        )
    except Exception as e:
        print(f"[asgi] skip SBERT: {e}", file=sys.stderr)

    try:
        from services.dqn.main import app as dqn_app

        targets.append(
            Target(
                name="DQN",
                port=8003,
                post_path="/learning-path",
                valid_body={
                    "user_id": "swarm-user",
                    "current_skills": ["Python"],
                    "target_role": "Data Scientist",
                },
                malformed_body={"user_id": "swarm-user"},
                use_asgi=True,
                asgi_app=dqn_app,
            )
        )
    except Exception as e:
        print(f"[asgi] skip DQN: {e}", file=sys.stderr)

    try:
        from services.hybrid.main import app as hybrid_app

        targets.append(
            Target(
                name="Hybrid",
                port=8004,
                post_path="/recommend/hybrid",
                valid_body={
                    "user_id": "swarm-user",
                    "user_profile_text": "Data scientist with Python",
                    "is_new_user": True,
                    "job_candidates": [
                        {"id": "j1", "desc": "ML Engineer"},
                        {"id": "j2", "desc": "Frontend Dev"},
                    ],
                },
                malformed_body={"user_id": "swarm-user"},
                use_asgi=True,
                asgi_app=hybrid_app,
            )
        )
    except Exception as e:
        print(f"[asgi] skip Hybrid: {e}", file=sys.stderr)

    try:
        from services.pipeline.main import api as pipeline_app

        targets.append(
            Target(
                name="Pipeline",
                port=8005,
                post_path="/scrape",
                valid_body={"keywords": ["python"], "max_pages": 1},
                malformed_body={"keywords": "not-a-list"},
                use_asgi=True,
                asgi_app=pipeline_app,
            )
        )
    except Exception as e:
        print(f"[asgi] skip Pipeline: {e}", file=sys.stderr)

    try:
        from services.gateway.main import app as gateway_app

        targets.append(
            Target(
                name="Gateway",
                port=8010,
                post_path="/api/auth/login",
                valid_body={"email": "a@b.com", "password": "secret"},
                malformed_body={"email": "not-email"},
                use_asgi=True,
                asgi_app=gateway_app,
            )
        )
    except Exception as e:
        print(f"[asgi] skip Gateway: {e}", file=sys.stderr)

    return targets


def http_targets() -> list[Target]:
    return [
        Target(
            name="Nginx",
            port=8000,
            health_path="/health",
            gateway_prefix=None,
        ),
        Target(
            name="NCF",
            port=8001,
            post_path="/recommend/ncf",
            valid_body={"user_id": "swarm-user", "n_items": 5},
            malformed_body={},
            gateway_prefix="/api/ncf",
        ),
        Target(
            name="SBERT",
            port=8002,
            post_path="/match/semantic",
            valid_body={
                "user_profile_text": "Python developer",
                "job_descriptions": ["ML Engineer", "Frontend Dev"],
            },
            malformed_body={"user_profile_text": "x"},
            gateway_prefix="/api/sbert",
        ),
        Target(
            name="DQN",
            port=8003,
            post_path="/learning-path",
            valid_body={
                "user_id": "swarm-user",
                "current_skills": ["Python"],
                "target_role": "Data Scientist",
            },
            malformed_body={"user_id": "swarm-user"},
            gateway_prefix="/api/dqn",
        ),
        Target(
            name="Hybrid",
            port=8004,
            post_path="/recommend/hybrid",
            valid_body={
                "user_id": "swarm-user",
                "user_profile_text": "Data scientist with Python",
                "is_new_user": True,
                "job_candidates": [
                    {"id": "j1", "desc": "ML Engineer"},
                    {"id": "j2", "desc": "Frontend Dev"},
                ],
            },
            malformed_body={"user_id": "swarm-user"},
            gateway_prefix="/api/hybrid",
        ),
        Target(
            name="Pipeline",
            port=8005,
            post_path="/scrape",
            valid_body={"keywords": ["python"], "max_pages": 1},
            malformed_body={"keywords": "not-a-list"},
        ),
        Target(
            name="Gateway",
            port=int(os.environ.get("GATEWAY_PORT", "8010")),
            post_path="/api/auth/login",
            valid_body={"email": "swarm@example.com", "password": "TestPass123!"},
            malformed_body={"email": "bad", "password": 123},
        ),
        Target(
            name="Frontend",
            port=3000,
            health_path="/",
        ),
    ]


async def _probe_http(port: int, path: str = "/health") -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"http://127.0.0.1:{port}{path}")
            return r.status_code < 500
    except Exception:
        return False


async def detect_mode() -> str:
    if await _probe_http(8001):
        return "http"
    return "asgi"


def make_client(t: Target) -> httpx.AsyncClient:
    if t.use_asgi and t.asgi_app is not None:
        from httpx import ASGITransport

        return httpx.AsyncClient(
            transport=ASGITransport(app=t.asgi_app),
            base_url="http://test",
            timeout=TIMEOUT,
        )
    return httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{t.port}",
        timeout=TIMEOUT,
    )


async def run_wave(
    t: Target,
    method: str,
    path: str,
    body: Optional[dict],
    n: int,
    accept_status: Callable[[int], bool],
) -> WaveResult:
    wr = WaveResult()
    sem = asyncio.Semaphore(n)

    async def one(_: int) -> None:
        async with sem:
            t0 = time.perf_counter()
            status = 0
            err: Optional[str] = None
            try:
                async with make_client(t) as client:
                    if method == "GET":
                        r = await client.get(path)
                    else:
                        r = await client.post(path, json=body)
                    status = r.status_code
                    if not accept_status(status):
                        err = f"status={status} body={r.text[:120]}"
            except Exception as ex:
                status = 0
                err = str(ex)[:200]
            ms = (time.perf_counter() - t0) * 1000
            wr.record(status, ms, err if err and not accept_status(status) else None)

    await asyncio.gather(*[one(i) for i in range(n)])
    wr.ok = sum(
        c
        for s, c in wr.status_counts.items()
        if accept_status(s)
    )
    return wr


async def wave_health(t: Target, n: int) -> WaveResult:
    path = t.health_path
    if t.name == "Nginx":
        accept = lambda s: s == 200
    elif t.name == "Frontend":
        accept = lambda s: 200 <= s < 400
    else:
        accept = lambda s: s == 200
    return await run_wave(t, "GET", path, None, n, accept)


async def wave_valid_post(t: Target, n: int) -> Optional[WaveResult]:
    if not t.post_path or t.valid_body is None:
        return None
    accept = lambda s: 200 <= s < 300
    return await run_wave(t, "POST", t.post_path, t.valid_body, n, accept)


async def wave_malformed_post(t: Target, n: int) -> Optional[WaveResult]:
    if not t.post_path or t.malformed_body is None:
        return None
    accept = lambda s: s in (400, 401, 403, 404, 422)
    return await run_wave(t, "POST", t.post_path, t.malformed_body, n, accept)


async def gateway_health_probes(n: int) -> dict[str, WaveResult]:
    """Extra wave via nginx prefixes."""
    out: dict[str, WaveResult] = {}
    prefixes = [
        ("gw-ncf", "/api/ncf/health"),
        ("gw-sbert", "/api/sbert/health"),
        ("gw-dqn", "/api/dqn/health"),
        ("gw-hybrid", "/api/hybrid/health"),
    ]
    if not await _probe_http(8000):
        return out

    async def probe(label: str, path: str) -> None:
        wr = WaveResult()
        sem = asyncio.Semaphore(n)

        async def one(_: int) -> None:
            async with sem:
                t0 = time.perf_counter()
                try:
                    async with httpx.AsyncClient(
                        base_url="http://127.0.0.1:8000", timeout=TIMEOUT
                    ) as c:
                        r = await c.get(path)
                        status = r.status_code
                        err = None if status == 200 else r.text[:80]
                except Exception as ex:
                    status = 0
                    err = str(ex)[:120]
                ms = (time.perf_counter() - t0) * 1000
                wr.record(status, ms, err)

        await asyncio.gather(*[one(i) for i in range(n)])
        wr.ok = sum(c for s, c in wr.status_counts.items() if s == 200)
        out[label] = wr

    await asyncio.gather(*[probe(l, p) for l, p in prefixes])
    return out


@dataclass
class ServiceReport:
    name: str
    port: int
    health: Optional[WaveResult] = None
    post: Optional[WaveResult] = None
    malformed: Optional[WaveResult] = None
    notes: str = ""
    mode: str = "http"


async def main() -> int:
    global WAVE4_SECONDS
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--wave4", type=int, default=0, help="mixed load seconds")
    parser.add_argument("--force-asgi", action="store_true")
    parser.add_argument("--force-http", action="store_true")
    args = parser.parse_args()
    n = args.concurrency
    WAVE4_SECONDS = args.wave4

    mode = "asgi" if args.force_asgi else "http"
    if not args.force_asgi and not args.force_http:
        mode = await detect_mode()
    if args.force_http:
        mode = "http"

    blockers: list[str] = []
    if mode == "http":
        targets = http_targets()
        up = 0
        for t in targets:
            if t.port and await _probe_http(t.port, t.health_path):
                up += 1
        if up == 0:
            blockers.append("Docker Desktop not running; no HTTP listeners on 8001-8005/8000")
            blockers.append("Falling back to in-process ASGI swarm (not true network integration)")
            asgi = _load_asgi_targets()
            # merge: keep nginx/frontend http-only if partially up
            for t in http_targets():
                if t.name in ("Nginx", "Frontend") and await _probe_http(t.port, t.health_path):
                    asgi.append(t)
            targets = asgi if asgi else targets
            mode = "asgi-mixed" if any(t.use_asgi for t in targets) else "http-dead"
    else:
        targets = _load_asgi_targets()
        if not targets:
            print("FATAL: could not import any ASGI apps", file=sys.stderr)
            return 2
        blockers.append("Using in-process ASGI (--force-asgi or no HTTP on 8001)")

    reports: list[ServiceReport] = []
    failures: list[tuple[str, str, str, str]] = []

    print(f"SCPA Swarm Test | mode={mode} | concurrency={n} per wave")
    print("=" * 72)

    for t in targets:
        if t.use_asgi:
            t.mode_note = "ASGI"
        rep = ServiceReport(name=t.name, port=t.port, mode=mode)
        if t.name == "Nginx" and not t.use_asgi and not await _probe_http(8000):
            rep.notes = "down"
            reports.append(rep)
            continue
        if t.name == "Frontend" and not t.use_asgi and not await _probe_http(3000, "/"):
            rep.notes = "down"
            reports.append(rep)
            continue
        if t.name == "Gateway" and mode.startswith("http") and not await _probe_http(t.port):
            rep.notes = "not in compose; port 8010 default — down"
            reports.append(rep)
            continue

        rep.health = await wave_health(t, n)
        if rep.health.success_pct < 100:
            failures.append(
                (t.name, t.health_path, f"health {rep.health.success_pct:.0f}%", "High")
            )

        rep.post = await wave_valid_post(t, n)
        if rep.post and rep.post.success_pct < 100:
            for e in rep.post.errors[:3]:
                failures.append((t.name, t.post_path or "", e, "Critical"))
            if any(s >= 500 for s in rep.post.status_counts):
                failures.append((t.name, t.post_path or "", "5xx on valid POST", "Critical"))

        rep.malformed = await wave_malformed_post(t, n)
        if rep.malformed:
            bad_5xx = sum(rep.malformed.status_counts.get(s, 0) for s in range(500, 600))
            if bad_5xx:
                failures.append(
                    (t.name, t.post_path or "", f"{bad_5xx}× 5xx on malformed", "Critical")
                )
            elif rep.malformed.success_pct < 80:
                failures.append(
                    (t.name, t.post_path or "", "malformed not mostly 4xx", "Medium")
                )

        reports.append(rep)

    gw = await gateway_health_probes(n) if mode == "http" and await _probe_http(8000) else {}

    # Print summary table
    print("\n### Swarm Test Summary")
    print(
        "| Service | Port | Health | POST | Malformed | Success % | p95 ms | Notes |"
    )
    print("| --- | ---: | --- | --- | --- | ---: | ---: | --- |")
    for rep in reports:
        h = rep.health
        p = rep.post
        m = rep.malformed
        health_s = f"{h.success_pct:.0f}%" if h else "—"
        post_s = f"{p.success_pct:.0f}%" if p else "n/a"
        mal_s = f"{m.success_pct:.0f}%" if m else "n/a"
        combined = []
        if h:
            combined.extend(h.latencies_ms)
        if p:
            combined.extend(p.latencies_ms)
        p95 = 0.0
        if combined:
            s = sorted(combined)
            p95 = s[max(0, int(len(s) * 0.95) - 1)]
        overall = 0.0
        tot_ok = (h.ok if h else 0) + (p.ok if p else 0)
        tot_n = (h.total if h else 0) + (p.total if p else 0)
        if tot_n:
            overall = 100.0 * tot_ok / tot_n
        notes = rep.notes or mode
        print(
            f"| {rep.name} | {rep.port} | {health_s} | {post_s} | {mal_s} | {overall:.0f}% | {p95:.0f} | {notes} |"
        )

    if gw:
        print("\n### Nginx proxy health (wave 1)")
        for label, wr in gw.items():
            print(f"- {label}: {wr.success_pct:.0f}% ok, p95={wr.p95():.0f}ms")

    if failures:
        print("\n### Failures")
        print("| Service | Endpoint | Error | Severity |")
        print("| --- | --- | --- | --- |")
        seen = set()
        for row in failures:
            if row in seen:
                continue
            seen.add(row)
            print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")

    if blockers:
        print("\n### Blockers")
        for b in blockers:
            print(f"- {b}")

    crit = [f for f in failures if f[3] == "Critical"]
    return 1 if crit else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
