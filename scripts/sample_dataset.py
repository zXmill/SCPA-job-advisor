"""Load the permanent SCPA sample dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE_DIR = REPO_ROOT / "data" / "sample"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_sample_dataset(sample_dir: Path = DEFAULT_SAMPLE_DIR) -> dict[str, list[dict[str, Any]]]:
    return {
        "users": load_jsonl(sample_dir / "users.jsonl"),
        "jobs": load_jsonl(sample_dir / "jobs.jsonl"),
        "interactions": load_jsonl(sample_dir / "interactions.jsonl"),
        "milestones": load_jsonl(sample_dir / "milestones.jsonl"),
    }


def validate_sample_dataset(dataset: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    user_ids = {row["user_id"] for row in dataset["users"]}
    job_ids = {row["job_id"] for row in dataset["jobs"]}

    for job in dataset["jobs"]:
        for field in ("title", "company", "location", "source_url", "description", "skills", "company_logo"):
            if not job.get(field):
                errors.append(f"job {job.get('job_id')} missing {field}")

    for interaction in dataset["interactions"]:
        if interaction.get("user_id") not in user_ids:
            errors.append(f"interaction references unknown user {interaction.get('user_id')}")
        if interaction.get("job_id") not in job_ids:
            errors.append(f"interaction references unknown job {interaction.get('job_id')}")

    roles = {user["target_role"] for user in dataset["users"]}
    milestone_roles = {row["target_role"] for row in dataset["milestones"]}
    missing_roles = roles - milestone_roles
    for role in sorted(missing_roles):
        errors.append(f"missing milestones for target role {role}")
    return errors

