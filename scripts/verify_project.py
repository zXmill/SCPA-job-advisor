"""Local verification runner for SCPA clone/demo readiness."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

IMPORT_CHECK = """
import importlib
mods = [
    'services.scraper.main',
    'services.sbert.main',
    'services.ncf.main',
    'services.dqn.main',
    'services.pipeline.main',
    'services.evaluation.recommendation_metrics',
    'scripts.sample_dataset',
    'scripts.run_full_pipeline',
    'scripts.retrain_pipeline',
    'scripts.demo_pipeline',
]
for mod in mods:
    importlib.import_module(mod)
    print('import_ok', mod)
"""

SCRAPER_SMOKE = """
import asyncio
from httpx import ASGITransport, AsyncClient
from services.scraper.main import app

async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://scraper') as client:
        response = await client.get('/sample')
    response.raise_for_status()
    data = response.json()
    assert data['count'] >= 5
    assert all(job.get('job_id') for job in data['jobs'])
    assert all(job.get('company_logo') for job in data['jobs'])
    print('scraper_smoke_ok', data['count'])

asyncio.run(main())
"""


def _run(name: str, command: list[str], *, env: dict[str, str]) -> bool:
    print(f"\n== {name} ==")
    print(" ".join(command))
    result = subprocess.run(command, cwd=REPO_ROOT, env=env, text=True)
    print(f"result: {'PASS' if result.returncode == 0 else 'FAIL'} ({result.returncode})")
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SCPA local verification checks.")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=[
            "import",
            "compile",
            "scraper",
            "metrics",
            "e2e",
            "pipeline",
            "retrain",
            "demo",
            "full-pytest",
        ],
        help="Run only the named checks.",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("SBERT_FORCE_FALLBACK", "1")
    env.setdefault("SBERT_ENABLE_TRANSFORMER", "0")

    checks = {
        "import": [sys.executable, "-c", IMPORT_CHECK],
        "compile": [sys.executable, "-m", "compileall", "-q", "services", "scripts", "tests"],
        "scraper": [sys.executable, "-c", SCRAPER_SMOKE],
        "metrics": [sys.executable, "-m", "pytest", "tests/test_recommendation_metrics.py", "-q"],
        "e2e": [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_sample_dataset_flow.py",
            "tests/test_training_entrypoints.py",
            "tests/test_full_pipeline_entrypoint.py",
            "tests/test_e2e_pipeline.py",
            "-q",
        ],
        "pipeline": [sys.executable, "scripts/run_full_pipeline.py", "--steps", "1", "--limit", "5"],
        "retrain": [
            sys.executable,
            "scripts/retrain_pipeline.py",
            "--output-dir",
            "reports/retraining_artifacts",
            "--steps",
            "1",
        ],
        "demo": [sys.executable, "scripts/demo_pipeline.py", "--steps", "1", "--limit", "3"],
        "full-pytest": [sys.executable, "-m", "pytest", "-q"],
    }
    selected = args.only or ["import", "compile", "scraper", "metrics", "e2e", "pipeline", "retrain", "demo"]
    failed = [name for name in selected if not _run(name, checks[name], env=env)]
    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        return 1
    print("\nAll selected verification checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
