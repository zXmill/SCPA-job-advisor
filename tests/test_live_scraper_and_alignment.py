from __future__ import annotations

import pytest

from services.pipeline.stages.stage_5_aggregate import run_aggregate_stage
from services.scraper.main import (
    SeedUrl,
    _configured_seed_urls,
    _runtime_seed_budget,
    _select_runtime_seed_urls,
    extract_jobs,
    extract_jobs_from_json,
)


def test_scraper_default_registry_includes_all_enabled_indonesian_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCRAPER_SEED_URLS", raising=False)
    monkeypatch.setenv("PIPELINE_ENABLE_LINKEDIN", "true")
    monkeypatch.setenv("PIPELINE_ENABLE_INDEED", "true")
    monkeypatch.setenv("PIPELINE_ENABLE_JOBSTREET", "true")
    monkeypatch.setenv("PIPELINE_ENABLE_GLINTS", "true")
    monkeypatch.setenv("PIPELINE_ENABLE_KALIBRR", "true")
    monkeypatch.setenv("PIPELINE_ENABLE_KARIR", "true")
    monkeypatch.setenv("PIPELINE_ENABLE_TECHINASIA", "true")

    sources = {seed.source for seed in _configured_seed_urls()}

    assert {
        "linkedin",
        "indeed",
        "jobstreet",
        "glints",
        "kalibrr",
        "karir",
        "techinasia",
    }.issubset(sources)


def test_runtime_seed_selection_round_robins_across_sources() -> None:
    seeds = [
        *(SeedUrl(source="kalibrr", url=f"https://www.kalibrr.com/jobs/{index}") for index in range(20)),
        *(SeedUrl(source="linkedin", url=f"https://www.linkedin.com/jobs/{index}") for index in range(20)),
        *(SeedUrl(source="jobstreet", url=f"https://id.jobstreet.com/id/jobs/{index}") for index in range(20)),
        *(SeedUrl(source="glints", url=f"https://glints.com/id/jobs/{index}") for index in range(20)),
    ]

    selected = _select_runtime_seed_urls(seeds, 8)

    assert [seed.source for seed in selected] == [
        "kalibrr",
        "linkedin",
        "jobstreet",
        "glints",
        "kalibrr",
        "linkedin",
        "jobstreet",
        "glints",
    ]


def test_runtime_seed_selection_rotates_each_source_bucket() -> None:
    seeds = [
        *(SeedUrl(source="kalibrr", url=f"https://www.kalibrr.com/jobs/{index}") for index in range(4)),
        *(SeedUrl(source="linkedin", url=f"https://www.linkedin.com/jobs/{index}") for index in range(4)),
    ]

    selected = _select_runtime_seed_urls(seeds, 6, seed_offset=2)

    assert [seed.url.rsplit("/", 1)[-1] for seed in selected] == ["2", "2", "3", "3", "0", "0"]


def test_runtime_seed_budget_scales_with_requested_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.scraper.main._RUNTIME_URL_CAP", 160)
    seeds = [
        *(SeedUrl(source="kalibrr", url=f"https://www.kalibrr.com/jobs/{index}") for index in range(40)),
        *(SeedUrl(source="linkedin", url=f"https://www.linkedin.com/jobs/{index}") for index in range(40)),
        *(SeedUrl(source="jobstreet", url=f"https://id.jobstreet.com/id/jobs/{index}") for index in range(40)),
        *(SeedUrl(source="glints", url=f"https://glints.com/id/jobs/{index}") for index in range(40)),
        *(SeedUrl(source="indeed", url=f"https://id.indeed.com/jobs/{index}") for index in range(40)),
    ]

    small_budget = _runtime_seed_budget(seeds, raw_target=20, max_urls=160)
    large_budget = _runtime_seed_budget(seeds, raw_target=2000, max_urls=160)

    assert small_budget == 10
    assert large_budget == 160


def test_scraper_infers_skills_and_source_from_indonesian_job_card() -> None:
    html = """
    <article class="job-card">
      <h2 class="job-title">Frontend React Developer</h2>
      <div class="company">PT Web Nusantara</div>
      <div class="location">Jakarta, Indonesia</div>
      <p class="description">Build web applications with React, TypeScript, and REST APIs.</p>
    </article>
    """

    result = extract_jobs(html, source_url="https://id.jobstreet.com/id/jobs?keywords=react", limit=5)

    assert result.count == 1
    job = result.jobs[0]
    assert job.source == "jobstreet"
    assert "React" in job.skills
    assert "Web" in job.skills
    assert job.company_logo


def test_glints_nested_json_records_keep_unique_urls_and_skill_signals() -> None:
    payload = {
        "jobs": [
            {
                "id": "d875b086-bc88-4a63-a123-a6df05c6365d",
                "title": "Data Engineer",
                "company": {"name": "PT Badr Interactive", "logo": "logo.png"},
                "location": {
                    "formattedName": "Sukmajaya",
                    "parents": [
                        {"formattedName": "Depok"},
                        {"formattedName": "Jawa Barat"},
                        {"formattedName": "Indonesia"},
                    ],
                },
                "country": {"code": "ID", "name": "Indonesia"},
                "hierarchicalJobCategory": {
                    "name": "Data Engineer",
                    "parents": [{"name": "Computer & Software"}, {"name": "Data"}],
                },
                "workArrangementOption": "HYBRID",
                "type": "CONTRACT",
                "educationLevel": "BACHELOR_DEGREE",
                "minYearsOfExperience": 1,
                "maxYearsOfExperience": 3,
                "salaries": [
                    {
                        "CurrencyCode": "IDR",
                        "minAmount": 7000000,
                        "maxAmount": 10000000,
                        "salaryMode": "MONTH",
                    }
                ],
                "skills": [
                    {"skill": {"name": "Data Modeling"}, "mustHave": True},
                    {"skill": {"name": "Python"}, "mustHave": True},
                    {"skill": {"name": "Big Data Processing"}, "mustHave": True},
                ],
            }
        ]
    }

    result = extract_jobs_from_json(
        payload,
        source_url="https://glints.com/id/opportunities/jobs/explore?keyword=data+engineer&country=ID",
        limit=5,
    )

    assert result.count == 1
    job = result.jobs[0]
    assert job.source == "glints"
    assert job.source_url == "https://glints.com/id/opportunities/jobs/d875b086-bc88-4a63-a123-a6df05c6365d/data-engineer"
    assert job.company == "PT Badr Interactive"
    assert "Indonesia" in job.location
    assert "Python" in job.extracted_skills
    assert "Data Modeling" in job.extracted_skills
    assert job.salary_text == "IDR 7000000 - 10000000 / month"
    assert len(job.description_text) >= 300


@pytest.mark.anyio
async def test_skill_alignment_reports_unrelated_tutor_without_hidden_score_mutation() -> None:
    user = {
        "id": "greed",
        "program_studi": "Teknik Informatika",
        "jurusan": "Teknik Informatika",
        "skills": ["Python", "React", "Web"],
        "profile_text": "Teknik Informatika Python React Web",
        "interaction_count": 0,
    }
    jobs = [
        {
            "id": "tutor",
            "title": "Tutor Freelance Bahasa Indonesia",
            "company": "CV Pendidikan",
            "location": "Jakarta, Indonesia",
            "description": "Mengajar Bahasa Indonesia untuk siswa SMA.",
            "skills": ["Education"],
            "sbert_score": 0.64,
            "ncf_score": 0.60,
            "dqn_score": 1.0,
        },
        {
            "id": "frontend",
            "title": "Frontend React Developer",
            "company": "PT Web Nusantara",
            "location": "Jakarta, Indonesia",
            "description": "Build web products with React, TypeScript, APIs, and modern frontend tooling.",
            "skills": ["React", "Web", "TypeScript"],
            "sbert_score": 0.62,
            "ncf_score": 0.55,
            "dqn_score": 0.1,
        },
        {
            "id": "backend",
            "title": "Python Backend Developer",
            "company": "PT API Nusantara",
            "location": "Jakarta, Indonesia",
            "description": "Build FastAPI services with Python, PostgreSQL, and REST APIs.",
            "skills": ["Python", "SQL", "FastAPI"],
            "sbert_score": 0.61,
            "ncf_score": 0.54,
            "dqn_score": 0.1,
        },
        {
            "id": "data",
            "title": "Data Engineer",
            "company": "PT Data Nusantara",
            "location": "Jakarta, Indonesia",
            "description": "Build data pipelines using Python and SQL.",
            "skills": ["Python", "SQL"],
            "sbert_score": 0.60,
            "ncf_score": 0.53,
            "dqn_score": 0.1,
        },
        {
            "id": "web",
            "title": "Web Developer",
            "company": "PT Digital Nusantara",
            "location": "Bandung, Indonesia",
            "description": "Develop responsive web interfaces with JavaScript and React.",
            "skills": ["Web", "React", "JavaScript"],
            "sbert_score": 0.59,
            "ncf_score": 0.52,
            "dqn_score": 0.1,
        },
        {
            "id": "software",
            "title": "Software Engineer",
            "company": "PT Tech Nusantara",
            "location": "Surabaya, Indonesia",
            "description": "Create software systems for web platforms and APIs.",
            "skills": ["Web", "Python"],
            "sbert_score": 0.58,
            "ncf_score": 0.51,
            "dqn_score": 0.1,
        },
    ]

    result = await run_aggregate_stage(user, jobs)

    tutor = next(job for job in result.ranked if job["id"] == "tutor")
    assert tutor["skill_alignment_score"] == 0.0
    assert tutor["skill_alignment_penalty"] > 0.0
    assert tutor["matched_skills"] == []
    assert tutor["gamma"] == 0.0
    assert tutor["final_score"] == pytest.approx((0.8 * 0.64) + (0.2 * 0.60))
    assert "Matched skills:" not in " ".join(tutor["explanation"])


@pytest.mark.anyio
async def test_skill_alignment_does_not_match_generic_training_or_data_words_to_tech_skills() -> None:
    user = {
        "id": "greed",
        "program_studi": "Teknik Informatika",
        "jurusan": "Teknik Informatika",
        "skills": ["SQL", "Python", "Statistics", "Machine Learning", "React", "Artificial Intelligence"],
        "profile_text": "Teknik Informatika SQL Python Statistics Machine Learning React Artificial Intelligence",
        "interaction_count": 0,
    }
    jobs = [
        {
            "id": "training-supervisor",
            "title": "Hub Mitra Training & Program Supervisor",
            "company": "Astro Technologies Indonesia",
            "location": "West Jakarta, Indonesia",
            "description": (
                "Role Overview The role ensures mitra onboarding, training execution, "
                "retention, operations alignment, reporting, performance monitoring, "
                "and improvement initiatives based on data insights."
            ),
            "required_skills": ["Training", "Operations", "Reporting"],
            "extracted_skills": ["Onboarding", "Performance Monitoring", "Data Analysis"],
            "tags": ["E-Commerce"],
            "sbert_score": 0.57,
            "ncf_score": 0.58,
            "dqn_score": 1.0,
        }
    ]

    result = await run_aggregate_stage(user, jobs)
    item = result.ranked[0]

    assert item["matched_skills"] == []
    assert item["skill_alignment_score"] == 0.0
    assert "Matched skills:" not in " ".join(item["explanation"])
