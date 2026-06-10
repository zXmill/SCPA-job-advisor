"""Regression tests for rich job descriptions and skill signals."""

from __future__ import annotations

from fastapi.testclient import TestClient

from services.scraper.main import _job_item, _quality_filter_jobs, app as scraper_app
from services.shared.job_description import parse_job_description
from services.shared.skill_taxonomy import load_skill_seed


CBI_DESCRIPTION = """
Who We Are
PT Kredit Biro Indonesia Jaya (Credit Bureau Indonesia, CBI) is one of the
private credit bureaus in Indonesia and is licensed by Otoritas Jasa Keuangan.

Why Join Us
Innovative Environment: the team invests in artificial intelligence for
financial services. Impactful Work: shape the financial future of individuals
and businesses across Indonesia.

Role Overview
A Data Scientist builds and optimizes data-driven solutions by developing
machine learning models and maintaining end-to-end data science platforms,
including feature engineering, model training, deployment, and monitoring.

Job Responsibilities
Develop and maintain the fundamental platforms for the data science team,
including feature engineering, model training, and model monitoring. Upgrade
technical frameworks for model serving and code management. Conduct data
analysis and credit modeling tasks.

Job Requirements
Bachelor degree in Computer Science, Data Science, Statistics, or related
fields. Minimum 3 years of experience in Machine Learning Engineering, MLOps,
or related areas. Strong Python skills for automation, pipelines, and tooling;
familiar with Linux and database design. Hands-on experience with REST APIs,
Docker, Kubernetes, workflow orchestration tools (Airflow, Prefect), and Git.
Familiar with MLOps practices such as model versioning, lineage,
reproducibility, and observability. Experience in financial credit scoring
models is mandatory. Good English communication skills.

Nice to Have
Experience with feature stores, CI/CD, Terraform, or Helm. Familiarity with
risk models, financial data products, or model risk frameworks.

Seniority level Senior tingkat menengah
Employment type Penuh waktu
Job function Rekayasa, Teknologi Informasi
Industry Jasa Keuangan
"""

ASTRO_TRAINING_SUPERVISOR_DESCRIPTION = """
Role Overview
The Hub Mitra Training & Program Supervisor is responsible for ensuring the
effectiveness of mitra onboarding, training execution, and early-stage
engagement (1-30 days). This role plays a key part in maintaining mitra
retention, driving training excellence, and ensuring operational alignment
between training and operations teams.

Job Responsibilities
Mitra Onboarding & Retention Monitor and maintain newly onboarded mitra within
their first 1-30 days.
Ensure mitra turn rate remains below 10% through proactive engagement and issue
resolution.
Coordinate with Operations to ensure mitra scheduling accuracy, including
identifying and resolving unscheduled mitra cases.
Training Excellence & Quality Assurance Deliver and oversee training programs
to ensure high-quality learning experiences.
Achieve minimum training satisfaction score of 4.5/5.0.
Ensure post-test results reach a minimum average score of 90%.
Maintain training attendance rate above 75%.
Reporting & Performance Monitoring Prepare and submit accurate daily and
weekly performance reports.
Track key training and onboarding metrics to ensure targets are achieved.
Identify gaps and propose improvement initiatives based on data insights.
"""


def test_parse_cbi_job_description_extracts_sections_and_metadata() -> None:
    parsed = parse_job_description(CBI_DESCRIPTION)

    assert "credit bureaus" in parsed.description_sections["who_we_are"].lower()
    assert "machine learning models" in parsed.description_sections["role_overview"].lower()
    assert parsed.responsibilities
    assert parsed.requirements
    assert parsed.nice_to_have
    assert parsed.seniority_level == "Senior tingkat menengah"
    assert parsed.employment_type == "Penuh waktu"
    assert parsed.job_function == "Rekayasa, Teknologi Informasi"
    assert parsed.industry == "Jasa Keuangan"
    assert parsed.years_experience_min == 3


def test_scraper_job_item_derives_required_and_extracted_skills_from_full_description() -> None:
    job = _job_item(
        title="Data Scientist",
        company="CBI Credit Bureau Indonesia",
        location="South Jakarta, Indonesia",
        description=CBI_DESCRIPTION,
        tags=[],
        company_logo=None,
        source_url="https://www.linkedin.com/jobs/view/cbi-data-scientist",
        source="linkedin",
    )

    required = set(job.required_skills)
    extracted = set(job.extracted_skills)

    assert {"Python", "Linux", "Database Design", "REST APIs"}.issubset(required | extracted)
    assert {"Docker", "Kubernetes", "Apache Airflow", "Git"}.issubset(required | extracted)
    assert {"MLOps", "Model Versioning", "Model Monitoring", "Credit Scoring"}.issubset(required | extracted)
    assert job.description_sections["requirements"]


def test_scraper_job_item_uses_responsibility_skills_when_requirements_are_absent() -> None:
    job = _job_item(
        title="Hub Mitra Training & Program Supervisor",
        company="Astro Technologies Indonesia",
        location="West Jakarta, Indonesia",
        description=ASTRO_TRAINING_SUPERVISOR_DESCRIPTION,
        tags=["E-Commerce"],
        company_logo=None,
        source_url="https://www.kalibrr.com/c/astro/jobs/1/hub-mitra-training-program-supervisor",
        source="kalibrr",
    )

    assert "E-Commerce" not in job.required_skills
    assert {"Training", "Program Management"} & set(job.required_skills)
    assert {"Onboarding", "Operations", "Quality Assurance", "Reporting"} & set(
        job.required_skills + job.extracted_skills
    )


def test_skill_seed_contains_real_taxonomy_categories_and_user_queries() -> None:
    rows = load_skill_seed()
    categories = {row["category"] for row in rows}
    names = {row["name"] for row in rows}

    assert len(rows) >= 5_000
    assert {"technical", "tool", "framework", "language", "soft", "domain", "certification", "knowledge"}.issubset(categories)
    assert {"Machine Learning", "Data Analysis", "Docker", "Kubernetes", "English", "Credit Scoring"}.issubset(names)


def test_scraper_sample_endpoint_is_disabled_for_real_data_only_contract() -> None:
    client = TestClient(scraper_app)

    response = client.get("/sample")

    assert response.status_code == 410
    assert "disabled" in response.json()["detail"].lower()


def test_realtime_scrape_quality_gate_rejects_listing_summaries() -> None:
    generic_listing = _job_item(
        title="Python Developer",
        company="Listing Board",
        location="Indonesia",
        description=(
            "Temukan lebih dari 100.000 lowongan kerja dan loker terbaru di "
            "Indonesia Juni 2026. Lamar cepat, cukup sekali tap!"
        ),
        tags=["Python"],
        company_logo=None,
        source_url="https://glints.com/id/opportunities/jobs/explore?keyword=python",
        source="glints",
    )
    rich_real_job = _job_item(
        title="Data Scientist",
        company="CBI Credit Bureau Indonesia",
        location="South Jakarta, Indonesia",
        description=CBI_DESCRIPTION,
        tags=[],
        company_logo=None,
        source_url="https://www.kalibrr.com/c/cbi/jobs/1/data-scientist",
        source="kalibrr",
    )

    accepted, rejections = _quality_filter_jobs([generic_listing, rich_real_job])

    assert accepted == [rich_real_job]
    assert rejections["generic_listing_description"] == 1
    assert rejections["short_description"] == 1


def test_realtime_scrape_quality_gate_requires_extracted_skill_signal() -> None:
    tag_only_job = _job_item(
        title="General Coordinator",
        company="Real Company",
        location="Jakarta, Indonesia",
        description=(
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
            "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
            "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
            "commodo consequat. Duis aute irure dolor in reprehenderit in voluptate "
            "velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat "
            "cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id "
            "est laborum. Sed ut perspiciatis unde omnis iste natus error sit voluptatem "
            "accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab."
        ),
        tags=[],
        company_logo=None,
        source_url="https://www.kalibrr.com/c/real-company/jobs/123/general-coordinator",
        source="kalibrr",
    )

    accepted, rejections = _quality_filter_jobs([tag_only_job])

    assert accepted == []
    assert rejections["missing_skill_signal"] == 1


def test_inline_real_job_headings_are_structured_for_skill_gap_context() -> None:
    parsed = parse_job_description(
        "What You’ll Be Doing Build campaigns and tracking infrastructure. "
        "Technical & Engineering Focus Implement GTM, conversion APIs, and product feeds. "
        "Data & Performance Analysis Use Looker and Google Analytics for reports. "
        "Essential Criteria 5+ years experience in performance marketing and analytics. "
        "What We’re Looking For Strong analytical mindset. "
        "Our Stack Google Ads, Meta Ads, Looker, Data Studio. "
        "Why This Role is Different Building systems, not just campaigns."
    )

    assert "tracking infrastructure" in parsed.description_sections["responsibilities"].lower()
    assert "5+ years" in parsed.description_sections["requirements"].lower()
    assert "google ads" in parsed.description_sections["nice_to_have"].lower()
    assert parsed.years_experience_min == 5
