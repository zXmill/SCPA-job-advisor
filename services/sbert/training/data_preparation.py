"""Prepare Indonesian and mixed-language profile-job pairs for SBERT training."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


POSITIVE_LABEL_THRESHOLD = 0.7
SPLITS = ("train", "validation", "test")

_SEPARATOR_RE = re.compile(r"[\s_/\-]+")
_SPACE_RE = re.compile(r"\s+")


def _compact_text(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "").strip())


def _lookup_key(value: Any) -> str:
    text = _compact_text(value).casefold()
    text = text.replace("&", " and ")
    text = _SEPARATOR_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


_RAW_SKILL_ALIASES = {
    "api": "api",
    "aws": "cloud",
    "bahasa indonesia": "indonesian",
    "bahasa inggris": "english",
    "basis data": "database",
    "berbicara di depan umum": "public speaking",
    "business analysis": "business analysis",
    "ci cd": "ci cd",
    "cloud": "cloud",
    "content writing": "content writing",
    "copywriting": "copywriting",
    "dashboard": "dashboard",
    "dasbor": "dashboard",
    "data analysis": "data analysis",
    "desain ui": "ui design",
    "docker": "docker",
    "english": "english",
    "event": "event hosting",
    "event host": "event hosting",
    "excel": "excel",
    "fastapi": "fastapi",
    "figma": "figma",
    "flutter": "flutter",
    "indonesian": "indonesian",
    "k8s": "kubernetes",
    "komputasi awan": "cloud",
    "kubernetes": "kubernetes",
    "machine learning": "machine learning",
    "master of ceremony": "event hosting",
    "mc": "event hosting",
    "menulis konten": "content writing",
    "mobile development": "mobile development",
    "pandas": "pandas",
    "pembawa acara": "event hosting",
    "pembelajaran mesin": "machine learning",
    "pemrograman python": "python",
    "penerjemahan": "translation",
    "penulisan konten": "content writing",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "presentasi": "presentation",
    "presentation": "presentation",
    "prototipe": "prototyping",
    "prototyping": "prototyping",
    "public speaking": "public speaking",
    "python": "python",
    "redis": "redis",
    "rest api": "api",
    "riset pengguna": "ux research",
    "riset ux": "ux research",
    "sql": "sql",
    "statistika": "statistics",
    "statistics": "statistics",
    "structured query language": "sql",
    "translation": "translation",
    "ui design": "ui design",
    "ui ux": "ui ux design",
    "ui ux design": "ui ux design",
    "ux research": "ux research",
}

SKILL_ALIASES = {_lookup_key(alias): canonical for alias, canonical in _RAW_SKILL_ALIASES.items()}


@dataclass(slots=True)
class SbertPairRecord:
    """Schema for a positive SBERT profile-job training pair."""

    pair_id: str
    pair_kind: str
    profile_id: str
    job_id: str
    profile_text: str
    job_text: str
    profile_skills: list[str]
    job_skills: list[str]
    matched_skills: list[str]
    hard_negative_job_id: str
    hard_negative_text: str
    hard_negative_skills: list[str]
    label: float
    source_event: str
    source_label: float
    split: str
    provenance: str


def normalize_skill(skill: Any) -> str:
    """Normalize English and Indonesian skill aliases into one canonical key."""

    key = _lookup_key(skill)
    if not key:
        return ""
    return SKILL_ALIASES.get(key, key)


def normalize_skills(skills: Iterable[Any]) -> list[str]:
    normalized = {skill for skill in (normalize_skill(value) for value in skills) if skill}
    return sorted(normalized)


def _known_skills_from_text(text: str) -> list[str]:
    lookup_text = f" {_lookup_key(text)} "
    found: set[str] = set()
    for alias, canonical in SKILL_ALIASES.items():
        if f" {alias} " in lookup_text:
            found.add(canonical)
    return sorted(found)


def _row_skills(row: Mapping[str, Any], *, text_fields: Sequence[str]) -> list[str]:
    declared = row.get("skills") or row.get("tags") or []
    if isinstance(declared, str):
        declared = [declared]
    text = " ".join(_compact_text(row.get(field)) for field in text_fields)
    return normalize_skills([*declared, *_known_skills_from_text(text)])


def _profile_text(user: Mapping[str, Any], skills: Sequence[str]) -> str:
    parts = [
        user.get("profile_text"),
        user.get("program_studi"),
        user.get("target_role"),
        " ".join(skills),
    ]
    return _compact_text(" ".join(_compact_text(part) for part in parts if _compact_text(part)))


def _job_text(job: Mapping[str, Any], skills: Sequence[str]) -> str:
    parts = [
        job.get("title"),
        job.get("company"),
        job.get("location"),
        job.get("description"),
        " ".join(skills),
    ]
    return _compact_text(" ".join(_compact_text(part) for part in parts if _compact_text(part)))


def _pair_id(profile_id: str, job_id: str) -> str:
    return f"{profile_id}__{job_id}".replace(" ", "-")


def _split_counts(size: int) -> dict[str, int]:
    if size < 3:
        return {"train": size, "validation": 0, "test": 0}
    validation = max(1, round(size * 0.1))
    test = max(1, round(size * 0.1))
    while validation + test >= size:
        if validation >= test and validation > 0:
            validation -= 1
        elif test > 0:
            test -= 1
    return {"train": size - validation - test, "validation": validation, "test": test}


def assign_deterministic_splits(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Assign train/validation/test splits independent of input order."""

    counts = _split_counts(len(records))
    ordered_ids = sorted(str(record["pair_id"]) for record in records)
    split_by_id: dict[str, str] = {}
    cursor = 0
    for split in ("test", "validation", "train"):
        count = counts[split]
        for pair_id in ordered_ids[cursor : cursor + count]:
            split_by_id[pair_id] = split
        cursor += count

    result: list[dict[str, Any]] = []
    for record in records:
        prepared = dict(record)
        prepared["split"] = split_by_id[str(record["pair_id"])]
        result.append(prepared)
    return result


def _positive_job_ids_by_user(
    interactions: Iterable[Mapping[str, Any]],
    *,
    positive_label_threshold: float,
) -> dict[str, set[str]]:
    positives: dict[str, set[str]] = {}
    for row in interactions:
        if float(row.get("label") or 0.0) >= positive_label_threshold:
            positives.setdefault(str(row.get("user_id") or ""), set()).add(str(row.get("job_id") or ""))
    return positives


def _hard_negative(
    *,
    profile_skills: Sequence[str],
    positive_job_skills: Sequence[str],
    positive_job_id: str,
    positive_job_ids: set[str],
    jobs: Mapping[str, Mapping[str, Any]],
    job_skills_by_id: Mapping[str, list[str]],
) -> tuple[str, str, list[str]]:
    excluded = set(positive_job_ids)
    excluded.add(positive_job_id)
    profile_skill_set = set(profile_skills)
    positive_skill_set = set(positive_job_skills)
    candidates: list[tuple[int, int, str]] = []
    for job_id, skills in job_skills_by_id.items():
        if job_id in excluded:
            continue
        skill_set = set(skills)
        candidates.append(
            (
                len(profile_skill_set & skill_set),
                len(positive_skill_set & skill_set),
                job_id,
            )
        )
    if not candidates:
        return "", "", []

    _, _, job_id = max(candidates, key=lambda item: (item[0], item[1], item[2]))
    skills = job_skills_by_id[job_id]
    return job_id, _job_text(jobs[job_id], skills), skills


def prepare_sbert_pair_records(
    users: Sequence[Mapping[str, Any]],
    jobs: Sequence[Mapping[str, Any]],
    interactions: Sequence[Mapping[str, Any]],
    *,
    positive_label_threshold: float = POSITIVE_LABEL_THRESHOLD,
    provenance: str = "sample_dataset",
) -> list[dict[str, Any]]:
    """Build schema-validated positive profile-job pair records."""

    users_by_id = {str(user.get("user_id") or ""): user for user in users}
    jobs_by_id = {str(job.get("job_id") or ""): job for job in jobs}
    profile_skills_by_id = {
        user_id: _row_skills(user, text_fields=("profile_text", "program_studi", "target_role"))
        for user_id, user in users_by_id.items()
    }
    job_skills_by_id = {
        job_id: _row_skills(job, text_fields=("title", "description"))
        for job_id, job in jobs_by_id.items()
    }
    positives_by_user = _positive_job_ids_by_user(
        interactions,
        positive_label_threshold=positive_label_threshold,
    )

    records: list[dict[str, Any]] = []
    for row in sorted(
        interactions,
        key=lambda item: (str(item.get("user_id") or ""), str(item.get("job_id") or "")),
    ):
        source_label = float(row.get("label") or 0.0)
        if source_label < positive_label_threshold:
            continue

        profile_id = str(row.get("user_id") or "")
        job_id = str(row.get("job_id") or "")
        if profile_id not in users_by_id or job_id not in jobs_by_id:
            continue

        profile_skills = profile_skills_by_id[profile_id]
        job_skills = job_skills_by_id[job_id]
        hard_id, hard_text, hard_skills = _hard_negative(
            profile_skills=profile_skills,
            positive_job_skills=job_skills,
            positive_job_id=job_id,
            positive_job_ids=positives_by_user.get(profile_id, set()),
            jobs=jobs_by_id,
            job_skills_by_id=job_skills_by_id,
        )
        record = SbertPairRecord(
            pair_id=_pair_id(profile_id, job_id),
            pair_kind="positive",
            profile_id=profile_id,
            job_id=job_id,
            profile_text=_profile_text(users_by_id[profile_id], profile_skills),
            job_text=_job_text(jobs_by_id[job_id], job_skills),
            profile_skills=profile_skills,
            job_skills=job_skills,
            matched_skills=sorted(set(profile_skills) & set(job_skills)),
            hard_negative_job_id=hard_id,
            hard_negative_text=hard_text,
            hard_negative_skills=hard_skills,
            label=1.0,
            source_event=str(row.get("event") or "positive"),
            source_label=source_label,
            split="train",
            provenance=provenance,
        )
        records.append(asdict(record))

    prepared = assign_deterministic_splits(records)
    errors = validate_pair_records(prepared)
    if errors:
        raise ValueError("invalid SBERT pair records: " + "; ".join(errors))
    return prepared


def validate_pair_record(record: Mapping[str, Any], *, index: int = 0) -> list[str]:
    errors: list[str] = []
    required_strings = (
        "pair_id",
        "pair_kind",
        "profile_id",
        "job_id",
        "profile_text",
        "job_text",
        "hard_negative_job_id",
        "hard_negative_text",
        "source_event",
        "split",
        "provenance",
    )
    required_lists = ("profile_skills", "job_skills", "matched_skills", "hard_negative_skills")
    for field in required_strings:
        if not isinstance(record.get(field), str) or not str(record.get(field)).strip():
            errors.append(f"record[{index}].{field} must be a non-empty string")
    for field in required_lists:
        if not isinstance(record.get(field), list):
            errors.append(f"record[{index}].{field} must be a list")
    if record.get("pair_kind") != "positive":
        errors.append(f"record[{index}].pair_kind must be positive")
    if record.get("split") not in SPLITS:
        errors.append(f"record[{index}].split must be one of {', '.join(SPLITS)}")
    if record.get("job_id") == record.get("hard_negative_job_id"):
        errors.append(f"record[{index}].hard_negative_job_id must differ from job_id")
    if float(record.get("label") or 0.0) <= 0.0:
        errors.append(f"record[{index}].label must be positive")
    if float(record.get("source_label") or 0.0) < POSITIVE_LABEL_THRESHOLD:
        errors.append(f"record[{index}].source_label must be >= {POSITIVE_LABEL_THRESHOLD}")
    for field in ("profile_skills", "job_skills", "matched_skills", "hard_negative_skills"):
        value = record.get(field)
        if isinstance(value, list):
            normalized = normalize_skills(value)
            if value != normalized:
                errors.append(f"record[{index}].{field} must be sorted normalized skills")
            if field != "matched_skills" and not value:
                errors.append(f"record[{index}].{field} must not be empty")
    return errors


def validate_pair_records(records: Sequence[Mapping[str, Any]]) -> list[str]:
    if not records:
        return ["at least one SBERT pair record is required"]
    pair_ids: set[str] = set()
    errors: list[str] = []
    for index, record in enumerate(records):
        errors.extend(validate_pair_record(record, index=index))
        pair_id = str(record.get("pair_id") or "")
        if pair_id in pair_ids:
            errors.append(f"record[{index}].pair_id duplicates {pair_id}")
        pair_ids.add(pair_id)
    return errors


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) for row in rows)
    path.write_text(payload + "\n", encoding="utf-8")


def _load_input_dir(input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        load_jsonl(input_dir / "users.jsonl"),
        load_jsonl(input_dir / "jobs.jsonl"),
        load_jsonl(input_dir / "interactions.jsonl"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare SBERT positive profile-job pair records.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--positive-label-threshold", type=float, default=POSITIVE_LABEL_THRESHOLD)
    parser.add_argument("--provenance", default="sample_dataset")
    args = parser.parse_args()

    users, jobs, interactions = _load_input_dir(args.input_dir)
    records = prepare_sbert_pair_records(
        users,
        jobs,
        interactions,
        positive_label_threshold=args.positive_label_threshold,
        provenance=args.provenance,
    )
    write_jsonl(args.output, records)
    print(json.dumps({"records": len(records), "output": str(args.output), "splits": _split_summary(records)}))
    return 0


def _split_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {split: sum(1 for record in records if record.get("split") == split) for split in SPLITS}


if __name__ == "__main__":
    raise SystemExit(main())
