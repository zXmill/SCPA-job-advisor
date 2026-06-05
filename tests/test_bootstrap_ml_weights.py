"""Tests for local ML weight bootstrap utility."""

from __future__ import annotations

import sys
import types
import subprocess
from pathlib import Path

import torch

from scripts import bootstrap_ml_weights


def test_ensure_weight_dirs(tmp_path: Path) -> None:
    dirs = bootstrap_ml_weights.ensure_weight_dirs(tmp_path)

    assert dirs["sbert"].is_dir()
    assert dirs["ncf"].is_dir()
    assert dirs["dqn"].is_dir()


def test_bootstrap_torch_checkpoints(tmp_path: Path) -> None:
    dirs = bootstrap_ml_weights.ensure_weight_dirs(tmp_path)

    ncf = bootstrap_ml_weights.bootstrap_ncf(dirs["ncf"])
    dqn = bootstrap_ml_weights.bootstrap_dqn(dirs["dqn"])

    assert Path(ncf["path"]).is_file()
    assert Path(dqn["path"]).is_file()
    assert torch.load(ncf["path"], map_location="cpu", weights_only=True)
    assert torch.load(dqn["path"], map_location="cpu", weights_only=True)


def test_bootstrap_sbert_uses_local_save_pretrained(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_module = types.ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def save_pretrained(self, output_dir: str) -> None:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            Path(output_dir, "fake-model.txt").write_text(
                self.model_name,
                encoding="utf-8",
            )

    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    result = bootstrap_ml_weights.bootstrap_sbert(
        tmp_path,
        model_name="fake/sbert",
    )

    assert result["status"] == "created"
    assert Path(tmp_path, "fake-model.txt").read_text(encoding="utf-8") == "fake/sbert"


def test_bootstrap_script_runs_from_cli(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(Path("scripts") / "bootstrap_ml_weights.py"),
            "--root",
            str(tmp_path),
            "--skip-sbert",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert '"ncf"' in result.stdout
    assert (tmp_path / "services" / "ncf" / "weights" / "ncf_model.pt").is_file()
    assert (tmp_path / "services" / "dqn" / "weights" / "dqn_model.pt").is_file()
