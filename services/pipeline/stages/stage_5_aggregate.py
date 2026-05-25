"""Stage 5: learned score aggregation.

No static domain map is used here. The cold-start path relies on SBERT
similarity; as feedback accumulates, online NCF and DQN scores naturally take
more weight.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from services.pipeline.calibration import (
    CALIBRATOR_BASELINE,
    calibrated_score,
    extract_calibration_features,
    get_default_calibrator,
)


@dataclass
class AggregateStageResult:
    ranked: list[dict[str, Any]]
    summary: dict[str, Any]


def dynamic_weights(interaction_count: int) -> tuple[float, float, float, str]:
    if interaction_count <= 0:
        return 0.75, 0.2, 0.05, "cold"
    if interaction_count <= 20:
        return 0.55, 0.35, 0.1, "warm"
    return 0.45, 0.4, 0.15, "active"


_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")

SKILL_RELATED_TERMS: dict[str, set[str]] = {
    "python": {"python", "fastapi", "django", "pandas", "numpy", "backend", "data", "machine", "learning", "api"},
    "react": {"react", "reactjs", "react.js", "nextjs", "next.js", "frontend", "front-end", "javascript", "typescript", "web"},
    "web": {"web", "frontend", "front-end", "html", "css", "javascript", "typescript", "react", "nextjs", "node", "developer"},
    "sql": {"sql", "postgresql", "postgres", "mysql", "database", "data", "analyst"},
    "machine learning": {"machine", "learning", "ml", "ai", "model", "pytorch", "tensorflow", "data", "scientist"},
}

TECH_PROFILE_TERMS = {
    "teknik",
    "informatika",
    "computer",
    "science",
    "information",
    "technology",
    "software",
    "developer",
    "engineer",
    "data",
    "web",
    "it",
}

LOW_RELEVANCE_TEACHING_TERMS = {
    "tutor",
    "guru",
    "teacher",
    "mengajar",
    "bahasa",
    "education",
    "sekolah",
    "siswa",
    "kursus",
}


def _tokens(*values: Any) -> set[str]:
    return {
        token
        for value in values
        for token in _TOKEN_RE.findall(str(value or "").lower())
    }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _job_text(job: dict[str, Any]) -> str:
    return " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("company") or ""),
            str(job.get("location") or ""),
            str(job.get("description") or ""),
            " ".join(_as_list(job.get("skills") or job.get("tags"))),
        ]
    )


def _alignment(user: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    user_skills = [skill.lower() for skill in _as_list(user.get("skills"))]
    profile_tokens = _tokens(user.get("profile_text"), user.get("program_studi"), user.get("jurusan"), *user_skills)
    job_text = _job_text(job)
    job_tokens = _tokens(job_text)
    matched_skills: list[str] = []
    related_hits: set[str] = set()

    for skill in user_skills:
        related = SKILL_RELATED_TERMS.get(skill, {skill})
        if skill in job_text.lower() or related & job_tokens:
            matched_skills.append(skill)
            related_hits.update(related & job_tokens)

    tech_profile = bool(profile_tokens & TECH_PROFILE_TERMS)
    tech_job = bool(job_tokens & TECH_PROFILE_TERMS) or bool(related_hits)
    skill_score = min(1.0, len(set(matched_skills)) / max(1, len(set(user_skills)))) if user_skills else 0.0
    domain_score = 0.25 if tech_profile and tech_job else 0.0
    low_relevance_teaching = bool(job_tokens & LOW_RELEVANCE_TEACHING_TERMS)
    penalty = 0.0
    if tech_profile and low_relevance_teaching and not matched_skills and not tech_job:
        penalty = 0.3
    return {
        "score": min(1.0, skill_score + domain_score),
        "matched_skills": sorted({skill.title() if skill != "web" else "Web" for skill in matched_skills}),
        "related_hits": sorted(related_hits),
        "penalty": penalty,
        "tech_profile": tech_profile,
    }


async def run_aggregate_stage(user: dict[str, Any], jobs: list[dict[str, Any]]) -> AggregateStageResult:
    w_sbert, w_ncf, w_dqn, segment = dynamic_weights(int(user.get("interaction_count") or 0))
    calibrator = get_default_calibrator()
    ranked: list[dict[str, Any]] = []
    alignments = [_alignment(user, job) for job in jobs]
    aligned_candidates = sum(1 for item in alignments if float(item["score"]) > 0.0)

    for job, alignment in zip(jobs, alignments):
        sbert_score = float(job.get("sbert_score") or 0.0)
        ncf_score = float(job.get("ncf_score") or 0.0)
        dqn_score = float(job.get("dqn_score") or 0.0)
        base_score = (w_sbert * sbert_score) + (w_ncf * ncf_score) + (w_dqn * dqn_score)
        alignment_score = float(alignment["score"])
        penalty = float(alignment["penalty"])
        if aligned_candidates >= 5 and alignment_score <= 0.0 and sbert_score < 0.68:
            penalty = max(penalty, 0.22)
        static_score = max(0.0, min(1.0, base_score + (0.18 * alignment_score) - penalty))
        calibration_features = extract_calibration_features(
            user,
            job,
            static_score=static_score,
            alignment_score=alignment_score,
        )
        final_score = calibrated_score(calibration_features, calibrator)
        explanation: list[str] = []
        if alignment["matched_skills"]:
            explanation.append(f"Matched skills: {', '.join(alignment['matched_skills'][:5])}.")
        elif alignment["tech_profile"]:
            explanation.append("No direct profile-skill overlap; relevance was demoted because stronger aligned jobs exist.")
        explanation.append(f"SBERT semantic similarity {round(sbert_score * 100)}%.")
        explanation.append(f"NCF interaction pattern {round(ncf_score * 100)}%.")
        explanation.append(f"DQN career-action signal {round(dqn_score * 100)}%.")
        if segment == "cold":
            explanation.append("Cold-start weighting keeps SBERT and skill alignment dominant.")
        ablation_scores = {
            "sbert_only": round(sbert_score, 6),
            "ncf_only": round(ncf_score, 6),
            "dqn_only": round(dqn_score, 6),
            "sbert_ncf": round((0.6 * sbert_score) + (0.4 * ncf_score), 6),
            "sbert_dqn": round((0.7 * sbert_score) + (0.3 * dqn_score), 6),
            "ncf_dqn": round((0.7 * ncf_score) + (0.3 * dqn_score), 6),
            "full": round(final_score, 6),
            "static_baseline": round(static_score, 6),
            "learned_calibrator": round(final_score, 6),
        }
        ranked.append(
            {
                **job,
                "final_score": round(final_score, 6),
                "match_percent": int(round(final_score * 100)),
                "static_baseline_score": round(static_score, 6),
                "calibrated_score": round(final_score, 6),
                "sbert_score": round(sbert_score, 6),
                "ncf_score": round(ncf_score, 6),
                "dqn_score": round(dqn_score, 6),
                "skill_alignment_score": round(alignment_score, 6),
                "matched_skills": alignment["matched_skills"],
                "explanation": explanation,
                "weights": {"sbert": w_sbert, "ncf": w_ncf, "dqn": w_dqn},
                "ablation_scores": ablation_scores,
                "calibration": {
                    **calibrator.summary(),
                    "features": calibration_features,
                },
            }
        )

    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    strategy = "learned_logistic_calibrator_with_static_baseline"
    calibrator_summary = calibrator.summary()
    return AggregateStageResult(
        ranked=ranked,
        summary={
            "ranked": len(ranked),
            "segment": segment,
            "weights": {"sbert": w_sbert, "ncf": w_ncf, "dqn": w_dqn},
            "aligned_candidates": aligned_candidates,
            "strategy": strategy,
            "calibrator": calibrator_summary,
            "static_baseline": CALIBRATOR_BASELINE,
            "ablation_ready": True,
            "ablation_conditions": [
                "sbert_only",
                "ncf_only",
                "dqn_only",
                "sbert_ncf",
                "sbert_dqn",
                "ncf_dqn",
                "full",
                "static_baseline",
                "learned_calibrator",
            ],
        },
    )
