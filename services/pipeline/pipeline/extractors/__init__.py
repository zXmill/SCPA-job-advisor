"""Structured text extractors for job postings."""

from .contacts import extract_contacts
from .experience import extract_experience
from .job_type import detect_job_type
from .mode import extract_employment_mode
from .salary import SalaryResult, extract_salary
from .skills import canonical_skill_count, extract_skills
from .taxonomy import extract_taxonomy_terms, upsert_taxonomy

__all__ = [
    "SalaryResult",
    "canonical_skill_count",
    "detect_job_type",
    "extract_contacts",
    "extract_employment_mode",
    "extract_experience",
    "extract_salary",
    "extract_skills",
    "extract_taxonomy_terms",
    "upsert_taxonomy",
]
