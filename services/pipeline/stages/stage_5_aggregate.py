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
from services.shared.skill_taxonomy import normalize_skill_term, skill_alias_mapping


@dataclass
class AggregateStageResult:
    ranked: list[dict[str, Any]]
    summary: dict[str, Any]


def dynamic_weights(interaction_count: int, *, dqn_available: bool = True) -> tuple[float, float, float, str]:
    if interaction_count <= 0:
        return 0.8, 0.2, 0.0, "cold_start"
    if not dqn_available:
        return 0.6, 0.4, 0.0, "fallback_no_session_events"
    if interaction_count <= 20:
        return 0.55, 0.35, 0.1, "warm_user"
    return 0.45, 0.35, 0.2, "active_session"


def _validate_weights(alpha: float, beta: float, gamma: float) -> None:
    if abs((alpha + beta + gamma) - 1.0) > 1e-9:
        raise ValueError("hybrid scoring weights must sum to 1.0")


_TOKEN_RE = re.compile(r"[a-z0-9+#.]+")
SKILL_ALIASES: dict[str, set[str]] = skill_alias_mapping()
ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in SKILL_ALIASES.items()
    for alias in aliases
}

SKILL_RELATED_TERMS: dict[str, set[str]] = {
    "python": {"python", "fastapi", "django", "flask", "pandas", "numpy"},
    "react": {"react", "reactjs", "react.js", "nextjs", "next.js", "frontend", "javascript", "typescript"},
    "web": {"web", "frontend", "front-end", "html", "css", "javascript", "typescript", "react", "nextjs", "node"},
    "sql": {"sql", "postgresql", "postgres", "mysql", "sql server", "structured query language"},
    "machine learning": {"machine learning", "ml", "pytorch", "tensorflow", "scikit learn", "scikit-learn", "mlops"},
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
    "web",
    "it",
}

TECH_JOB_TERMS = {
    "api",
    "backend",
    "developer",
    "devops",
    "engineer",
    "frontend",
    "it",
    "machine",
    "ml",
    "mobile",
    "programmer",
    "software",
    "web",
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


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    if len(term) <= 2 and term not in {"ai", "go"}:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _canonical_skill_key(value: Any) -> str:
    key = normalize_skill_term(value)
    canonical = ALIAS_TO_CANONICAL.get(key)
    return normalize_skill_term(canonical) if canonical else key


def _aliases_for_skill(value: Any) -> set[str]:
    key = normalize_skill_term(value)
    canonical = ALIAS_TO_CANONICAL.get(key)
    if canonical is None:
        for name in SKILL_ALIASES:
            if normalize_skill_term(name) == key:
                canonical = name
                break
    aliases = set(SKILL_ALIASES.get(canonical or "", set()))
    aliases.add(key)
    return {alias for alias in aliases if alias}


def _job_skill_signal_terms(job: dict[str, Any]) -> set[str]:
    fields = (
        "required_skills",
        "required_skill_names",
        "preferred_skills",
        "preferred_skill_names",
        "extracted_skills",
        "extracted_skill_names",
        "skills",
    )
    terms: set[str] = set()
    for field in fields:
        for value in _as_list(job.get(field)):
            key = normalize_skill_term(value)
            if not key:
                continue
            terms.add(key)
            canonical = ALIAS_TO_CANONICAL.get(key)
            if canonical:
                terms.add(normalize_skill_term(canonical))
                terms.update(SKILL_ALIASES.get(canonical, set()))
    return terms


def _job_text(job: dict[str, Any]) -> str:
    return " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("company") or ""),
            str(job.get("location") or ""),
            str(job.get("description_text") or job.get("description") or ""),
            " ".join(_as_list(job.get("description_sections"))),
            " ".join(_as_list(job.get("responsibilities"))),
            " ".join(_as_list(job.get("requirements"))),
            " ".join(_as_list(job.get("skills"))),
        ]
    )


def _alignment(user: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    user_skills = _as_list(user.get("skills"))
    profile_tokens = _tokens(user.get("profile_text"), user.get("program_studi"), user.get("jurusan"), *user_skills)
    job_text = _job_text(job)
    job_text_norm = normalize_skill_term(job_text)
    job_tokens = _tokens(job_text)
    job_signal_terms = _job_skill_signal_terms(job)
    matched_skills: list[str] = []
    related_hits: set[str] = set()
    matched_keys: set[str] = set()

    for skill in user_skills:
        skill_key = _canonical_skill_key(skill)
        aliases = _aliases_for_skill(skill)
        direct_match = any(
            alias in job_signal_terms or _contains_term(job_text_norm, alias)
            for alias in aliases
        )
        strict_related = SKILL_RELATED_TERMS.get(skill_key, set())
        strict_hits = {
            term for term in strict_related
            if term in job_signal_terms or _contains_term(job_text_norm, term)
        }
        if (direct_match or strict_hits) and skill_key not in matched_keys:
            matched_skills.append(skill)
            matched_keys.add(skill_key)
            related_hits.update(strict_hits)

    tech_profile = bool(profile_tokens & TECH_PROFILE_TERMS)
    tech_job = bool(job_tokens & TECH_JOB_TERMS) or bool(related_hits)
    skill_score = min(1.0, len(set(matched_skills)) / max(1, len(set(user_skills)))) if user_skills else 0.0
    domain_score = 0.25 if tech_profile and tech_job else 0.0
    low_relevance_teaching = bool(job_tokens & LOW_RELEVANCE_TEACHING_TERMS)
    penalty = 0.0
    if tech_profile and low_relevance_teaching and not matched_skills and not tech_job:
        penalty = 0.3
    elif tech_profile and not matched_skills and not tech_job:
        penalty = 0.28
    return {
        "score": min(1.0, skill_score + domain_score),
        "matched_skills": sorted({skill for skill in matched_skills}, key=lambda item: item.lower()),
        "related_hits": sorted(related_hits),
        "penalty": penalty,
        "tech_profile": tech_profile,
    }


async def run_aggregate_stage(user: dict[str, Any], jobs: list[dict[str, Any]]) -> AggregateStageResult:
    dqn_available = any(str(job.get("dqn_mode") or "session_rerank") == "session_rerank" for job in jobs)
    w_sbert, w_ncf, w_dqn, segment = dynamic_weights(
        int(user.get("interaction_count") or 0),
        dqn_available=dqn_available,
    )
    _validate_weights(w_sbert, w_ncf, w_dqn)
    calibrator = get_default_calibrator()
    ranked: list[dict[str, Any]] = []
    alignments = [_alignment(user, job) for job in jobs]
    aligned_candidates = sum(1 for item in alignments if float(item["score"]) > 0.0)
    scoring_formula = "final_score = alpha*sbert_score + beta*ncf_score + gamma*dqn_session_score"

    for job, alignment in zip(jobs, alignments):
        sbert_score = float(job.get("sbert_score") or 0.0)
        ncf_score = float(job.get("ncf_score") or 0.0)
        dqn_session_score = float(job.get("dqn_session_score", job.get("dqn_score") or 0.0) or 0.0)
        final_score = max(
            0.0,
            min(
                1.0,
                (w_sbert * sbert_score) + (w_ncf * ncf_score) + (w_dqn * dqn_session_score),
            ),
        )
        alignment_score = float(alignment["score"])
        penalty = float(alignment["penalty"])
        if aligned_candidates >= 5 and alignment_score <= 0.0 and sbert_score < 0.68:
            penalty = max(penalty, 0.22)
        calibration_features = extract_calibration_features(
            user,
            job,
            static_score=final_score,
            alignment_score=alignment_score,
        )
        separate_calibrated_score = calibrated_score(calibration_features, calibrator)
        explanation: list[str] = []
        if alignment["matched_skills"]:
            explanation.append(f"Matched skills: {', '.join(alignment['matched_skills'][:5])}.")
        elif alignment["tech_profile"]:
            explanation.append("No direct profile-skill overlap; skill alignment is reported separately from final score.")
        explanation.append(f"SBERT semantic similarity {round(sbert_score * 100)}%.")
        explanation.append(f"NCF interaction pattern {round(ncf_score * 100)}%.")
        explanation.append(f"DQN session signal {round(dqn_session_score * 100)}%.")
        if segment == "cold_start":
            explanation.append("Cold-start scoring sets DQN weight to zero.")
        ablation_scores = {
            "sbert_only": round(sbert_score, 6),
            "ncf_only": round(ncf_score, 6),
            "dqn_only": round(dqn_session_score, 6),
            "sbert_ncf": round((0.6 * sbert_score) + (0.4 * ncf_score), 6),
            "sbert_dqn": round((0.7 * sbert_score) + (0.3 * dqn_session_score), 6),
            "ncf_dqn": round((0.7 * ncf_score) + (0.3 * dqn_session_score), 6),
            "full": round(final_score, 6),
            "static_baseline": round(final_score, 6),
            "learned_calibrator": round(separate_calibrated_score, 6),
        }
        ranked.append(
            {
                **job,
                "final_score": round(final_score, 6),
                "match_percent": int(round(final_score * 100)),
                "static_baseline_score": round(final_score, 6),
                "calibrated_score": round(separate_calibrated_score, 6),
                "calibration_note": "calibrated_score is reported separately and is not mixed into final_score",
                "sbert_score": round(sbert_score, 6),
                "ncf_score": round(ncf_score, 6),
                "dqn_session_score": round(dqn_session_score, 6),
                "dqn_score": round(dqn_session_score, 6),
                "alpha": w_sbert,
                "beta": w_ncf,
                "gamma": w_dqn,
                "scoring_formula": scoring_formula,
                "scoring_mode": segment,
                "rank_before_dqn": job.get("rank_before_dqn"),
                "rank_after_dqn": job.get("rank_after_dqn"),
                "candidate_pool_source": job.get("candidate_pool_source"),
                "skill_alignment_score": round(alignment_score, 6),
                "skill_alignment_penalty": round(penalty, 6),
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
    for final_rank, item in enumerate(ranked, start=1):
        item["final_rank"] = final_rank
    strategy = "transparent_alpha_beta_gamma_hybrid_with_separate_calibration"
    calibrator_summary = calibrator.summary()
    return AggregateStageResult(
        ranked=ranked,
        summary={
            "ranked": len(ranked),
            "segment": segment,
            "scoring_mode": segment,
            "alpha": w_sbert,
            "beta": w_ncf,
            "gamma": w_dqn,
            "scoring_formula": scoring_formula,
            "weights": {"sbert": w_sbert, "ncf": w_ncf, "dqn": w_dqn},
            "weights_sum": round(w_sbert + w_ncf + w_dqn, 6),
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
