"""Build a labeled Indonesian profile-job pair dataset for SBERT fine-tuning.

Produces realistic Indonesian academic profiles matched with job vacancies
from local portals. Each record includes positive pairs, hard negatives,
skill annotations, and deterministic train/validation/test splits.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


# ════════════════════════════════════════════════════════════════
# Dataset definitions
# ════════════════════════════════════════════════════════════════

_PROFILES: list[dict[str, Any]] = [
    {
        "profile_id": "u-ti-01",
        "program_studi": "Teknik Informatika",
        "university": "Institut Teknologi Bandung",
        "skills": ["python", "fastapi", "postgresql", "docker", "redis", "api"],
        "target_role": "Backend Developer",
    },
    {
        "profile_id": "u-ti-02",
        "program_studi": "Teknik Informatika",
        "university": "Universitas Indonesia",
        "skills": ["javascript", "react", "typescript", "css", "frontend"],
        "target_role": "Frontend Developer",
    },
    {
        "profile_id": "u-si-01",
        "program_studi": "Sistem Informasi",
        "university": "Universitas Gadjah Mada",
        "skills": ["sql", "excel", "dashboard", "business analysis", "presentation"],
        "target_role": "Business Analyst",
    },
    {
        "profile_id": "u-si-02",
        "program_studi": "Sistem Informasi",
        "university": "Universitas Airlangga",
        "skills": ["python", "sql", "statistics", "pandas", "machine learning"],
        "target_role": "Data Analyst",
    },
    {
        "profile_id": "u-sasing-01",
        "program_studi": "Sastra Inggris",
        "university": "Universitas Negeri Malang",
        "skills": ["english", "content writing", "public speaking", "event hosting"],
        "target_role": "Content Writer",
    },
    {
        "profile_id": "u-sasing-02",
        "program_studi": "Sastra Inggris",
        "university": "Universitas Padjadjaran",
        "skills": ["english", "indonesian", "translation", "copywriting"],
        "target_role": "Translator",
    },
    {
        "profile_id": "u-manajemen-01",
        "program_studi": "Manajemen",
        "university": "Universitas Indonesia",
        "skills": ["presentation", "excel", "business analysis", "communication"],
        "target_role": "Marketing Specialist",
    },
    {
        "profile_id": "u-manajemen-02",
        "program_studi": "Manajemen",
        "university": "Universitas Brawijaya",
        "skills": ["communication", "presentation", "excel", "stakeholder management"],
        "target_role": "HR Specialist",
    },
    {
        "profile_id": "u-akuntansi-01",
        "program_studi": "Akuntansi",
        "university": "Universitas Indonesia",
        "skills": ["excel", "sql", "dashboard", "financial analysis"],
        "target_role": "Financial Analyst",
    },
    {
        "profile_id": "u-akuntansi-02",
        "program_studi": "Akuntansi",
        "university": "Universitas Gadjah Mada",
        "skills": ["excel", "statistics", "business analysis", "presentation"],
        "target_role": "Auditor",
    },
    {
        "profile_id": "u-psikologi-01",
        "program_studi": "Psikologi",
        "university": "Universitas Airlangga",
        "skills": ["communication", "presentation", "research", "statistics"],
        "target_role": "HR Recruiter",
    },
    {
        "profile_id": "u-psikologi-02",
        "program_studi": "Psikologi",
        "university": "Universitas Padjadjaran",
        "skills": ["communication", "research", "statistics", "counseling"],
        "target_role": "Counselor",
    },
    {
        "profile_id": "u-dkv-01",
        "program_studi": "Desain Komunikasi Visual",
        "university": "Institut Teknologi Sepuluh Nopember",
        "skills": ["figma", "ui design", "ux research", "prototyping"],
        "target_role": "UI/UX Designer",
    },
    {
        "profile_id": "u-dkv-02",
        "program_studi": "Desain Komunikasi Visual",
        "university": "Universitas Negeri Semarang",
        "skills": ["figma", "design", "prototyping", "ui ux design"],
        "target_role": "Graphic Designer",
    },
    {
        "profile_id": "u-elektro-01",
        "program_studi": "Teknik Elektro",
        "university": "Institut Teknologi Bandung",
        "skills": ["python", "machine learning", "cloud", "docker"],
        "target_role": "IoT Engineer",
    },
    {
        "profile_id": "u-hukum-01",
        "program_studi": "Hukum",
        "university": "Universitas Indonesia",
        "skills": ["research", "communication", "presentation", "analysis"],
        "target_role": "Legal Officer",
    },
    {
        "profile_id": "u-kedokteran-01",
        "program_studi": "Kedokteran",
        "university": "Universitas Gadjah Mada",
        "skills": ["research", "communication", "statistics", "presentation"],
        "target_role": "Medical Researcher",
    },
    {
        "profile_id": "u-ti-03",
        "program_studi": "Teknik Informatika",
        "university": "Universitas Hasanuddin",
        "skills": ["python", "machine learning", "pandas", "sql", "statistics"],
        "target_role": "Data Scientist",
    },
    {
        "profile_id": "u-ti-04",
        "program_studi": "Teknik Informatika",
        "university": "Universitas Diponegoro",
        "skills": ["docker", "kubernetes", "ci cd", "cloud", "python"],
        "target_role": "DevOps Engineer",
    },
    {
        "profile_id": "u-si-03",
        "program_studi": "Sistem Informasi",
        "university": "Universitas Kristen Petra",
        "skills": ["python", "api", "fastapi", "postgresql", "docker"],
        "target_role": "Backend Developer",
    },
]

_JOBS: list[dict[str, Any]] = [
    {
        "job_id": "job-backend-001",
        "title": "Backend Developer",
        "company": "PT Teknologi Nusantara",
        "location": "Jakarta Selatan",
        "description": "Develop REST API microservices using Python FastAPI, design PostgreSQL schemas, implement Redis caching, and manage Docker deployment workflows.",
        "skills": ["python", "fastapi", "postgresql", "docker", "redis", "api"],
    },
    {
        "job_id": "job-frontend-001",
        "title": "Frontend Developer",
        "company": "PT Digital Kreasi",
        "location": "Bandung",
        "description": "Build responsive web interfaces with React and TypeScript, implement CSS animations, and integrate with REST APIs.",
        "skills": ["javascript", "react", "typescript", "css", "frontend", "api"],
    },
    {
        "job_id": "job-ba-001",
        "title": "Business Analyst",
        "company": "PT Solusi Bisnis Digital",
        "location": "Jakarta Pusat",
        "description": "Analyze business operations, build SQL dashboards, document requirements, and support product decisions with data-driven insights.",
        "skills": ["sql", "excel", "dashboard", "business analysis", "presentation"],
    },
    {
        "job_id": "job-da-001",
        "title": "Data Analyst",
        "company": "PT Analitika Indonesia",
        "location": "Surabaya",
        "description": "Analyze product data with SQL and Python, build dashboards, and present statistical findings to stakeholders.",
        "skills": ["python", "sql", "statistics", "pandas", "dashboard", "presentation"],
    },
    {
        "job_id": "job-cw-001",
        "title": "Content Writer",
        "company": "PT Media Edukasi Indonesia",
        "location": "Surabaya",
        "description": "Write course scripts, public relations articles, and social media content in English and Indonesian.",
        "skills": ["content writing", "copywriting", "english", "indonesian"],
    },
    {
        "job_id": "job-translator-001",
        "title": "English Translator",
        "company": "PT Lingua Nusantara",
        "location": "Remote Indonesia",
        "description": "Translate English articles, edit learning materials, and localize course scripts for Indonesian users.",
        "skills": ["content writing", "english", "indonesian", "translation"],
    },
    {
        "job_id": "job-marketing-001",
        "title": "Marketing Specialist",
        "company": "PT Brand Nusantara",
        "location": "Jakarta Barat",
        "description": "Plan digital marketing campaigns, analyze market trends, and coordinate with creative teams for product launches.",
        "skills": ["presentation", "excel", "business analysis", "communication", "content writing"],
    },
    {
        "job_id": "job-hr-001",
        "title": "HR Specialist",
        "company": "PT Sumber Daya Manusia",
        "location": "Tangerang",
        "description": "Manage recruitment pipelines, conduct interviews, and maintain employee relations with data-driven HR processes.",
        "skills": ["communication", "presentation", "excel", "research", "statistics"],
    },
    {
        "job_id": "job-fa-001",
        "title": "Financial Analyst",
        "company": "PT Keuangan Mandiri",
        "location": "Jakarta Selatan",
        "description": "Build financial models, analyze investment opportunities, and create dashboards for executive decision-making.",
        "skills": ["excel", "sql", "dashboard", "statistics", "business analysis"],
    },
    {
        "job_id": "job-auditor-001",
        "title": "Internal Auditor",
        "company": "PT Audit Indonesia",
        "location": "Jakarta Pusat",
        "description": "Review financial records, assess compliance, and prepare audit reports for regulatory submissions.",
        "skills": ["excel", "statistics", "business analysis", "presentation"],
    },
    {
        "job_id": "job-recruiter-001",
        "title": "Talent Acquisition Specialist",
        "company": "PT Rekrutmen Digital",
        "location": "Jakarta Selatan",
        "description": "Source candidates, conduct interviews, and manage hiring pipelines using ATS and data analytics.",
        "skills": ["communication", "research", "presentation", "statistics", "excel"],
    },
    {
        "job_id": "job-counselor-001",
        "title": "Career Counselor",
        "company": "PT Bimbing Karir",
        "location": "Yogyakarta",
        "description": "Provide career guidance, conduct counseling sessions, and develop personal development plans for clients.",
        "skills": ["communication", "research", "counseling", "presentation"],
    },
    {
        "job_id": "job-uiux-001",
        "title": "UI/UX Designer",
        "company": "PT Kreasi Produk Digital",
        "location": "Yogyakarta",
        "description": "Conduct user research, design Figma prototypes, and collaborate with product teams on web and mobile interfaces.",
        "skills": ["figma", "prototyping", "ui design", "ux research", "ui ux design"],
    },
    {
        "job_id": "job-gd-001",
        "title": "Graphic Designer",
        "company": "PT Visual Nusantara",
        "location": "Malang",
        "description": "Create visual designs for marketing materials, social media, and brand identity using design tools.",
        "skills": ["figma", "design", "prototyping", "ui design"],
    },
    {
        "job_id": "job-iot-001",
        "title": "IoT Engineer",
        "company": "PT Smart Devices Indonesia",
        "location": "Bandung",
        "description": "Develop firmware for embedded devices, build IoT cloud pipelines, and optimize sensor data processing.",
        "skills": ["python", "machine learning", "cloud", "docker", "api"],
    },
    {
        "job_id": "job-legal-001",
        "title": "Legal Officer",
        "company": "PT Hukum & Konsultan",
        "location": "Jakarta Selatan",
        "description": "Draft legal contracts, review compliance documents, and provide legal advisory for corporate transactions.",
        "skills": ["research", "communication", "presentation", "business analysis"],
    },
    {
        "job_id": "job-medical-001",
        "title": "Medical Research Coordinator",
        "company": "RS Umum Pusat",
        "location": "Jakarta Pusat",
        "description": "Coordinate clinical trials, analyze medical data, and prepare research publications for peer review.",
        "skills": ["research", "communication", "statistics", "presentation"],
    },
    {
        "job_id": "job-ds-001",
        "title": "Data Scientist",
        "company": "PT AI Nusantara",
        "location": "Jakarta Selatan",
        "description": "Build machine learning models, analyze product data with SQL and Python, and present experiment results to stakeholders.",
        "skills": ["python", "machine learning", "pandas", "sql", "statistics", "dashboard"],
    },
    {
        "job_id": "job-devops-001",
        "title": "DevOps Engineer",
        "company": "PT Cloud Rakyat",
        "location": "Bandung",
        "description": "Operate Docker, Kubernetes, CI/CD pipelines, cloud monitoring, and infrastructure automation for product teams.",
        "skills": ["docker", "kubernetes", "ci cd", "cloud", "python"],
    },
    {
        "job_id": "job-backend-002",
        "title": "Backend Developer",
        "company": "PT Startup Teknologi",
        "location": "Remote Indonesia",
        "description": "Develop scalable APIs using Python and FastAPI, manage PostgreSQL databases, and deploy services with Docker.",
        "skills": ["python", "fastapi", "postgresql", "docker", "api"],
    },
    {
        "job_id": "job-mobile-001",
        "title": "Mobile Developer",
        "company": "PT Aplikasi Mandiri",
        "location": "Depok",
        "description": "Build Flutter mobile features, integrate APIs, and collaborate with backend engineers on product delivery.",
        "skills": ["flutter", "api", "mobile development", "python"],
    },
    {
        "job_id": "job-sre-001",
        "title": "Site Reliability Engineer",
        "company": "PT Infrastruktur Digital",
        "location": "Jakarta Selatan",
        "description": "Monitor system reliability, automate incident response, and optimize cloud infrastructure performance.",
        "skills": ["docker", "kubernetes", "cloud", "python", "api"],
    },
    {
        "job_id": "job-ml-001",
        "title": "Machine Learning Engineer",
        "company": "PT AI Terapan",
        "location": "Jakarta Selatan",
        "description": "Deploy ML models to production, build data pipelines, and optimize inference latency for real-time applications.",
        "skills": ["python", "machine learning", "pandas", "sql", "cloud", "docker"],
    },
    {
        "job_id": "job-mc-001",
        "title": "Master of Ceremony",
        "company": "PT Event Nusantara",
        "location": "Jakarta",
        "description": "Host corporate events, moderate panel discussions, and represent brands at national product launches.",
        "skills": ["english", "event hosting", "public speaking", "communication"],
    },
]

# Hand-curated positive pairs (profile_id -> list of job_ids)
_POSITIVE_MATCHES: dict[str, list[str]] = {
    "u-ti-01": ["job-backend-001", "job-backend-002"],
    "u-ti-02": ["job-frontend-001"],
    "u-si-01": ["job-ba-001"],
    "u-si-02": ["job-da-001", "job-ds-001"],
    "u-sasing-01": ["job-cw-001", "job-mc-001"],
    "u-sasing-02": ["job-translator-001", "job-cw-001"],
    "u-manajemen-01": ["job-marketing-001"],
    "u-manajemen-02": ["job-hr-001", "job-recruiter-001"],
    "u-akuntansi-01": ["job-fa-001"],
    "u-akuntansi-02": ["job-auditor-001"],
    "u-psikologi-01": ["job-recruiter-001", "job-hr-001"],
    "u-psikologi-02": ["job-counselor-001"],
    "u-dkv-01": ["job-uiux-001"],
    "u-dkv-02": ["job-gd-001"],
    "u-elektro-01": ["job-iot-001"],
    "u-hukum-01": ["job-legal-001"],
    "u-kedokteran-01": ["job-medical-001"],
    "u-ti-03": ["job-ds-001", "job-ml-001"],
    "u-ti-04": ["job-devops-001", "job-sre-001"],
    "u-si-03": ["job-backend-001", "job-backend-002"],
}

# Negative pairs: explicitly poor matches for contrastive learning
_NEGATIVE_MATCHES: dict[str, list[str]] = {
    "u-ti-01": ["job-mc-001", "job-translator-001", "job-counselor-001"],
    "u-ti-02": ["job-mc-001", "job-translator-001", "job-auditor-001"],
    "u-si-01": ["job-mc-001", "job-translator-001", "job-iot-001"],
    "u-si-02": ["job-mc-001", "job-legal-001", "job-counselor-001"],
    "u-sasing-01": ["job-backend-001", "job-iot-001", "job-ds-001"],
    "u-sasing-02": ["job-backend-001", "job-iot-001", "job-devops-001"],
    "u-manajemen-01": ["job-backend-001", "job-iot-001", "job-ds-001"],
    "u-manajemen-02": ["job-backend-001", "job-iot-001", "job-ds-001"],
    "u-akuntansi-01": ["job-mc-001", "job-iot-001", "job-counselor-001"],
    "u-akuntansi-02": ["job-mc-001", "job-iot-001", "job-translator-001"],
    "u-psikologi-01": ["job-backend-001", "job-iot-001", "job-ds-001"],
    "u-psikologi-02": ["job-backend-001", "job-iot-001", "job-ds-001"],
    "u-dkv-01": ["job-mc-001", "job-backend-001", "job-ds-001"],
    "u-dkv-02": ["job-mc-001", "job-backend-001", "job-ds-001"],
    "u-elektro-01": ["job-mc-001", "job-translator-001", "job-counselor-001"],
    "u-hukum-01": ["job-mc-001", "job-backend-001", "job-iot-001"],
    "u-kedokteran-01": ["job-mc-001", "job-backend-001", "job-iot-001"],
    "u-ti-03": ["job-mc-001", "job-translator-001", "job-counselor-001"],
    "u-ti-04": ["job-mc-001", "job-translator-001", "job-counselor-001"],
    "u-si-03": ["job-mc-001", "job-translator-001", "job-counselor-001"],
}


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════

def _profile_text(profile: dict[str, Any]) -> str:
    parts = [
        profile.get("program_studi"),
        profile.get("target_role"),
        " ".join(profile.get("skills", [])),
    ]
    return " ".join(p for p in parts if p)


def _job_text(job: dict[str, Any]) -> str:
    parts = [
        job.get("title"),
        job.get("company"),
        job.get("location"),
        job.get("description"),
        " ".join(job.get("skills", [])),
    ]
    return " ".join(p for p in parts if p)


def _matched_skills(profile_skills: list[str], job_skills: list[str]) -> list[str]:
    ps = {s.lower() for s in profile_skills}
    js = {s.lower() for s in job_skills}
    return sorted(ps & js)


def _pair_id(profile_id: str, job_id: str) -> str:
    return f"{profile_id}__{job_id}"


def _job_by_id(jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {job["job_id"]: job for job in jobs}


def _split_counts(size: int) -> dict[str, int]:
    if size < 3:
        return {"train": size, "validation": 0, "test": 0}
    validation = max(1, round(size * 0.15))
    test = max(1, round(size * 0.15))
    while validation + test >= size:
        if validation >= test and validation > 0:
            validation -= 1
        elif test > 0:
            test -= 1
    return {"train": size - validation - test, "validation": validation, "test": test}


def _assign_splits(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = _split_counts(len(records))
    ordered_ids = sorted(str(r["pair_id"]) for r in records)
    split_by_id: dict[str, str] = {}
    cursor = 0
    for split in ("test", "validation", "train"):
        count = counts[split]
        for pair_id in ordered_ids[cursor:cursor + count]:
            split_by_id[pair_id] = split
        cursor += count
    for r in records:
        r["split"] = split_by_id[str(r["pair_id"])]
    return records


# ════════════════════════════════════════════════════════════════
# Build dataset
# ════════════════════════════════════════════════════════════════

def build_dataset() -> list[dict[str, Any]]:
    """Build all labeled Indonesian profile-job pair records."""

    job_map = _job_by_id(_JOBS)
    records: list[dict[str, Any]] = []
    all_pair_ids: set[str] = set()

    for profile in _PROFILES:
        profile_id = profile["profile_id"]
        profile_text = _profile_text(profile)
        profile_skills = list(profile.get("skills", []))

        # Positive pairs
        for job_id in _POSITIVE_MATCHES.get(profile_id, []):
            job = job_map[job_id]
            pair_id = _pair_id(profile_id, job_id)
            if pair_id in all_pair_ids:
                continue
            all_pair_ids.add(pair_id)
            job_skills = list(job.get("skills", []))
            records.append({
                "pair_id": pair_id,
                "pair_kind": "positive",
                "profile_id": profile_id,
                "job_id": job_id,
                "profile_text": profile_text,
                "job_text": _job_text(job),
                "profile_skills": profile_skills,
                "job_skills": job_skills,
                "matched_skills": _matched_skills(profile_skills, job_skills),
                "label": 1.0,
                "source_event": "apply",
                "source_label": 1.0,
                "provenance": "indonesian_profile_job_dataset_v1",
            })

        # Negative pairs
        for job_id in _NEGATIVE_MATCHES.get(profile_id, []):
            job = job_map[job_id]
            pair_id = _pair_id(profile_id, job_id)
            if pair_id in all_pair_ids:
                continue
            all_pair_ids.add(pair_id)
            job_skills = list(job.get("skills", []))
            records.append({
                "pair_id": pair_id,
                "pair_kind": "negative",
                "profile_id": profile_id,
                "job_id": job_id,
                "profile_text": profile_text,
                "job_text": _job_text(job),
                "profile_skills": profile_skills,
                "job_skills": job_skills,
                "matched_skills": _matched_skills(profile_skills, job_skills),
                "label": 0.0,
                "source_event": "skip",
                "source_label": 0.0,
                "provenance": "indonesian_profile_job_dataset_v1",
            })

    # Add hard negatives for positive pairs
    for profile in _PROFILES:
        profile_id = profile["profile_id"]
        positive_job_ids = set(_POSITIVE_MATCHES.get(profile_id, []))
        negative_job_ids = set(_NEGATIVE_MATCHES.get(profile_id, []))
        profile_text = _profile_text(profile)
        profile_skills = set(s.lower() for s in profile.get("skills", []))

        # Find hard negative: same general domain but poor skill overlap
        for pos_job_id in positive_job_ids:
            pos_job = job_map[pos_job_id]
            pos_skills = set(s.lower() for s in pos_job.get("skills", []))

            best_hard_negative = None
            best_score = -1.0
            for neg_job_id in negative_job_ids:
                neg_job = job_map[neg_job_id]
                neg_skills = set(s.lower() for s in neg_job.get("skills", []))
                # Hard negative should have some overlap but not too much
                overlap = len(profile_skills & neg_skills)
                pos_overlap = len(pos_skills & neg_skills)
                score = overlap + pos_overlap * 0.5
                if score > best_score:
                    best_score = score
                    best_hard_negative = neg_job

            if best_hard_negative:
                pair_id = _pair_id(profile_id, pos_job_id)
                for r in records:
                    if r["pair_id"] == pair_id and r["pair_kind"] == "positive":
                        r["hard_negative_job_id"] = best_hard_negative["job_id"]
                        r["hard_negative_text"] = _job_text(best_hard_negative)
                        r["hard_negative_skills"] = list(best_hard_negative.get("skills", []))
                        break

    # Assign deterministic splits
    records = _assign_splits(records)
    return records


def write_dataset(records: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("services/sbert/training/data/indonesian_profile_job_pairs.jsonl"),
    )
    args = parser.parse_args()
    records = build_dataset()
    write_dataset(records, args.output)
    split_counts = {"train": 0, "validation": 0, "test": 0}
    for r in records:
        split_counts[r["split"]] += 1
    print(f"Wrote {len(records)} records to {args.output}")
    print(f"  Splits: {split_counts}")
    print(f"  Positive: {sum(1 for r in records if r['pair_kind'] == 'positive')}")
    print(f"  Negative: {sum(1 for r in records if r['pair_kind'] == 'negative')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
