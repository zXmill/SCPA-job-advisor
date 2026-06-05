"""Pipeline configuration with Indonesia-first defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class PipelineSettings:
    """Runtime flags for pipeline source selection.

    The constructor accepts ``_env_file`` for compatibility with
    pydantic-settings based call sites; this lightweight class reads directly
    from the process environment for tests and local scripts.
    """

    indonesia_only: bool = True
    enable_jobstreet: bool = True
    enable_linkedin: bool = True
    enable_glints: bool = True
    enable_kalibrr: bool = True
    enable_karir: bool = True
    enable_topkarir: bool = True
    enable_kitalulus: bool = True
    enable_techinasia: bool = True
    enable_indeed: bool = True
    enable_remotive: bool = False

    def __init__(self, _env_file: str | None = None, **overrides: bool) -> None:
        del _env_file
        self.indonesia_only = bool(
            overrides.get("indonesia_only", _env_bool("PIPELINE_INDONESIA_ONLY", True))
        )
        for name, default in {
            "enable_jobstreet": True,
            "enable_linkedin": True,
            "enable_glints": True,
            "enable_kalibrr": True,
            "enable_karir": True,
            "enable_topkarir": True,
            "enable_kitalulus": True,
            "enable_techinasia": True,
            "enable_indeed": True,
            "enable_remotive": False,
        }.items():
            env_name = f"PIPELINE_{name.upper()}"
            setattr(self, name, bool(overrides.get(name, _env_bool(env_name, default))))

    @property
    def enabled_sources(self) -> list[str]:
        mapping = {
            "jobstreet": self.enable_jobstreet,
            "linkedin": self.enable_linkedin,
            "glints": self.enable_glints,
            "kalibrr": self.enable_kalibrr,
            "karir": self.enable_karir,
            "topkarir": self.enable_topkarir,
            "kitalulus": self.enable_kitalulus,
            "techinasia": self.enable_techinasia,
            "indeed": self.enable_indeed,
            "remotive": self.enable_remotive,
        }
        return [source for source, enabled in mapping.items() if enabled]

