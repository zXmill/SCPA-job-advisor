from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


DATABASE_CLEANUP_ORDER = [
    "feedback_events",
    "dqn_episodes",
    "served_slate_items",
    "served_slates",
    "embedding_cache_entries",
    "model_entity_mappings",
    "model_artifacts",
    "dqn_replay_archive",
    "dqn_session_logs",
    "user_job_interactions",
    "user_interactions",
    "applications",
    "user_skills",
    "jobs",
    "users",
]


def uid() -> str:
    return str(uuid.uuid4())


def normalize_database_url(database_url: str) -> str:
    """Return an asyncpg URL suitable for async SQLAlchemy seeding."""
    if "psycopg2" in database_url:
        return database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def get_seed_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required to seed the database.")
    return normalize_database_url(database_url)


def get_database_cleanup_order() -> list[str]:
    """Return child-before-parent table cleanup order for deterministic reseeding."""
    return list(DATABASE_CLEANUP_ORDER)


def make_async_session_factory(database_url: str | None = None):
    engine = create_async_engine(database_url or get_seed_database_url(), echo=False)
    return engine, sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def build_seed_users() -> list[dict[str, Any]]:
    return [
        {
            "id": uid(),
            "name": "Budi Santoso",
            "email": "budi@example.com",
            "password_hash": pwd.hash("password123"),
            "program_studi": "Teknik Informatika",
            "university": "Universitas Indonesia",
            "role": "user",
            "completion_percent": 85,
        },
        {
            "id": uid(),
            "name": "Siti Aminah",
            "email": "siti@example.com",
            "password_hash": pwd.hash("password123"),
            "program_studi": "Sistem Informasi",
            "university": "Institut Teknologi Bandung",
            "role": "user",
            "completion_percent": 70,
        },
        {
            "id": uid(),
            "name": "Admin SCPA",
            "email": "admin@scpa.id",
            "password_hash": pwd.hash("admin123"),
            "program_studi": "Ilmu Komputer",
            "university": "Universitas Gadjah Mada",
            "role": "admin",
            "completion_percent": 100,
        },
    ]


def build_seed_jobs() -> list[dict[str, Any]]:
    jobs = [
        {
            "title": "Data Scientist Junior",
            "company": "PT Tokopedia",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 12000000,
            "max_salary": 18000000,
            "description": "Bergabung dengan tim data science kami untuk mengembangkan model prediktif menggunakan Python, TensorFlow, dan SQL. Menganalisis data pengguna untuk meningkatkan rekomendasi produk.",
            "experience_level": "entry",
            "source": "jobstreet",
        },
        {
            "title": "Product Manager",
            "company": "Gojek",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 15000000,
            "max_salary": 25000000,
            "description": "Memimpin pengembangan produk digital untuk jutaan pengguna di Asia Tenggara. Membutuhkan kemampuan analitik data, Agile/Scrum, dan stakeholder management.",
            "experience_level": "mid",
            "source": "linkedin",
        },
        {
            "title": "Frontend Engineer",
            "company": "Bukalapak",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 10000000,
            "max_salary": 16000000,
            "description": "Membangun antarmuka pengguna yang responsif menggunakan React, TypeScript, dan Next.js. Pengalaman dengan design system dan testing framework diutamakan.",
            "experience_level": "entry",
            "source": "glints",
        },
        {
            "title": "Senior Data Analyst",
            "company": "Gopay Indonesia",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 18000000,
            "max_salary": 28000000,
            "description": "Menganalisis data transaksi fintech untuk mendukung keputusan strategis. Keahlian SQL, Tableau, Python, dan statistical modeling diperlukan.",
            "experience_level": "senior",
            "source": "jobstreet",
        },
        {
            "title": "Machine Learning Engineer",
            "company": "Traveloka",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 20000000,
            "max_salary": 35000000,
            "description": "Membangun dan deploy model ML untuk personalisasi harga dan rekomendasi perjalanan. PyTorch, MLOps, dan cloud infrastructure (AWS/GCP).",
            "experience_level": "mid",
            "source": "linkedin",
        },
        {
            "title": "Backend Engineer (Go)",
            "company": "Shopee Indonesia",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 15000000,
            "max_salary": 25000000,
            "description": "Mengembangkan microservices menggunakan Go, gRPC, dan Kubernetes. Membutuhkan pengalaman distributed systems dan high-throughput architectures.",
            "experience_level": "mid",
            "source": "glints",
        },
        {
            "title": "DevOps Engineer",
            "company": "OVO",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 16000000,
            "max_salary": 26000000,
            "description": "Mengelola infrastructure CI/CD, Docker, Kubernetes, dan monitoring. Pengalaman AWS, Terraform, dan observability stack (Prometheus, Grafana).",
            "experience_level": "mid",
            "source": "linkedin",
        },
        {
            "title": "UI/UX Designer",
            "company": "Blibli.com",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 12000000,
            "max_salary": 20000000,
            "description": "Merancang pengalaman pengguna e-commerce. Figma, user research, prototyping, design system. Portofolio desain interaksi diperlukan.",
            "experience_level": "entry",
            "source": "glints",
        },
        {
            "title": "Cloud Solutions Architect",
            "company": "Google Indonesia",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 30000000,
            "max_salary": 50000000,
            "description": "Membantu enterprise Indonesia mengadopsi Google Cloud. Keahlian cloud architecture, networking, security, dan data analytics di GCP.",
            "experience_level": "senior",
            "source": "linkedin",
        },
        {
            "title": "Cybersecurity Analyst",
            "company": "Bank Mandiri",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 14000000,
            "max_salary": 22000000,
            "description": "Monitoring keamanan sistem perbankan, incident response, dan vulnerability assessment. Sertifikasi CompTIA Security+ atau CEH diutamakan.",
            "experience_level": "mid",
            "source": "jobstreet",
        },
        {
            "title": "Data Engineer",
            "company": "Grab Indonesia",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 18000000,
            "max_salary": 30000000,
            "description": "Membangun data pipeline dan data warehouse menggunakan Apache Spark, Airflow, dan BigQuery. ETL optimization dan data quality monitoring.",
            "experience_level": "mid",
            "source": "linkedin",
        },
        {
            "title": "Mobile Developer (Flutter)",
            "company": "Dana Indonesia",
            "location": "Jakarta, Indonesia",
            "type": "full_time",
            "min_salary": 13000000,
            "max_salary": 20000000,
            "description": "Mengembangkan aplikasi mobile fintech dengan Flutter/Dart. Pengalaman REST API integration, state management, dan app performance optimization.",
            "experience_level": "entry",
            "source": "glints",
        },
    ]

    for job in jobs:
        raw_id = f"{job['title'].lower()}|{job['company'].lower()}|{job['location'].lower()}"
        digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]
        job["id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, digest))
    return jobs


def build_recommendation_evidence_seed_rows(
    users: list[dict[str, Any]], jobs: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Build deterministic rows for recommendation evidence tables."""
    user_id = users[0]["id"]
    selected_jobs = jobs[:2]
    slate_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"scpa-seed-slate:{user_id}"))
    model_versions = {
        "sbert": "sbert-seed-v1",
        "ncf": "ncf-seed-v1",
        "dqn": "dqn-seed-v1",
    }
    fallback_flags = {"sbert": False, "ncf": False, "dqn": False}

    slate_items = [
        {
            "slate_id": slate_id,
            "job_id": job["id"],
            "rank": index,
            "score": round(0.92 - (index * 0.08), 4),
            "component_scores": {
                "sbert": round(0.88 - (index * 0.05), 4),
                "ncf": round(0.74 - (index * 0.04), 4),
                "dqn": round(0.69 - (index * 0.03), 4),
            },
            "model_versions": model_versions,
            "fallback_flags": fallback_flags,
            "explanation": {
                "matched_skills": ["Python", "SQL"],
                "missing_skills": ["MLOps"],
            },
        }
        for index, job in enumerate(selected_jobs, start=1)
    ]

    return {
        "served_slates": [
            {
                "id": slate_id,
                "user_id": user_id,
                "request_id": "seed-request-001",
                "pipeline_run_id": "seed-pipeline-run-001",
                "model_versions": model_versions,
                "fallback_flags": fallback_flags,
                "context": {"profile": "Teknik Informatika", "source": "seed"},
            }
        ],
        "served_slate_items": slate_items,
        "feedback_events": [
            {
                "event_type": "impression",
                "user_id": user_id,
                "job_id": selected_jobs[0]["id"],
                "slate_id": slate_id,
                "slate_item_id": None,
                "rank": 1,
                "session_id": "seed-session-001",
                "source": "seed",
                "dwell_ms": None,
                "model_provenance": model_versions,
                "fallback_flags": fallback_flags,
                "metadata": {"surface": "recommendation_card"},
            },
            {
                "event_type": "view",
                "user_id": user_id,
                "job_id": selected_jobs[0]["id"],
                "slate_id": slate_id,
                "slate_item_id": None,
                "rank": 1,
                "session_id": "seed-session-001",
                "source": "seed",
                "dwell_ms": 4200,
                "model_provenance": model_versions,
                "fallback_flags": fallback_flags,
                "metadata": {"surface": "job_detail"},
            },
            {
                "event_type": "save",
                "user_id": user_id,
                "job_id": selected_jobs[1]["id"],
                "slate_id": slate_id,
                "slate_item_id": None,
                "rank": 2,
                "session_id": "seed-session-001",
                "source": "seed",
                "dwell_ms": 1800,
                "model_provenance": model_versions,
                "fallback_flags": fallback_flags,
                "metadata": {"surface": "recommendation_card"},
            },
        ],
        "model_artifacts": [
            {
                "service": "sbert",
                "model_name": "sentence-transformer-seed",
                "model_version": "sbert-seed-v1",
                "artifact_path": "models/sbert/seed",
                "artifact_hash": "seed-sbert-artifact",
                "training_run_id": "seed-sbert-run",
                "metrics": {"ndcg_at_10": 0.0, "status": "seed-placeholder"},
                "fallback_mode": False,
                "active": True,
            },
            {
                "service": "ncf",
                "model_name": "neumf-seed",
                "model_version": "ncf-seed-v1",
                "artifact_path": "models/ncf/seed.pt",
                "artifact_hash": "seed-ncf-artifact",
                "training_run_id": "seed-ncf-run",
                "metrics": {"ndcg_at_10": 0.0, "status": "seed-placeholder"},
                "fallback_mode": False,
                "active": True,
            },
            {
                "service": "dqn",
                "model_name": "qnetwork-seed",
                "model_version": "dqn-seed-v1",
                "artifact_path": "models/dqn/seed.pt",
                "artifact_hash": "seed-dqn-artifact",
                "training_run_id": "seed-dqn-run",
                "metrics": {"reward_lift": 0.0, "status": "seed-placeholder"},
                "fallback_mode": False,
                "active": True,
            },
        ],
        "embedding_cache_entries": [
            {
                "cache_key": "seed-profile-budi-sbert-seed-v1",
                "source_text_hash": hashlib.sha256(
                    "Budi Santoso Teknik Informatika".encode("utf-8")
                ).hexdigest(),
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "embedding_dim": 4,
                "model_version": "sbert-seed-v1",
                "service": "sbert",
                "fallback_mode": False,
                "expires_at": datetime.now(UTC) + timedelta(days=7),
            }
        ],
        "model_entity_mappings": [
            {
                "service": "ncf",
                "model_version": "ncf-seed-v1",
                "entity_type": "user",
                "external_id": user_id,
                "entity_uuid": user_id,
                "internal_index": 0,
            },
            {
                "service": "ncf",
                "model_version": "ncf-seed-v1",
                "entity_type": "job",
                "external_id": selected_jobs[0]["id"],
                "entity_uuid": selected_jobs[0]["id"],
                "internal_index": 0,
            },
            {
                "service": "ncf",
                "model_version": "ncf-seed-v1",
                "entity_type": "job",
                "external_id": selected_jobs[1]["id"],
                "entity_uuid": selected_jobs[1]["id"],
                "internal_index": 1,
            },
        ],
        "dqn_episodes": [
            {
                "episode_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "scpa-seed-dqn-episode")),
                "user_id": user_id,
                "slate_id": slate_id,
                "state": {"skills": ["Python", "SQL"], "target_role": "Data Scientist"},
                "action": "recommend_data_scientist_path",
                "reward": 1.0,
                "next_state": {"saved_job": selected_jobs[1]["id"]},
                "done": False,
                "policy_version": "dqn-seed-v1",
            }
        ],
    }


async def _insert_recommendation_evidence(
    session: AsyncSession, users: list[dict[str, Any]], jobs: list[dict[str, Any]]
) -> None:
    rows = build_recommendation_evidence_seed_rows(users, jobs)

    for row in rows["served_slates"]:
        await session.execute(
            text(
                "INSERT INTO served_slates "
                "(id,user_id,request_id,pipeline_run_id,model_versions,fallback_flags,context) "
                "VALUES (:id,:user_id,:request_id,:pipeline_run_id,:model_versions,:fallback_flags,:context)"
            ),
            row,
        )

    for row in rows["served_slate_items"]:
        await session.execute(
            text(
                "INSERT INTO served_slate_items "
                "(slate_id,job_id,rank,score,component_scores,model_versions,fallback_flags,explanation) "
                "VALUES (:slate_id,:job_id,:rank,:score,:component_scores,:model_versions,:fallback_flags,:explanation)"
            ),
            row,
        )

    for row in rows["feedback_events"]:
        await session.execute(
            text(
                "INSERT INTO feedback_events "
                "(event_type,user_id,job_id,slate_id,slate_item_id,rank,session_id,source,dwell_ms,model_provenance,fallback_flags,metadata) "
                "VALUES (:event_type,:user_id,:job_id,:slate_id,:slate_item_id,:rank,:session_id,:source,:dwell_ms,:model_provenance,:fallback_flags,:metadata)"
            ),
            row,
        )

    for row in rows["model_artifacts"]:
        await session.execute(
            text(
                "INSERT INTO model_artifacts "
                "(service,model_name,model_version,artifact_path,artifact_hash,training_run_id,metrics,fallback_mode,active) "
                "VALUES (:service,:model_name,:model_version,:artifact_path,:artifact_hash,:training_run_id,:metrics,:fallback_mode,:active)"
            ),
            row,
        )

    for row in rows["embedding_cache_entries"]:
        await session.execute(
            text(
                "INSERT INTO embedding_cache_entries "
                "(cache_key,source_text_hash,embedding,embedding_dim,model_version,service,fallback_mode,expires_at) "
                "VALUES (:cache_key,:source_text_hash,:embedding,:embedding_dim,:model_version,:service,:fallback_mode,:expires_at)"
            ),
            row,
        )

    for row in rows["model_entity_mappings"]:
        await session.execute(
            text(
                "INSERT INTO model_entity_mappings "
                "(service,model_version,entity_type,external_id,entity_uuid,internal_index) "
                "VALUES (:service,:model_version,:entity_type,:external_id,:entity_uuid,:internal_index)"
            ),
            row,
        )

    for row in rows["dqn_episodes"]:
        await session.execute(
            text(
                "INSERT INTO dqn_episodes "
                "(episode_id,user_id,slate_id,state,action,reward,next_state,done,policy_version) "
                "VALUES (:episode_id,:user_id,:slate_id,:state,:action,:reward,:next_state,:done,:policy_version)"
            ),
            row,
        )


async def seed_data() -> None:
    engine, async_session_local = make_async_session_factory()
    async with async_session_local() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        if result.scalar() > 0:
            print("DB already seeded. Dropping and re-seeding...")
            for table_name in get_database_cleanup_order():
                await session.execute(text(f"DELETE FROM {table_name}"))
            await session.commit()

        print("Seeding database with production data...")

        users = build_seed_users()
        for user in users:
            await session.execute(
                text(
                    "INSERT INTO users "
                    "(id,name,email,password_hash,program_studi,university,role,completion_percent) "
                    "VALUES (:id,:name,:email,:password_hash,:program_studi,:university,:role,:completion_percent)"
                ),
                user,
            )

        jobs = build_seed_jobs()
        for job in jobs:
            await session.execute(
                text(
                    "INSERT INTO jobs "
                    "(id,title,company,location,type,min_salary,max_salary,description,experience_level,source) "
                    "VALUES (:id,:title,:company,:location,:type,:min_salary,:max_salary,:description,:experience_level,:source)"
                ),
                job,
            )

        budi_id = users[0]["id"]
        for skill in ["Python", "Machine Learning", "Data Analysis", "SQL", "React"]:
            await session.execute(
                text(
                    "INSERT INTO user_skills (user_id,skill,category,proficiency_level) "
                    "VALUES (:uid,:s,'technical','intermediate')"
                ),
                {"uid": budi_id, "s": skill},
            )

        await session.execute(
            text(
                "INSERT INTO applications (id,user_id,job_id,status) "
                "VALUES (:id,:uid,:jid,'submitted')"
            ),
            {"id": uid(), "uid": budi_id, "jid": jobs[0]["id"]},
        )
        await session.execute(
            text(
                "INSERT INTO applications (id,user_id,job_id,status) "
                "VALUES (:id,:uid,:jid,'reviewed')"
            ),
            {"id": uid(), "uid": budi_id, "jid": jobs[2]["id"]},
        )

        await _insert_recommendation_evidence(session, users, jobs)

        await session.commit()
        print(
            "[OK] Seeded: "
            f"{len(users)} users, {len(jobs)} jobs, 5 skills, 2 applications, "
            "recommendation evidence rows"
        )
        print("   Login: budi@example.com / password123")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())
