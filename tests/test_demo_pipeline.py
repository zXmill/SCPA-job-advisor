from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_demo_pipeline_prints_real_recommendations_and_reports() -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("SBERT_FORCE_FALLBACK", "1")
    env.setdefault("SBERT_ENABLE_TRANSFORMER", "0")

    result = subprocess.run(
        [sys.executable, "scripts/demo_pipeline.py", "--steps", "1", "--limit", "2"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Demo status: ok" in result.stdout
    assert "Job recommendations" in result.stdout
    assert "DQN reranker evidence" in result.stdout
    assert "DQN session rerank score" in result.stdout
    assert "is_generalization_evidence" in result.stdout
    assert "precision@5=" in result.stdout
    assert (REPO_ROOT / "reports" / "full_pipeline_metrics.csv").exists()
    assert (REPO_ROOT / "reports" / "full_pipeline_summary.json").exists()
    assert (REPO_ROOT / "reports" / "full_pipeline_recommendations.json").exists()
