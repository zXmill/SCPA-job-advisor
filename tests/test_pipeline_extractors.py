"""Offline unit tests for the v2 pipeline extractor library.

These tests deliberately do NOT touch the network, the DB, Redis, or
Playwright. They exercise the pure-function extractors that turn
free-form Indonesian + English job text into structured signals
(salary, experience, employment mode, job type, skills, contacts).

Run with:
    pytest tests/test_pipeline_extractors.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the pipeline package importable without installing it.
_PIPELINE_SRC = Path(__file__).resolve().parents[1] / "services" / "pipeline"
if str(_PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_SRC))

from pipeline.extractors import (  # noqa: E402
    detect_job_type,
    extract_contacts,
    extract_employment_mode,
    extract_experience,
    extract_salary,
    extract_skills,
)
from pipeline.extractors.skills import canonical_skill_count  # noqa: E402
from pipeline.extractors.taxonomy import extract_taxonomy_terms  # noqa: E402
from pipeline.models import (  # noqa: E402
    NormalizedJob,
    RawJobPosting,
    build_dedupe_key,
    build_url_hash,
)
from pipeline.normalizer import normalize  # noqa: E402


# ════════════════════════════════════════════════════════════════
# Salary extraction
# ════════════════════════════════════════════════════════════════

class TestSalaryExtractor:
    def test_indonesian_range_juta(self):
        result = extract_salary("Gaji Rp 5 juta - 10 juta per bulan")
        assert result.has_value
        assert result.min_idr == 5_000_000
        assert result.max_idr == 10_000_000
        assert result.raw_currency == "IDR"
        assert result.raw_interval == "monthly"

    def test_indonesian_range_dotted_thousands(self):
        result = extract_salary("Rp 8.000.000 - Rp 12.000.000")
        assert result.min_idr == 8_000_000
        assert result.max_idr == 12_000_000

    def test_indonesian_short_form_jt(self):
        result = extract_salary("8jt - 15jt / bulan")
        assert result.min_idr == 8_000_000
        assert result.max_idr == 15_000_000

    def test_inherited_suffix(self):
        # "5-10 juta" -> both sides multiplied by 1_000_000
        result = extract_salary("Rentang 5 - 10 juta per bulan")
        assert result.min_idr == 5_000_000
        assert result.max_idr == 10_000_000

    def test_usd_yearly_normalised_to_monthly_idr(self):
        result = extract_salary("USD 60,000 - 90,000 / year")
        assert result.has_value
        # Yearly USD -> monthly IDR using the approximate rate.
        assert result.min_idr is not None and result.min_idr > 50_000_000
        assert result.max_idr is not None and result.max_idr > result.min_idr

    def test_negotiable_returns_no_value(self):
        result = extract_salary("Salary: Negotiable")
        assert not result.has_value
        assert result.confidence == 0.1

    def test_hint_short_circuit(self):
        result = extract_salary(
            "ignored body text", hint_min=10_000_000, hint_max=15_000_000,
            hint_currency="IDR", hint_interval="monthly",
        )
        assert result.min_idr == 10_000_000
        assert result.max_idr == 15_000_000
        assert result.confidence == 0.95

    def test_empty_text(self):
        assert not extract_salary(None).has_value
        assert not extract_salary("").has_value


class TestTaxonomyExtractor:
    def test_extract_taxonomy_terms_includes_canonical_skills(self):
        terms = extract_taxonomy_terms(
            "Dicari Data Analyst yang menguasai Python, SQL, dan bahasa Inggris.",
            top_n=5,
        )

        canonical = {
            term["skill"]
            for term in terms
            if term["source"] == "canonical"
        }
        assert {"Python", "SQL", "English"}.issubset(canonical)
        assert all("confidence" in term for term in terms)


# ════════════════════════════════════════════════════════════════
# Experience extraction
# ════════════════════════════════════════════════════════════════

class TestExperienceExtractor:
    def test_senior_from_title(self):
        assert extract_experience(None, title_hint="Senior Backend Engineer") == "senior"

    def test_junior_from_title(self):
        assert extract_experience(None, title_hint="Junior Data Analyst") == "entry"

    def test_year_range_mid(self):
        assert extract_experience(
            "We require 3-5 years of backend experience"
        ) == "mid"

    def test_year_range_senior(self):
        assert extract_experience(
            "Minimum 7 tahun pengalaman di bidang machine learning"
        ) == "senior"

    def test_intern_keyword(self):
        assert extract_experience("Open for internship / magang") == "entry"

    def test_unknown_returns_none(self):
        assert extract_experience("We hire great people") is None


# ════════════════════════════════════════════════════════════════
# Employment mode
# ════════════════════════════════════════════════════════════════

class TestEmploymentMode:
    def test_remote(self):
        assert extract_employment_mode("Fully remote position, WFH") == "remote"

    def test_hybrid_takes_precedence(self):
        # Description mentions both office and remote -> hybrid
        assert extract_employment_mode(
            "Hybrid setup: 2 days remote, 3 days in-office"
        ) == "hybrid"

    def test_onsite_via_wfo(self):
        assert extract_employment_mode("WFO di Jakarta") == "onsite"

    def test_location_hint_remote(self):
        assert extract_employment_mode(
            None, location_hint="Remote (Indonesia)"
        ) == "remote"

    def test_unknown(self):
        assert extract_employment_mode("Standard 9-to-5") is None


# ════════════════════════════════════════════════════════════════
# Job type
# ════════════════════════════════════════════════════════════════

class TestJobType:
    def test_internship(self):
        assert detect_job_type("3-month magang program") == "internship"

    def test_contract(self):
        assert detect_job_type("Freelance kontrak 6 bulan") == "contract"

    def test_full_time_via_hint(self):
        assert detect_job_type("ignored text", hint="Full-Time") == "full_time"

    def test_full_time_via_text(self):
        assert detect_job_type("Permanent / tetap") == "full_time"

    def test_unknown(self):
        assert detect_job_type("Looking for great talent") is None


# ════════════════════════════════════════════════════════════════
# Contacts
# ════════════════════════════════════════════════════════════════

class TestContactExtractor:
    def test_email_filtered_against_template_domains(self):
        text = "Send your CV to careers@realstartup.id or info@example.com"
        result = extract_contacts(text)
        assert "careers@realstartup.id" in result["emails"]
        assert "info@example.com" not in result["emails"]

    def test_id_phone_normalised(self):
        text = "Hubungi kami di +62 812-3456-7890 atau 081234567890"
        result = extract_contacts(text)
        assert any(p.startswith("+62812") for p in result["phones"])

    def test_max_results_cap(self):
        text = "Emails: a@x.id b@x.id c@x.id d@x.id e@x.id"
        result = extract_contacts(text, max_results=2)
        assert len(result["emails"]) == 2

    def test_empty(self):
        result = extract_contacts(None)
        assert result == {"emails": [], "phones": []}


# ════════════════════════════════════════════════════════════════
# Skills
# ════════════════════════════════════════════════════════════════

class TestSkills:
    def test_canonical_count_is_substantial(self):
        # Sanity check: the taxonomy should be >=400 entries.
        assert canonical_skill_count() >= 400

    def test_aliases_collapsed_to_canonical(self):
        text = "Looking for ReactJS + nextjs + nodejs + tailwindcss devs"
        skills = extract_skills(text)
        assert "React" in skills
        assert "Next.js" in skills
        assert "Node.js" in skills
        assert "Tailwind CSS" in skills

    def test_dedupe(self):
        text = "Python python PYTHON pandas Pandas"
        skills = extract_skills(text)
        assert skills.count("Python") == 1
        assert skills.count("Pandas") == 1

    def test_indonesian_text(self):
        skills = extract_skills(
            "Kandidat memahami pengembangan web dan analisis data dengan Python."
        )
        assert "Python" in skills
        # Indonesian alias entry exists but match is best-effort.

    def test_max_results_cap(self):
        text = "Python Java Go Rust Kotlin Swift Ruby PHP " * 10
        skills = extract_skills(text, max_results=3)
        assert len(skills) == 3

    def test_extra_hints_seeded(self):
        skills = extract_skills(
            "Backend role at scale", extra_hints=["PostgreSQL", "Redis"]
        )
        assert "PostgreSQL" in skills
        assert "Redis" in skills


# ════════════════════════════════════════════════════════════════
# Hashes (dedupe key + URL hash)
# ════════════════════════════════════════════════════════════════

class TestHashes:
    def test_dedupe_key_is_deterministic(self):
        a = build_dedupe_key("Senior Backend Engineer", "Tokopedia")
        b = build_dedupe_key("senior backend engineer", "TOKOPEDIA")
        assert a == b

    def test_dedupe_key_with_location(self):
        a = build_dedupe_key("Backend Engineer", "Gojek", "Jakarta")
        b = build_dedupe_key("Backend Engineer", "Gojek", "Bandung")
        assert a != b

    def test_url_hash_strips_query_and_fragment(self):
        a = build_url_hash("https://example.com/jobs/123?ref=abc")
        b = build_url_hash("https://example.com/jobs/123")
        c = build_url_hash("https://EXAMPLE.com/jobs/123#apply")
        assert a == b == c

    def test_url_hash_none_returns_none(self):
        assert build_url_hash(None) is None
        assert build_url_hash("") is None


# ════════════════════════════════════════════════════════════════
# Full normaliser pipeline
# ════════════════════════════════════════════════════════════════

class TestNormalizer:
    def test_indonesian_posting_end_to_end(self):
        raw = RawJobPosting(
            title="Senior Backend Engineer (Go)",
            company="Tokopedia",
            source="linkedin",
            location="Jakarta, Indonesia",
            description=(
                "We need a senior Go engineer with 5-7 years experience. "
                "Stack: Go, Kubernetes, gRPC, PostgreSQL, Redis. "
                "Hybrid arrangement, mostly WFH. Salary: Rp 25-40 juta/bulan. "
                "Send CV to careers@tokopedia.com or call +62812-3456-7890."
            ),
            salary_text="Rp 25 juta - 40 juta per bulan",
            apply_url="https://www.linkedin.com/jobs/view/123?ref=abc",
        )
        job = normalize(raw)

        assert isinstance(job, NormalizedJob)
        assert job.title == "Senior Backend Engineer (Go)"
        assert job.company == "Tokopedia"
        assert job.source == "linkedin"
        assert job.experience_level == "senior"
        assert job.employment_mode == "hybrid"
        assert job.min_salary == 25_000_000
        assert job.max_salary == 40_000_000
        assert job.salary_currency == "IDR"
        assert "Go" in job.skills
        assert "Kubernetes" in job.skills
        assert "PostgreSQL" in job.skills
        assert "Redis" in job.skills
        assert job.contact_email == "careers@tokopedia.com"
        assert job.contact_phone is not None
        assert job.contact_phone.startswith("+62")
        assert job.dedupe_key
        assert job.url_hash

    def test_minimal_posting_does_not_crash(self):
        raw = RawJobPosting(
            title="Junior Data Analyst",
            company="StartupX",
            source="glints",
        )
        job = normalize(raw)
        assert job.experience_level == "entry"
        assert job.employment_mode is None
        assert job.min_salary is None
        assert job.max_salary is None
        assert job.skills == []

    def test_remotive_payload(self):
        raw = RawJobPosting(
            title="DevOps Engineer",
            company="RemoteCo",
            source="remotive",
            location="Worldwide",
            description_html=(
                "<p>Requirements: <strong>AWS</strong>, Terraform, "
                "Kubernetes, GitHub Actions.</p>"
            ),
            employment_mode_hint="remote",
            job_type_hint="full_time",
        )
        job = normalize(raw)
        assert job.employment_mode == "remote"
        assert job.type == "full_time"
        assert "AWS" in job.skills
        assert "Terraform" in job.skills
        assert "Kubernetes" in job.skills
        # HTML stripped from description
        assert job.description is not None
        assert "<p>" not in job.description
        assert "<strong>" not in job.description


# ════════════════════════════════════════════════════════════════
# Dedupe store - in-memory backend
# ════════════════════════════════════════════════════════════════

@pytest.mark.anyio
class TestInMemoryDedupe:
    async def test_remember_then_seen(self):
        from pipeline.deduplication import InMemoryDedupeStore
        store = InMemoryDedupeStore(ttl_seconds=60)
        assert not await store.is_seen("abc")
        await store.remember("abc")
        assert await store.is_seen("abc")

    async def test_multiple_keys_any_match(self):
        from pipeline.deduplication import InMemoryDedupeStore
        store = InMemoryDedupeStore(ttl_seconds=60)
        await store.remember("k1")
        assert await store.is_seen("k1", "k2", "k3")  # k1 matches
        assert not await store.is_seen("k2", "k3")    # neither known

    async def test_stats_shape(self):
        from pipeline.deduplication import InMemoryDedupeStore
        store = InMemoryDedupeStore(ttl_seconds=60)
        await store.remember("x")
        await store.is_seen("x")
        stats = await store.stats()
        assert stats["backend"] == "memory"
        assert stats["size"] >= 1
        assert stats["hits"] >= 1
