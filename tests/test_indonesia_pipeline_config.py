from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT_DIR / "services" / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

locality_spec = importlib.util.spec_from_file_location(
    "pipeline_locality", PIPELINE_DIR / "pipeline" / "locality.py"
)
pipeline_locality = importlib.util.module_from_spec(locality_spec)
assert locality_spec and locality_spec.loader
locality_spec.loader.exec_module(pipeline_locality)
has_indonesia_signal = pipeline_locality.has_indonesia_signal


def test_pipeline_defaults_are_indonesia_first():
    pytest.importorskip("pydantic_settings")
    from pipeline.config import PipelineSettings

    settings = PipelineSettings(_env_file=None)

    assert settings.indonesia_only is True
    assert settings.enable_remotive is False
    assert settings.enable_jobstreet is True
    assert settings.enable_glints is True
    assert settings.enable_kalibrr is True
    assert settings.enable_karir is True
    assert settings.enable_techinasia is True
    assert "remotive" not in settings.enabled_sources
    assert "jobstreet" in settings.enabled_sources
    assert "techinasia" in settings.enabled_sources


def test_indonesia_signal_accepts_local_sources_and_locations():
    assert has_indonesia_signal(source="jobstreet", location=None)
    assert has_indonesia_signal(source="linkedin", location="Jakarta, Indonesia")
    assert has_indonesia_signal(source="indeed", salary_currency="IDR")


def test_indonesia_signal_rejects_global_remote_without_local_evidence():
    assert not has_indonesia_signal(
        source="remotive",
        location="United States",
        description="Remote backend role for US candidates only.",
        salary_currency="USD",
    )
