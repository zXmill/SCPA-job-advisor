"""Regression tests for rich job descriptions and skill signals."""

from __future__ import annotations

from fastapi.testclient import TestClient

from services.scraper.main import _job_item, app as scraper_app
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
