# SCPA — Sistem Rekomendasi Pekerjaan Berbasis AI

> **Smart Career Pathway Assistant** — AI-powered job recommendation system for job seekers in Indonesia.
>
> **Version:** 1.0.0 (Prototype/Mock) | **Last Updated:** 2026-05-15 | **Platform:** Docker Compose + Kubernetes

---

## Table of Contents

- [SECTION 1: Functionality & Architecture](#section-1-functionality--architecture)
  - [1.1 Overview](#11-overview)
  - [1.2 Architecture Diagram](#12-architecture-diagram)
  - [1.3 Service Registry](#13-service-registry)
  - [1.4 Data Flow](#14-data-flow)
  - [1.5 Technology Stack](#15-technology-stack)
  - [1.6 Database Schema Overview](#16-database-schema-overview)
  - [1.7 Infrastructure Components](#17-infrastructure-components)
- [SECTION 2: Use Cases & Implementation](#section-2-use-cases--implementation)
  - [2.1 Real-World Use Cases](#21-real-world-use-cases)
  - [2.2 Quick Start Guide](#22-quick-start-guide)
  - [2.3 API Usage Examples](#23-api-usage-examples)
  - [2.4 Environment Variable Reference](#24-environment-variable-reference)
  - [2.5 Configuration Guide](#25-configuration-guide)
- [SECTION 3: Code Review & Technical Documentation](#section-3-code-review--technical-documentation)
  - [3.1 Module-by-Module Documentation](#31-module-by-module-documentation)
  - [3.2 API Reference Table](#32-api-reference-table)
  - [3.3 Design Patterns](#33-design-patterns)
  - [3.4 Complexity Analysis](#34-complexity-analysis)
  - [3.5 Security Hardening](#35-security-hardening)
  - [3.6 Coding Standards & Conventions](#36-coding-standards--conventions)
  - [3.7 Testing Strategy](#37-testing-strategy)
  - [3.8 CI/CD Pipeline Notes](#38-cicd-pipeline-notes)
- [Appendix](#appendix)

---

## SECTION 1: Functionality & Architecture

### 1.1 Overview

SCPA is an Indonesian career intelligence platform that leverages three AI/ML models to deliver personalized job recommendations:

| Model | Purpose | Technique |
|-------|---------|-----------|
| **NCF** (Neural Collaborative Filtering) | Collaborative filtering based on collective user behavior | GMF + MLP hybrid (He et al., 2017) |
| **SBERT** (Semantic BERT) | Semantic text matching between user profiles and job descriptions | Sentence-BERT embeddings + cosine similarity |
| **DQN** (Deep Q-Network) | Adaptive career learning path construction | Reinforcement learning with experience replay |

The **Hybrid Blending Service** combines NCF and SBERT scores using an α-weighted formula with fairness constraints (Equal Opportunity, TPR gap < 8pp), providing a final ranked list of job recommendations.

**Core value proposition:** Help Indonesian job seekers discover relevant career opportunities through AI-driven personalization, semantic understanding, and adaptive learning path guidance.

---

### 1.2 Architecture Diagram

#### High-Level System Architecture (ASCII)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                               CLIENTS                                        │
│   ┌──────────────────────┐         ┌──────────────────┐                     │
│   │  Next.js Frontend    │         │  Mobile App      │                     │
│   │  (SSR/SSG, Port 3000)│         │  (Future, TBD)   │                     │
│   └────────┬─────────────┘         └────────┬─────────┘                     │
└────────────┼────────────────────────────────┼───────────────────────────────┘
             │                                │
             ▼                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY (Nginx :8000)                           │
│         Rate Limiting • Security Headers • Reverse Proxy Routing             │
│   ┌────────┬────────┬────────┬────────┬────────┬────────┬────────┬──────┐   │
│   │ /api/  │ /api/  │ /api/  │ /api/  │ /health│ /api/  │  CORS  │ SSL  │   │
│   │ ncf/   │ sbert/ │ dqn/   │hybrid/ │        │ */     │ config │ term │   │
│   └───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴────┘   │
└────────┼─────────┼────────┼─────────┼─────────┼────────┼───────────────────┘
         │         │        │         │         │        │
         ▼         ▼        ▼         ▼         ▼        ▼
┌──────────────┐┌──────────┐┌────────┐┌──────────────┐┌────────┐┌────────┐  │
│  ncf-service ││sbert-svc ││dqn-svc ││ hybrid-service││pipeline││Health  │  │
│   :8001      ││  :8002   ││ :8003  ││    :8004      ││ :8005  ││Checker │  │
│  (FastAPI)   ││ (FastAPI)││FastAPI ││   (FastAPI)   ││(Apsched)││ Script │  │
└──────┬───────┘└────┬─────┘└───┬────┘└──────┬───────┘└───┬────┘└────────┘  │
       │              │          │              │           │                 │
       └──────────────┴──────────┴──────────────┴───────────┘                 │
                                  │       │                                   │
                                  ▼       ▼                                   │
                     ┌─────────────────────────────────┐                      │
                     │        INFRASTRUCTURE            │                      │
                     │                                   │                      │
                     │  ┌────────────┐  ┌────────────┐  │                      │
                     │  │ PostgreSQL │  │   Redis     │  │                      │
                     │  │   :5432    │  │   :6379     │  │                      │
                     │  │  (v15)     │  │   (v7)      │  │                      │
                     │  └────────────┘  └────────────┘  │                      │
                     └─────────────────────────────────┘                      │
┌──────────────────────────────────────────────────────────────────────────────┐
│                          DEVELOPER MACHINE / CI                             │
│  scripts/validate_env.sh  •  scripts/health_check.py  •  scripts/git-       │
│  hooks/  •  alembic  •  pytest  •  docker compose up                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Mermaid Diagram (for Markdown renderers)

```mermaid
graph TD
    A[Next.js Frontend<br/>:3000] -->|HTTP/REST| B[Nginx API Gateway<br/>:8000]
    B -->|proxy_pass| C[ncf-service<br/>:8001]
    B -->|proxy_pass| D[sbert-service<br/>:8002]
    B -->|proxy_pass| E[dqn-service<br/>:8003]
    B -->|proxy_pass| F[hybrid-service<br/>:8004]
    C -->|Read/Write| PG[(PostgreSQL<br/>:5432)]
    D -->|Read| PG
    E -->|Read| PG
    F -->|Read| PG
    G[pipeline-service<br/>:8005] -->|Write| PG
    G -->|Cache Write| RD[(Redis<br/>:6379)]
    F -->|Cache Read| RD
    C -->|Cache Read| RD
    H[Health Checker<br/>scripts/] -->|Monitor| B
    H -->|Monitor| C
    H -->|Monitor| D
    H -->|Monitor| E
    H -->|Monitor| F
```

---

### 1.3 Service Registry

| # | Service | Port | Container | Purpose | Status |
|---|---------|------|-----------|---------|--------|
| 1 | **frontend** | 3000 | Next.js 16 / React 19 | SSR/SSG web UI, Tailwind v4 | Active (mock data) |
| 2 | **api-gateway** | 8000 | nginx:alpine | Reverse proxy, rate limiting, security headers | Active |
| 3 | **ncf-service** | 8001 | Python/FastAPI | Neural Collaborative Filtering recommendations | Mock |
| 4 | **sbert-service** | 8002 | Python/FastAPI | SBERT semantic matching (cosine similarity) | Mock |
| 5 | **dqn-service** | 8003 | Python/FastAPI | Deep Q-Network learning path generation | Mock |
| 6 | **hybrid-service** | 8004 | Python/FastAPI | α-blending, fairness enforcement, aggregation | Mock |
| 7 | **pipeline-service** | 8005 | Python/APSched | Web scraping (JobStreet, LinkedIn, Glints) | Mock |
| 8 | **postgres** | 5432 | postgres:15-alpine | Primary relational database | Configured |
| 9 | **redis** | 6379 | redis:7-alpine | Caching layer (recs, sessions, rate limits) | Configured |

---

### 1.4 Data Flow

#### 1.4.1 Recommendation Request Flow

```
 1. User opens Recommendations page (Next.js frontend)
 2. Frontend sends POST /api/hybrid/recommend/hybrid → Nginx (:8000)
 3. Nginx routes to hybrid-service (:8004)
 4. Hybrid service orchestrates:
    ├── 4a. POST /api/ncf/recommend/ncf (user_id, n_items) → ncf-service
    │       └── NCF Model: GMF dot-product + MLP → scored job list
    ├── 4b. POST /api/sbert/match/semantic (profile_text, job_descs) → sbert-service
    │       └── SBERT: encode → cosine similarity → ranked scores
    ├── 4c. Score Blending:
    │       h_score = α × SBERT_score + (1-α) × NCF_score
    │       α = 1.0 (cold-start) or 0.5 (returning user)
    ├── 4d. Fairness Check:
    │       TPR gap (majority vs minority) < 8 percentage points
    │       Re-rank if constraint violated
    └── 4e. Return top-10 blended results
 5. Frontend renders recommendation cards with MatchDonut visualization
```

#### 1.4.2 Learning Path Request Flow

```
 1. User requests career guidance
 2. Frontend sends POST /api/dqn/learning-path (user_id, current_skills, target_role)
 3. DQN service:
    ├── Encode user state (skills, interactions, target)
    ├── Forward pass through DQN network → Q-values for each action
    ├── ε-greedy action selection
    ├── Construct ordered career step sequence
    └── Return learning path with estimated completion time
```

#### 1.4.3 Data Pipeline Flow

```
 1. APScheduler triggers every 24h (configurable via SCRAPING_INTERVAL_HOURS)
 2. Selenium/Playwright scrapers target:
    ├── JobStreet Indonesia
    ├── LinkedIn Jobs
    └── Glints
 3. Raw data normalized → PostgreSQL `jobs` table
 4. Redis cache invalidated (rec:* pattern deleted)
 5. User interaction logs appended to `user_interactions`
```

---

### 1.5 Technology Stack

| Layer | Technology | Version | Role |
|-------|-----------|---------|------|
| **Frontend** | Next.js | 16.x | SSR/SSG web application |
| **Frontend** | React | 19.x | UI components & state management |
| **Frontend** | TypeScript | 5.x | Type-safe development |
| **Frontend** | Tailwind CSS | v4 | Utility-first styling |
| **Backend** | Python | 3.x | Microservice language |
| **Backend** | FastAPI | latest | REST API framework (all 5 services) |
| **Backend** | Pydantic | v2 | Request/response validation |
| **ML** | PyTorch | latest | NCF & DQN model frameworks |
| **ML** | sentence-transformers | latest | SBERT embedding models |
| **Database** | PostgreSQL | 15-alpine | Primary persistent store |
| **Cache** | Redis | 7-alpine | Application caching layer |
| **Scheduler** | APScheduler | latest | Pipeline cron scheduling |
| **Infra** | Docker Compose | latest | Local development orchestration |
| **Infra** | Kubernetes | latest | Production deployment manifests |
| **Reverse Proxy** | Nginx | alpine | API gateway, rate limiting, SSL termination |
| **Migration** | Alembic | latest | Database schema versioning |

---

### 1.6 Database Schema Overview

#### 8 Tables

| # | Table | Description | Rows (est.) |
|---|-------|-------------|-------------|
| 1 | `users` | User profiles, auth credentials, role | — |
| 2 | `jobs` | Job vacancy listings with ML metadata | Target: 5,000+ |
| 3 | `applications` | User↔Job application records with status | — |
| 4 | `user_skills` | User skill catalog with categories | — |
| 5 | `user_interactions` | DQN training data (click/view/apply logs) | — |

#### 8 ENUMs

| # | ENUM Name | Values | Used In |
|---|-----------|--------|---------|
| 1 | `userrole` | `user`, `admin`, `premium` | `users.role` |
| 2 | `jobtype` | `full_time`, `part_time`, `contract`, `internship` | `jobs.type` |
| 3 | `employmentmode` | `onsite`, `remote`, `hybrid` | `jobs.employment_mode` |
| 4 | `experiencelevel` | `entry`, `mid`, `senior` | `jobs.experience_level` |
| 5 | `jobsource` | `jobstreet`, `linkedin`, `glints` | `jobs.source` |
| 6 | `applicationstatus` | `submitted`, `reviewed`, `accepted`, `rejected`, `withdrawn` | `applications.status` |
| 7 | `skillcategory` | `technical`, `soft`, `linguistic` | `user_skills.category` |
| 8 | `proficiencylevel` | `beginner`, `intermediate`, `advanced` | `user_skills.proficiency_level` |

#### Full Schema (ERD)

```
┌─────────────┐       ┌──────────────────┐       ┌──────────────┐
│   users      │       │    jobs          │       │ applications  │
├─────────────┤       ├──────────────────┤       ├──────────────┤
│ id (UUID)   │──┐    │ id (UUID)        │       │ id (UUID)    │
│ name        │  │    │ title            │       │ user_id (FK) │──┐
│ email (UK)  │  │    │ company          │       │ job_id  (FK) │  │
│ pw_hash     │  │    │ location         │       │ status (ENUM)│  │
│ program_    │  │    │ type (ENUM)      │       │ cover_letter │  │
│  studi      │  │    │ min_salary       │       │ resume_url   │  │
│ university  │  │    │ max_salary       │       │ applied_via  │  │
│ completion_ │  │    │ salary_currency  │       │ applied_at   │  │
│  percent    │  │    │ empl_mode (ENUM) │       │ updated_at   │  │
│ role (ENUM) │  │    │ description      │       └──────────────┘
│ email_verif │  │    │ exp_level(ENUM)  │
│ last_login  │  │    │ posted_at        │
│ created_at  │  │    │ source (ENUM)    │
│ updated_at  │  │    │ is_active        │
└──────┬──────┘    │ match_data (JSONB) │
       │           └──────────────────┘
       │
       │  ┌───────────────┐    ┌────────────────────┐
       └──│  user_skills   │    │  user_interactions  │
          ├───────────────┤    ├────────────────────┤
          │ id (SERIAL)   │    │ id (SERIAL)        │
          │ user_id (FK)──┘    │ user_id (FK)──┐    │
          │ skill              │ action_type    │    │
          │ category (ENUM)    │ target_type    │    │
          │ proficiency(ENUM)  │ target_id (FK) │    │
          │ endorsed           │ metadata(JSONB)│    │
          │ created_at         │ session_id     │    │
          └───────────────────┘│ created_at     │    │
                               └────────────────┘────┘
```

#### Index Strategy

| Index Name | Table | Columns | Purpose |
|-----------|-------|---------|---------|
| `idx_users_email` | users | email (UNIQUE) | Auth lookup |
| `idx_users_completion` | users | completion_percent | Profile quality filter |
| `idx_users_created_at` | users | created_at | Audit queries |
| `idx_jobs_company` | jobs | company | Company search |
| `idx_jobs_location` | jobs | location | Geo filter |
| `idx_jobs_source` | jobs | source | Source analytics |
| `idx_jobs_posted_at` | jobs | posted_at (DESC) | Recency sort |
| `idx_jobs_active` | jobs | is_active (partial) | Active job filter |
| `idx_applications_status` | applications | status | Status filtering |
| `idx_applications_user` | applications | user_id | User app history |
| `idx_applications_job` | applications | job_id | Job app history |
| `idx_user_skills_user` | user_skills | (user_id, skill) UNIQUE | Dedup skills |
| `idx_user_skills_skill` | user_skills | skill | Skill analytics |
| `idx_interactions_user_time` | user_interactions | (user_id, created_at DESC) | Time-range queries for DQN |
| `idx_interactions_created` | user_interactions | created_at | Batch analytics |

---

### 1.7 Infrastructure Components

#### Docker Compose (`docker-compose.yml`)

```yaml
services:                          # 9 services defined
  frontend          → :3000        # Next.js (cap_drop ALL, read-only FS)
  api-gateway       → :8000        # Nginx reverse proxy
  ncf-service       → :8001        # Neural Collaborative Filtering
  sbert-service     → :8002        # Semantic BERT matching
  dqn-service       → :8003        # Deep Q-Network paths
  hybrid-service    → :8004        # Score blending + fairness
  pipeline-service  → :8005        # Job data scraping (APSched)
  postgres          → :5432        # PostgreSQL 15 (pgdata volume)
  redis             → :6379        # Redis 7 (redisdata volume)
```

**Security hardening applied:**
- All services: `cap_drop: [ALL]`, `read_only: true`, `tmpfs: /tmp`
- All services: `security_opt: [no-new-privileges:true]`
- All services: JSON-file logging with rotation (10MB × 3)
- All services: resource limits (CPU + memory)
- All services: health checks with retry logic

**Named volumes:**
- `pgdata` — PostgreSQL persistent data (driver: local)
- `redisdata` — Redis AOF/RDB persistence (driver: local)

#### Nginx Configuration (`infra/nginx.conf`)

| Feature | Configuration |
|---------|--------------|
| **Rate Limiting** | `api_limit`: 10 req/s per IP, `login_limit`: 5 req/s, `global_limit`: 100 req/s |
| **Connection Limits** | 50 concurrent connections per IP |
| **Proxy Timeouts** | Connect: 30s, Send: 60s, Read: 60s |
| **Security Headers** | HSTS, X-Frame-Options, XSS-Protection, CSP, Referrer-Policy, Permissions-Policy |
| **Hidden File Blocking** | Denies `.git`, `.env`, `.docker`, `Dockerfile` |
| **Upstreams** | `ncf_backend`, `sbert_backend`, `dqn_backend`, `hybrid_backend` |
| **Route Table** | `/api/ncf/*` → 8001, `/api/sbert/*` → 8002, `/api/dqn/*` → 8003, `/api/hybrid/*` → 8004 |

#### Redis Configuration (Recommended)

```conf
requirepass <REDIS_PASSWORD>          # Authentication
maxmemory 512mb                       # Memory cap
maxmemory-policy allkeys-lru          # LRU eviction
appendonly yes                        # AOF persistence
appendfsync everysec                  # Balanced durability
rename-command FLUSHALL ""            # Dangerous commands disabled
rename-command DEBUG ""
```

---

## SECTION 2: Use Cases & Implementation

### 2.1 Real-World Use Cases

| # | Use Case | Flow | AI Component |
|---|----------|------|-------------|
| 1 | **Personalized Job Recommendations** | User profile → Hybrid blending → Top-10 matched jobs | NCF + SBERT + Fairness |
| 2 | **Cold-Start Recommendations** | New user → Full SBERT mode (α=1.0) → Semantic matches | SBERT only (no interaction history needed) |
| 3 | **Career Path Planning** | Current skills → DQN state encoding → Adaptive step sequence | DQN (reinforcement learning) |
| 4 | **Job Application Tracking** | Submit application → Status lifecycle (SUBMITTED→REVIEWED→ACCEPTED/REJECTED) | PostgreSQL state machine |
| 5 | **Daily Job Aggregation** | APScheduler trigger → Scrape JobStreet/LinkedIn/Glints → Normalize → Store | Pipeline + NLP normalization |
| 6 | **Fair-Aware Filtering** | Recommend → Check TPR gap → Re-rank if gap > 8pp | Fairness constraint in hybrid service |
| 7 | **User Skill Gap Analysis** | Current skills vs target role → Missing skills identification → Course recommendations | DQN path optimization |

---

### 2.2 Quick Start Guide

> **Prerequisites:** Docker Desktop ≥ 4.25, Docker Compose ≥ 2.21, Git ≥ 2.40

#### Step 1: Clone the repository

```bash
git clone <repository-url>
cd SCPA
```

#### Step 2: Copy and configure environment file

```bash
# Copy the template
cp .env.example .env

# Edit the .env file with your secure values
vim .env  # or use any text editor

# At minimum, replace all "CHANGE_ME" values:
# - POSTGRES_PASSWORD: Use a strong, unique password
# - REDIS_PASSWORD: Use a strong, unique password
# - SECRET_KEY: Generate with: openssl rand -base64 64
# - JWT_SECRET: Generate with: openssl rand -base64 64
# - JWT_REFRESH_SECRET: Generate with: openssl rand -base64 64
```

#### Step 3: Validate environment

```bash
# Linux/macOS
bash scripts/validate_env.sh

# Windows PowerShell
.\scripts\validate_env.ps1
```

Expected output: All checks pass with ✓ marks.

#### Step 4: Build and start all services

```bash
# Detached mode (recommended)
docker compose up -d --build

# Attach mode (for debugging)
docker compose up --build
```

#### Step 5: Monitor startup

```bash
# Watch logs
docker compose logs -f

# Wait for health checks to pass (may take 60-90s for ML service init)
# Expected sequence:
#   1. postgres → healthy (pg_isready)
#   2. redis → healthy (redis-cli ping)
#   3. ncf-service → healthy (model loaded)
#   4. sbert-service → healthy (model loaded)
#   5. dqn-service → healthy
#   6. hybrid-service → healthy
#   7. pipeline-service → healthy
#   8. api-gateway → healthy
#   9. frontend → ready (on :3000)
```

#### Step 6: Verify the installation

```bash
# Run the automated health check script
python scripts/health_check.py

# Expected output:
# ✓ NCF Service: healthy
# ✓ SBERT Service: healthy
# ✓ DQN Service: healthy
# ✓ Hybrid Service: healthy
# ✓ API Gateway → NCF: healthy
# ✓ API Gateway → SBERT: healthy
# ✓ API Gateway → DQN: healthy
# ✓ API Gateway → Hybrid: healthy
# All 8 services healthy
```

#### Step 7: Access the application

- **Web UI:** [http://localhost:3000](http://localhost:3000)
- **API Gateway:** [http://localhost:8000/health](http://localhost:8000/health)
- **Direct NCF:** [http://localhost:8001/health](http://localhost:8001/health)
- **Direct Hybrid:** [http://localhost:8004/health](http://localhost:8004/health)

#### Step 8: Test the recommendation API

```bash
# Full hybrid recommendation request (see Section 2.3 for full examples)
curl -X POST http://localhost:8000/api/hybrid/recommend/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-001",
    "user_profile_text": "Data scientist with Python and ML experience",
    "is_new_user": false,
    "demographic_group": "majority",
    "job_candidates": [
      {"id": "job-001", "desc": "Machine Learning Engineer at TechCorp"},
      {"id": "job-002", "desc": "Data Analyst at FinanceCo"}
    ]
  }'
```

---

### 2.3 API Usage Examples

All examples use `http://localhost:8000` (API Gateway). Direct service URLs also work.

#### NCF Service — Neural Collaborative Filtering

**Health Check**
```bash
curl http://localhost:8000/api/ncf/health
```
```json
{
  "status": "healthy",
  "service": "ncf",
  "model_loaded": true
}
```

**Get Recommendations**
```bash
curl -X POST http://localhost:8000/api/ncf/recommend/ncf \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-12345",
    "n_items": 10
  }'
```
```json
{
  "user_id": "user-12345",
  "recommendations": [
    {"job_id": "job-0042", "score": 0.9781},
    {"job_id": "job-0137", "score": 0.9523},
    {"job_id": "job-0088", "score": 0.9312}
  ],
  "model_version": "ncf-v1.0"
}
```

**Get Model Metrics**
```bash
curl http://localhost:8000/api/ncf/metrics
```
```json
{
  "service": "ncf",
  "metrics": {
    "top_5_accuracy": 0.90,
    "ndcg_at_5": 0.93
  }
}
```

#### SBERT Service — Semantic Matching

**Health Check**
```bash
curl http://localhost:8000/api/sbert/health
```

**Get Semantic Matches**
```bash
curl -X POST http://localhost:8000/api/sbert/match/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "user_profile_text": "Senior data scientist with 5 years experience in Python, TensorFlow, and NLP. Masters degree in Computer Science.",
    "job_descriptions": [
      "Machine Learning Engineer needed. Requirements: Python, PyTorch, 3+ years ML experience.",
      "Frontend Developer. Requirements: React, TypeScript, CSS.",
      "Data Scientist. Requirements: Python, SQL, statistics, ML."
    ]
  }'
```
```json
{
  "scores": [
    {"job_index": 2, "score": 0.8912, "job_text_preview": "Data Scientist. Requirements: Python, SQL, statistics, ML..."},
    {"job_index": 0, "score": 0.7834, "job_text_preview": "Machine Learning Engineer needed. Requirements: Python, PyTorch..."},
    {"job_index": 1, "score": 0.4231, "job_text_preview": "Frontend Developer. Requirements: React, TypeScript, CSS..."}
  ],
  "model_version": "sbert-v1.0",
  "model_name": "paraphrase-multilingual-MiniLM-L12-v2"
}
```

#### DQN Service — Learning Path Generation

**Health Check**
```bash
curl http://localhost:8000/api/dqn/health
```

**Generate Learning Path**
```bash
curl -X POST http://localhost:8000/api/dqn/learning-path \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-12345",
    "current_skills": ["python", "statistics", "sql"],
    "interaction_history": ["viewed_job_ds", "clicked_course_ml"],
    "target_role": "Machine Learning Engineer",
    "experience_level": "mid"
  }'
```
```json
{
  "user_id": "user-12345",
  "learning_path": [
    {
      "step_id": 1,
      "action": "learn_ml",
      "description": "Pelajari Machine Learning Fundamentals",
      "estimated_duration": "3 bulan",
      "priority": 0.90,
      "skill_gain": ["Scikit-learn", "Statistics"]
    },
    {
      "step_id": 2,
      "action": "learn_dl",
      "description": "Deep Learning dan Neural Networks",
      "estimated_duration": "2 bulan",
      "priority": 0.85,
      "skill_gain": ["TensorFlow", "PyTorch"]
    }
  ],
  "total_steps": 2,
  "estimated_completion": "4 bulan",
  "model_version": "dqn-v1.0"
}
```

#### Hybrid Blending Service — Combined Recommendations

**Health Check**
```bash
curl http://localhost:8000/api/hybrid/health
```

**Get Hybrid Recommendations**
```bash
curl -X POST http://localhost:8000/api/hybrid/recommend/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-12345",
    "user_profile_text": "Data scientist with Python and ML experience",
    "is_new_user": false,
    "demographic_group": "majority",
    "job_candidates": [
      {"id": "job-001", "desc": "ML Engineer at TechCorp requiring Python and PyTorch"},
      {"id": "job-002", "desc": "Data Analyst at FinanceCo requiring SQL and Excel"},
      {"id": "job-003", "desc": "Senior Data Scientist at AI Startup requiring NLP and Transformers"}
    ]
  }'
```
```json
{
  "user_id": "user-12345",
  "recommendations": [
    {
      "job_id": "job-003",
      "hybrid_score": 0.9234,
      "sbert_score": 0.9102,
      "ncf_score": 0.9450,
      "alpha_used": 0.5
    },
    {
      "job_id": "job-001",
      "hybrid_score": 0.8812,
      "sbert_score": 0.8650,
      "ncf_score": 0.8500,
      "alpha_used": 0.5
    },
    {
      "job_id": "job-002",
      "hybrid_score": 0.6543,
      "sbert_score": 0.6200,
      "ncf_score": 0.8500,
      "alpha_used": 0.5
    }
  ],
  "fairness_tpr_gap": 3.0
}
```

#### Pipeline Service (Internal)

```bash
# Health check (direct)
curl http://localhost:8005/health
# Response: {"status": "healthy", "service": "pipeline"}
```

---

### 2.4 Environment Variable Reference

| Variable | Default | Scope | Description |
|----------|---------|-------|-------------|
| `APP_ENV` | `development` | All services | Application environment (`development`, `production`, `test`) |
| `LOG_LEVEL` | `INFO` | All services | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `json` | All services | Log output format (`json`, `text`) |
| `HEALTH_PORT` | `8005` | Pipeline service | Health check HTTP server port |
| `COMPOSE_PROJECT_NAME` | `scpa` | Docker Compose | Project namespace for containers |
| `POSTGRES_USER` | `scpa_user` | PostgreSQL container | Database superuser name |
| `POSTGRES_PASSWORD` | `scpa_pass` ⚠️ | PostgreSQL container | Database password (**MUST change**) |
| `POSTGRES_DB` | `scpa_db` | PostgreSQL container | Default database name |
| `DATABASE_URL` | See `.env.example` | Services (SQLAlchemy) | Full connection string: `postgresql+psycopg2://user:pass@host:5432/db` |
| `REDIS_PASSWORD` | `scpa_pass` ⚠️ | Redis container | Authentication password (**MUST change**) |
| `REDIS_URL` | See `.env.example` | Services | Connection URL: `redis://:pass@host:6379/0` |
| `SECRET_KEY` | — | App services | Flask/FastAPI session secret (32+ bytes) |
| `JWT_SECRET` | — | App services | JWT signing key (32+ bytes) |
| `JWT_ALGORITHM` | `HS256` | App services | JWT signing algorithm |
| `JWT_EXPIRY_HOURS` | `24` | App services | Access token TTL |
| `JWT_REFRESH_SECRET` | — | App services | JWT refresh token signing key |
| `JWT_REFRESH_EXPIRY_DAYS` | `30` | App services | Refresh token TTL |
| `NCF_SERVICE_URL` | `http://ncf-service:8001` | Hybrid service | NCF service base URL |
| `SBERT_SERVICE_URL` | `http://sbert-service:8002` | Hybrid service | SBERT service base URL |
| `DQN_SERVICE_URL` | `http://dqn-service:8003` | Hybrid service | DQN service base URL (future) |
| `HYBRID_SERVICE_URL` | `http://hybrid-service:8004` | Frontend | Hybrid service base URL |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend | Public API base URL (browser-accessible) |
| `MODEL_VERSION` | `ncf-v1.0` | NCF service | Model version identifier |
| `MODEL_NAME` | `paraphrase-multilingual-MiniLM-L12-v2` | SBERT service | HuggingFace model name |
| `SCRAPING_ENABLED` | `true` | Pipeline service | Enable/disable scraping |
| `SCRAPING_INTERVAL_HOURS` | `24` | Pipeline service | Hours between scraping runs |
| `JOBS_TARGET` | `5000` | Pipeline service | Target unique job count |
| `CORS_ORIGINS` | `http://localhost:3000` | Services | Allowed CORS origins (comma-separated) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Services | Extended CORS origins |
| `CORS_ALLOW_METHODS` | `GET,POST,PUT,DELETE,OPTIONS` | Services | Allowed HTTP methods |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Services | Allowed hostnames |
| `RATE_LIMIT_PER_MINUTE` | `60` | Services | Per-IP rate limit |
| `SENTRY_DSN` | — | All services | Sentry error tracking DSN |
| `OTEL_EXPORTER_ENDPOINT` | `http://localhost:4317` | All services | OpenTelemetry collector |
| `SMTP_HOST` | — | Future | SMTP server for email |
| `SMTP_PORT` | `587` | Future | SMTP port |

### 2.5 Configuration Guide

#### Development vs Production

| Setting | Development | Production |
|---------|-------------|------------|
| `APP_ENV` | `development` | `production` |
| `LOG_LEVEL` | `DEBUG` | `WARNING` |
| `LOG_FORMAT` | `text` (human-readable) | `json` (ELK-compatible) |
| `JWT_EXPIRY_HOURS` | `72` (long-lived for testing) | `1` (short-lived) |
| `JWT_REFRESH_EXPIRY_DAYS` | `60` | `7` |
| `SCRAPING_INTERVAL_HOURS` | `24` | `12` |
| Redis persistence | `appendonly no` (RDB only) | `appendonly yes` (AOF) |
| `maxmemory-policy` | `noeviction` | `allkeys-lru` |
| Nginx rate limits | Disabled or relaxed | Strict (`login_limit: 5r/s`) |
| `cap_drop` on containers | Optional | `[ALL]` enforced |
| `read_only` FS on containers | Optional | `true` enforced |
| PostgreSQL `max_connections` | 100 (default) | 200+ with PgBouncer |
| SSL/TLS | Self-signed | Let's Encrypt / ACM |
| Docker Compose | `docker compose up` | `docker compose up -d --build` |
| Secrets management | `.env` file (never committed) | Vault / AWS Secrets Manager / K8s Secrets |
| Health check intervals | 60s | 15-30s |
| Resource limits | Generous | Tight (see `docker-compose.yml`) |

---

## SECTION 3: Code Review & Technical Documentation

### 3.1 Module-by-Module Documentation

#### Module 1: NCF Service (`services/ncf/main.py`)

**File:** `services/ncf/main.py` (136 lines)
**Purpose:** Neural Collaborative Filtering — predicts user-job affinity from collective behavior patterns.

**Architecture:**
- Built with **FastAPI** (v0.68+)
- **NCFModel** class simulates a trained NCF model with:
  - GMF (Generalized Matrix Factorization) component: dot-product of user/item embeddings
  - MLP (Multi-Layer Perceptron) component: captures non-linear interactions (not yet implemented in mock)
- Embedding dimension: 64; User space: 10,000; Item space: 50,000
- Deterministic simulation via `hash(user_id) % num_users`

**Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST | `/recommend/ncf` | Generate top-N recommendations |
| GET | `/metrics` | Research metrics (accuracy, NDCG) |

**Request/Response Schema:**
- `NCFRequest`: `{user_id: str, n_items: int=10}`
- `NCFResponse`: `{user_id, recommendations: [NCFScore], model_version}`
- `NCFScore`: `{job_id: str, score: float}`

**Key observations:**
- Model is pure mock — embeddings are random with seed=42
- Production path documented in docstring: lookup → dot product → MLP → top-N
- Returns typed `NCFResponse` via FastAPI's `response_model`

---

#### Module 2: SBERT Service (`services/sbert/main.py`)

**File:** `services/sbert/main.py` (154 lines)
**Purpose:** Semantic BERT matching — computes cosine similarity between user profiles and job descriptions.

**Architecture:**
- **SBERTModel** class simulates sentence-transformers:
  - Embedding dimension: 384 (matching `paraphrase-multilingual-MiniLM-L12-v2`)
  - `encode()`: produces normalized random vectors (mock)
  - `compute_similarity()`: cosine similarity → normalized to [0.5, 1.0]
- Scores are sorted descending by relevance

**Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST | `/match/semantic` | Semantic similarity matching |
| GET | `/metrics` | Model metadata |

**Request/Response Schema:**
- `SBERTRequest`: `{user_profile_text: str, job_descriptions: List[str]}`
- `SBERTResponse`: `{scores: [SimilarityScore], model_version, model_name}`
- `SimilarityScore`: `{job_index: int, score: float, job_text_preview: str}`

**Key observations:**
- Cold-start α=1.0 documented (SBERT is the fallback for new users)
- Model name: `paraphrase-multilingual-MiniLM-L12-v2` (supports Bahasa Indonesia)
- Production integration point: `from sentence_transformers import SentenceTransformer`

---

#### Module 3: DQN Service (`services/dqn/main.py`)

**File:** `services/dqn/main.py` (167 lines)
**Purpose:** Deep Q-Network — constructs adaptive career learning paths via reinforcement learning.

**Architecture:**
- **DQNModel** class with predefined career path templates:
  - `data_science`: 6 steps (Python → SQL → ML → DL → Portfolio → Certification)
  - `frontend`: 5 steps (HTML/CSS → JavaScript → React → Testing → Portfolio)
  - `default`: 4-step generic career exploration path
- RL parameters: γ=0.99 (discount), ε=0.1 (exploration)
- Path filtering: removes steps where user already has all required skills

**Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST | `/learning-path` | Generate adaptive career path |
| GET | `/metrics` | DQN hyperparameters |

**Request/Response Schema:**
- `UserState`: `{user_id, current_skills: List[str], interaction_history: List[str], target_role: Optional[str], experience_level: str}`
- `DQNResponse`: `{user_id, learning_path: [CareerStep], total_steps, estimated_completion, model_version}`
- `CareerStep`: `{step_id, action, description, estimated_duration, priority, skill_gain: List[str]}`

**Key observations:**
- Skill-based routing: Python/ML → data_science, React/JS → frontend, else → default
- Production DQN would use experience replay buffer + target network
- State encoding and Q-network forward pass are documented but not yet implemented

---

#### Module 4: Hybrid Blending Service (`services/hybrid/main.py`)

**File:** `services/hybrid/main.py` (158 lines)
**Purpose:** Score aggregation using α-blending with fairness constraints (Equal Opportunity).

**Architecture:**
- **Blending formula:** `score = α × SBERT_score + (1-α) × NCF_score`
  - α = 1.0 for cold-start users (full content-based)
  - α = 0.5 for returning users (balanced hybrid)
- **FairnessTracker** class:
  - Monitors TPR across demographic groups
  - Constraint: TPR gap < 8 percentage points
  - Logs `fairness_tpr_gap` in response
- Would call NCF and SBERT services via `httpx.AsyncClient` (commented out in mock)

**Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST | `/recommend/hybrid` | Blended recommendation with fairness |
| GET | `/metrics` | CTR, fairness gap, latency |

**Request/Response Schema:**
- `HybridRequest`: `{user_id, user_profile_text, is_new_user: bool, demographic_group: Optional[str], job_candidates: List[{id, desc}]}`
- `HybridResponse`: `{user_id, recommendations: [HybridScore], fairness_tpr_gap}`
- `HybridScore`: `{job_id, hybrid_score, sbert_score, ncf_score, alpha_used}`

**Key observations:**
- This is the primary entry point from the frontend
- Implements the core business logic from the TA research
- Actual service-to-service calls are commented out (mock mode)

---

#### Module 5: Pipeline Service (`services/pipeline/main.py`)

**File:** `services/pipeline/main.py` (76 lines)
**Purpose:** Automated job data scraping and aggregation from JobStreet, LinkedIn, and Glints.

**Architecture:**
- **DataPipeline** class:
  - Target: 5,000 unique jobs
  - Domains: Technology, Digital, Data Analytics
  - Sources: JobStreet Indonesia, LinkedIn Jobs, Glints
- **APScheduler** (`BackgroundScheduler`): runs scraping every 24 hours
- Standalone health server using Python's `http.server.HTTPServer` (not FastAPI)
- PID file tracking at `/app/pipeline.pid`

**Key observations:**
- Scraping is simulated (`random.randint(100, 500)`)
- Production would use Selenium/Playwright for JS rendering
- Health endpoint served on `HEALTH_PORT` (default 8005) for Docker healthcheck
- No FastAPI dependency — minimal Python stdlib approach

---

#### Module 6: Pipeline Health Handler (`services/pipeline/health.py`)

**File:** `services/pipeline/health.py` (48 lines)
**Purpose:** Lightweight HTTP health check server for the pipeline service.

**Architecture:**
- Uses `http.server.HTTPServer` + `BaseHTTPRequestHandler`
- `/health` → 200 `{"status": "healthy", "service": "pipeline"}`
- Any other path → 404
- `write_pid()`: saves PID to `/app/pipeline.pid`
- Runs in a daemon thread
- Supports `HEALTH_PORT` environment variable

---

### 3.2 API Reference Table

All endpoints accessible via the Nginx API Gateway at `http://localhost:8000/api/<service>/...`

| Method | Route | Service | Auth | Description | Request Body | Response |
|--------|-------|---------|------|-------------|-------------|----------|
| GET | `/api/ncf/health` | NCF | None | NCF liveness check | — | `{status, service, model_loaded}` |
| POST | `/api/ncf/recommend/ncf` | NCF | None | NCF job recommendations | `{user_id, n_items?}` | `{user_id, recommendations: [{job_id, score}], model_version}` |
| GET | `/api/ncf/metrics` | NCF | None | Model performance metrics | — | `{service, metrics: {...}}` |
| GET | `/api/sbert/health` | SBERT | None | SBERT liveness check | — | `{status, service, model_loaded}` |
| POST | `/api/sbert/match/semantic` | SBERT | None | Semantic profile-job match | `{user_profile_text, job_descriptions: [str]}` | `{scores: [{job_index, score, job_text_preview}], model_version, model_name}` |
| GET | `/api/sbert/metrics` | SBERT | None | Model metadata | — | `{service, metrics}` |
| GET | `/api/dqn/health` | DQN | None | DQN liveness check | — | `{status, service, model_loaded}` |
| POST | `/api/dqn/learning-path` | DQN | None | Generate learning path | `{user_id, current_skills, interaction_history?, target_role?, experience_level?}` | `{user_id, learning_path: [{step_id, action, description, estimated_duration, priority, skill_gain}], total_steps, estimated_completion, model_version}` |
| GET | `/api/dqn/metrics` | DQN | None | DQN hyperparameters | — | `{service, metrics}` |
| GET | `/api/hybrid/health` | Hybrid | None | Hybrid liveness check | — | `{status, service}` |
| POST | `/api/hybrid/recommend/hybrid` |Hybrid | None | Blended job recommendations | `{user_id, user_profile_text, is_new_user, demographic_group?, job_candidates: [{id, desc}]}` | `{user_id, recommendations: [{job_id, hybrid_score, sbert_score, ncf_score, alpha_used}], fairness_tpr_gap}` |
| GET | `/api/hybrid/metrics` | Hybrid | None | CTR & fairness metrics | — | `{service, metrics}` |
| GET | `/health` | Gateway | None | Global health endpoint | — | `{"status":"ok","timestamp":"..."}` |

---

### 3.3 Design Patterns

| Pattern | Usage | Location | Rationale |
|---------|-------|----------|-----------|
| **Microservices** | 5 independent FastAPI services | All `services/*/main.py` | Independent deployment, scaling, and technology choices per domain |
| **API Gateway** | Nginx reverse proxy | `infra/nginx.conf` | Single entry point, rate limiting, security headers, routing abstraction |
| **CQRS-lite** | Read-heavy queries vs write-heavy pipeline | Services split by R/W concern | NCF/DB optimized for reads; pipeline optimized for writes; prevents read-write contention |
| **Repository Pattern** | DB access abstracted by service | Each service encapsulates data logic | Swap DB backend without changing business logic (future-ready for SQLAlchemy ORM) |
| **Cache-Aside** | Redis caching for recommendations | `docs/database/03-redis-cache-strategy.md` §3.6 | Fetch from cache first; compute and store on cache miss; TTL-based expiry |
| **Circuit Breaker** | Service-to-service calls (planned) | `docs/infrastructure/04-service-dependency-map.md` | Prevent cascade failures when downstream services are unavailable |
| **Health Check** | `/health` on every service | All service files | Docker healthcheck integration; load balancer health probes |
| **Configuration via Environment** | `.env` + `docker-compose.yml` env vars | `.env.example`, `docker-compose.yml` | 12-Factor App compliance; secrets externalized from code |
| **Pipeline/Event-Driven** | APScheduler for scraping jobs | `services/pipeline/main.py` | Scheduled data ingestion without blocking recommendation services |
| **α-Blending Strategy** | Hybrid recommendation fusion | `services/hybrid/main.py` | Tunable trade-off between collaborative (NCF) and content-based (SBERT) signals |
| **Fairness Constraint** | TPR parity enforcement | `FairnessTracker` class | Ensures recommendation quality parity across demographic groups |

---

### 3.4 Complexity Analysis

#### NCF Service — `recommend_ncf()`

| Step | Time Complexity | Space Complexity | Notes |
|------|----------------|-----------------|-------|
| User hash lookup | O(1) | O(1) | `hash(user_id) % num_users` |
| Embedding retrieval | O(1) | O(d) | d = embedding_dim (64) |
| Dot product (1000 items) | O(N·d) | O(N) | N = 1000 (capped item pool) |
| Normalization | O(N) | O(1) | Min-max scaling |
| Top-N sort | O(N log N) | O(k) | N = 1000, k = n_items ≤ 10 |
| **Total** | **O(N·d + N log N)** | **O(N)** | ≈ O(N·d) dominant term |

**Practical:** With N=1000, d=64 → ~64,000 multiply-adds + sort → **< 1ms** latency.
**Production at scale:** Full item space (50,000+) → vectorized (NumPy) + ANN (FAISS) for sub-linear approximate search.

#### SBERT Service — `compute_similarity()`

| Step | Time Complexity | Space Complexity | Notes |
|------|----------------|-----------------|-------|
| User embedding | O(T·d) | O(d) | T = token count in profile text |
| Job embeddings | O(J·T'·d) | O(J·d) | J = job count, T' = avg tokens per description |
| Cosine similarity | O(J·d) | O(J) | Matrix-vector dot product |
| Normalize + sort | O(J log J) | O(1) | Min-max + argsort |
| **Total** | **O(J·T'·d + J log J)** | **O(J·d)** | Dominated by SBERT encoding |

**Practical (mock):** Instant (random vectors). **Production with real SBERT:** ~50-200ms per batch on CPU, ~10ms on GPU for J=100 descriptions.

#### DQN Service — `predict_path()`

| Step | Time Complexity | Space Complexity | Notes |
|------|----------------|-----------------|-------|
| Skill matching | O(S·P) | O(1) | S = user skill count, P = path length |
| Path filtering | O(P·G) | O(P) | G = avg skill_gain per step |
| **Total** | **O(S·P + P·G)** | **O(P)** | Linear in path size |

**Practical:** Negligible — < 0.1ms. Path size is bounded (~6 steps).
**Production DQN forward pass:** O(L·H²) where L = layers, H = hidden dim → ~1-5ms on GPU.

#### Hybrid Service — `recommend_hybrid()`

| Step | Time Complexity | Space Complexity | Notes |
|------|----------------|-----------------|-------|
| NCF call (HTTP + compute) | O(N·d + N log N) | O(N) | See NCF analysis |
| SBERT call (HTTP + compute) | O(J·T'·d + J log J) | O(J·d) | See SBERT analysis |
| Score blending | O(min(N,J)) | O(min(N,J)) | Linear combination |
| Sort + trim | O(k log k) | O(k) | k = final top-10 |
| **Total** | **O(J·T'·d + J log J)** | **O(J·d)** | SBERT dominates |

#### Pipeline Service — `run_scraper()`

| Operation | Time Complexity | Notes |
|-----------|----------------|-------|
| Per-job scraping | O(1) per URL | Network-bound (100-500ms per page) |
| Total scrape | O(P) | P = number of pages scraped |
| DB insert | O(P) | Bulk batch insert |
| Redis invalidation | O(K) | K = number of cached keys to invalidate |

---

### 3.5 Security Hardening

#### Implemented Security Measures

| Layer | Measure | Location | Status |
|-------|---------|----------|--------|
| **Network** | Port binding to `127.0.0.1` only | `docker-compose.yml` | PostgreSQL (:5432), Redis (:6379) bound to localhost |
| **Container** | `cap_drop: [ALL]` | All services | Linux capability dropping |
| **Container** | `read_only: true` | All services | Immutable root filesystem |
| **Container** | `tmpfs: /tmp` | All services | Temporary filesystem isolation |
| **Container** | `no-new-privileges:true` | All services | Prevent privilege escalation |
| **Gateway** | Hidden file blocking | `nginx.conf` §86-111 | Denies `.git`, `.env`, `.docker`, `Dockerfile` |
| **Gateway** | XSS Protection headers | `nginx.conf` §31-41 | X-Frame-Options, CSP, HSTS, Referrer-Policy |
| **Gateway** | Rate limiting | `nginx.conf` §44-46 | Per-IP rate limits (100 req/s global, 10r/s API) |
| **Gateway** | Connection limits | `nginx.conf` §49 | 50 concurrent connections per IP |
| **DB** | Health check verification | `docker-compose.yml` | `pg_isready` before dependent services start |
| **Services** | Health check endpoints | All services | Docker-compose healthchecks with retry |
| **Logging** | JSON log rotation | All services | 10MB × 3 file rotation |
| **Secrets** | `.gitignore` exclusion | `.gitignore` `.env`, `.env.*` | Prevents accidental commits |

#### Known Security Issues (Requiring Remediation)

| Priority | Issue | Risk | Remediation |
|----------|-------|------|-------------|
| 🔴 CRITICAL | Hardcoded DB password `scpa_pass` in compose | Credential exposure | Use Docker secrets or Vault |
| 🔴 CRITICAL | Redis has no authentication | Unauthorized cache access | Set `requirepass` in Redis config |
| 🟠 HIGH | PostgreSQL credentials in plain text | Full DB compromise | Use `.env` file + `.gitignore` + secret manager |
| 🟠 HIGH | No SSL/TLS on Postgres connection | Network sniffing | Enable `sslmode=require`, mount certs |
| 🟠 HIGH | No SSL/TLS on Redis connection | Cache interception | Enable `stunnel` or Redis TLS |
| 🟡 MEDIUM | `root` logger level `WARN` in production | Missed error signals | Set `LOG_LEVEL=INFO` minimum in prod |
| 🟡 MEDIUM | No JWT token rotation mechanism | Stolen token replay | Implement refresh token rotation |
| 🟡 MEDIUM | No CORS in docker-compose | Cross-origin attacks | Add validated `CORS_ALLOWED_ORIGINS` |

#### Recommended Additional Measures

```yaml
# Docker Compose secrets (production)
services:
  postgres:
    secrets:
      - db_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password

secrets:
  db_password:
    file: ./secrets/pg_password.txt

# Or use Docker Swarm / Kubernetes Secrets in production
```

---

### 3.6 Coding Standards & Conventions

#### Python Code Style

| Convention | Standard | Enforcement |
|-----------|----------|-------------|
| **Formatter** | Black (88 chars line limit, Python 3.10+) | CI check |
| **Linter** | Pylint (min score 8.0) or Ruff | CI check |
| **Type hints** | PEP 484 — all function signatures | Mandatory |
| **Docstrings** | Google-style docstrings | Mandatory for public API |
| **Imports** | `stdlib → third-party → local`, sorted alphabetically | isort |
| **Naming** | `snake_case` variables, `PascalCase` classes, `SCREAMING_SNAKE_CASE` constants | PEP 8 |
| **Logging** | `logging.getLogger(__name__)`, never `print()` in production code | Mandatory |
| **Error handling** | `try/except` with specific exception types, log context, raise HTTPException | Mandatory |

#### FastAPI Conventions

- All endpoints return Pydantic models via `response_model=`
- Request validation through Pydantic `BaseModel`
- Async endpoints preferred (`async def route()`) for I/O-bound operations
- HTTP status codes: 200 (success), 400 (validation), 404 (not found), 500 (server error)
- Health endpoints return `{"status": "healthy", "service": "<name>"}` for consistency

#### Naming Conventions

| Resource | Pattern | Example |
|----------|---------|---------|
| Services | `<domain>-service` | `ncf-service`, `sbert-service` |
| Models | PascalCase singular | `NCFRequest`, `CareerStep` |
| Endpoints | `/<domain>/<action>` | `/recommend/ncf`, `/match/semantic` |
| Container names | `<service-name>` | `ncf-service`, `postgres` |
| Docker networks | Compose default (`scpa_default`) | — |
| Docker volumes | `<resource>data` | `pgdata`, `redisdata` |
| Indexes | `idx_<table>_<columns>` | `idx_applications_user` |
| Enums | Lowercase snake_case | `userrole`, `jobtype` |

#### Frontend Conventions (Next.js)

| Convention | Standard |
|-----------|----------|
| Router | App Router (`src/app/`) |
| Components | `src/components/` with PascalCase |
| Styles | Tailwind CSS v4 utility classes |
| State | React hooks (`useState`, `useEffect`) |
| API calls | `fetch` with base URL from `NEXT_PUBLIC_API_URL` |
| Build | Turbopack (Next.js default) or Webpack |

---

### 3.7 Testing Strategy

#### Test Pyramid

```
            ╱╲
           ╱  ╲         E2E Tests (Cypress/Playwright)
          ╱    ╲        Integration Tests (service-to-service)
         ╱      ╲       Unit Tests (pytest)
        ╱  ──   ╲      ──────────────────────────
       ╱          ╲     Test Coverage Target: ≥80%
```

#### Recommended Testing Framework

| Level | Tool | Scope |
|-------|------|-------|
| **Unit** | pytest + pytest-cov | Individual functions, model prediction logic, validation |
| **Integration** | pytest + httpx | Service-to-service HTTP calls, DB interactions |
| **E2E** | Cypress / Playwright | Full user flows through the frontend |
| **Contract** | Pact or Schemathesis | API schema compliance between services |
| **Load** | Locust / k6 | Stress testing recommendation endpoints |
| **Security** | Bandit (SAST) | Secret scanning, injection detection |

#### Current Test Status

> **⚠ No automated tests exist in this codebase.**

Test files have not been created. The following test files are recommended:

```
services/ncf/test_main.py
services/sbert/test_main.py
services/dqn/test_main.py
services/hybrid/test_main.py
services/pipeline/test_main.py
services/hybrid/test_fairness.py
services/shared/test_models.py
```

#### Example Test (recommended)

```python
"""Example unit test for NCF service — save as services/ncf/test_main.py"""
from ncf.main import NCFModel, NCFRequest

def test_ncf_recommendation_returns_correct_count():
    model = NCFModel()
    request = NCFRequest(user_id="test-user", n_items=5)
    result = model.predict(request.user_id, request.n_items)
    assert len(result) == 5
    assert all(hasattr(r, 'job_id') and hasattr(r, 'score') for r in result)

def test_ncf_scores_normalized():
    model = NCFModel()
    result = model.predict("test-user", 10)
    scores = [r.score for r in result]
    assert all(0.0 <= s <= 1.0 for s in scores)
```

---

### 3.8 CI/CD Pipeline Notes

#### Current Status

> **⚠ No CI/CD pipeline is configured.**

Based on `docs/infrastructure/07-ci-cd-infrastructure-plan.md`, the following pipeline is recommended:

#### Recommended GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: SCPA CI Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint Python
        run: pip install ruff && ruff check services/
      - name: Lint Dockerfile
        uses: hadolint/hadolint-action@v3

  test:
    needs: lint
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports: ["5432:5432"]
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pip install -r requirements.txt pytest pytest-cov httpx
          pytest services/ --cov=services/ --cov-report=xml

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: docker compose build

  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging
        run: ./scripts/deploy.sh staging

  deploy-production:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to production
        run: ./scripts/deploy.sh production
```

#### Recommended Branch Strategy

| Branch | Purpose | Protection |
|--------|---------|-----------|
| `main` | Production code | Required CI pass, 1 approval |
| `develop` | Staging / integration | Required CI pass |
| `feature/*` | Feature development | PR reviews required |
| `hotfix/*` | Emergency fixes | Fast-track merge to main |
| `release/*` | Release candidates | Tag + deploy |

#### Recommended Kubernetes Deployment

A Kubernetes manifest exists at `infra/k8s/ncf-deployment.yaml` for the NCF service. Full K8s manifests for all services should be created for production deployment with:
- Deployment objects with HPA (Horizontal Pod Autoscaler)
- Service objects (ClusterIP)
- Ingress via Nginx Ingress Controller
- ConfigMaps for non-secret configuration
- Secrets (base64-encoded) for passwords and keys
- Resource requests and limits
- Liveness and readiness probes

---

## Appendix

### Directory Structure

```
SCPA/
├── .env.example                    # Environment template (NEVER use in prod)
├── .gitignore                      # Excludes secrets, builds, IDE files
├── alembic.ini                     # Alembic configuration
├── docker-compose.yml              # Orchestration (9 services)
├── db/
│   ├── alembic/
│   │   └── env.py                  # Alembic environment config
│   ├── migrations/
│   │   ├── README.md               # Migration instructions
│   │   └── 001_initial_schema.py   # Initial schema (8 tables, 8 ENUMs)
│   └── models.py                   # SQLAlchemy models (TODO)
├── docs/                           # Full documentation
│   ├── architecture/               # Architecture diagrams & analysis
│   ├── database/                   # DB schema, caching, migration plans
│   ├── debugging/                  # Debugging guides per service
│   ├── design/                     # UI/UX design system specs
│   ├── execution/                  # Deployment & ops runbooks
│   ├── features/                   # Feature specifications
│   ├── infrastructure/             # Infra config, Docker, K8s, CI/CD
│   ├── security/                   # Security audit & hardening
│   ├── testing/                    # Testing strategies & plans
│   ├── README.md                   # Documentation index
│   └── MASTER.md                   # Master doc with critical findings
├── frontend/                       # Next.js 16 application
│   ├── src/
│   │   ├── app/                    # App Router pages
│   │   ├── components/             # React components
│   │   ├── lib/                    # Types, mock data, utilities
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   ├── next.config.ts
│   │   └── postcss.config.mjs
│   └── package.json
├── infra/
│   ├── nginx.conf                  # Nginx configuration (reverse proxy)
│   └── k8s/
│       └── ncf-deployment.yaml     # Kubernetes manifest (NCF example)
├── scripts/                        # Utility scripts
│   ├── generate_secrets.sh         # Secret generation helper
│   ├── health_check.py             # Multi-service health checker
│   ├── validate_env.sh             # Environment variable validation
│   └── validate_database.py        # Database structure validator
└── services/                       # Python microservices
    ├── ncf/
    │   └── main.py                 # Neural Collaborative Filtering (136 lines)
    ├── sbert/
    │   └── main.py                 # Semantic BERT matching (154 lines)
    ├── dqn/
    │   └── main.py                 # Deep Q-Network paths (167 lines)
    ├── hybrid/
    │   └── main.py                 # Score blending + fairness (158 lines)
    └── pipeline/
        ├── main.py                 # Job scraping pipeline (76 lines)
        └── health.py               # Health check endpoint (48 lines)
```

### Key Personnel & Development Notes

- **Academic Project:** Sistem Rekomendasi Pekerjaan Berbasis AI (Tugas Akhir / Final Thesis)
- **Research Focus:** Comparison of NCF, SBERT, and DQN for Indonesian job recommendation
- **Target Metrics:** Top-5 Accuracy ≥ 85%, NDCG@5 ≥ 0.90, Fairness TPR gap < 8pp
- **Current Status:** All ML models are in MOCK mode; production integration required
- **Known Critical Issues:** See [MASTER.md#🚨-critical-finding-summary](docs/MASTER.md#-critical-finding-summary)

### Support & Contributing

For issues, questions, or contributions, please follow the project's established development workflow and code review process as outlined in [docs/infrastructure/07-ci-cd-infrastructure-plan.md](docs/infrastructure/07-ci-cd-infrastructure-plan.md).