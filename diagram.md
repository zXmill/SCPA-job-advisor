# SCPA Architecture Documentation

> Generated from actual codebase audit. All diagrams reflect the real implementation as of the current commit.

---

## 1. Overview

SCPA (Smart Career Pathway Assistant) is an Indonesia-focused job recommendation system built as a modular microservices application. It combines three ML approaches — semantic similarity (SBERT), collaborative filtering (NCF), and reinforcement learning (DQN) — into a hybrid recommendation pipeline.

**Real tech stack**

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.2.6 + React + TypeScript + Tailwind CSS + Framer Motion |
| API Gateway | FastAPI (Python 3.12), port 8000 |
| Scraping | FastAPI + BeautifulSoup4 + httpx, port 8001 |
| Semantic Matching | FastAPI + sentence-transformers fallback + deterministic scoring, port 8002 |
| Collaborative Filtering | FastAPI + online matrix factorization (numpy), port 8003 |
| Reinforcement Learning | FastAPI + online linear Q-function (numpy), port 8004 |
| Pipeline Orchestrator | FastAPI + 5-stage HTTP pipeline, port 8005 |
| Database | PostgreSQL 15 (Alpine), port 5432 |
| Container Runtime | Docker Compose (7 services) |
| Auth | JWT (PyJWT) + bcrypt password hashing |

---

## 2. Architecture Diagram

### High-Level System Architecture

```mermaid
flowchart TD
    subgraph External
        User["User (Browser)"]
        JobBoards["Job Boards:<br/>LinkedIn, JobStreet,<br/>Glints, Kalibrr,<br/>Karir, TechInAsia,<br/>Indeed"]
    end

    subgraph DockerCompose["Docker Compose Network"]
        direction TB
        Frontend["Frontend<br/>Next.js 16<br/>Port 3000 (dev)"]
        Gateway["Gateway<br/>FastAPI<br/>Port 8000"]
        Pipeline["Pipeline<br/>FastAPI<br/>Port 8005"]
        Scraper["Scraper<br/>FastAPI<br/>Port 8001"]
        SBERT["SBERT<br/>FastAPI<br/>Port 8002"]
        NCF["NCF<br/>FastAPI<br/>Port 8003"]
        DQN["DQN<br/>FastAPI<br/>Port 8004"]
        Postgres["PostgreSQL 15<br/>Port 5432"]
    end

    subgraph OfflineAssets["Offline / Not in Compose"]
        HybridSvc["Hybrid Service<br/>Port NOT in compose<br/>Exists but unused"]
        Notebooks["Jupyter Notebooks<br/>(training/evaluation)"]
        Scripts["scripts/ (legacy runner)"]
    end

    User -->|HTTP| Frontend
    Frontend -->|REST API<br/>Bearer JWT| Gateway
    Gateway -->|SQLAlchemy async| Postgres
    Gateway -->|HTTP internal| Pipeline
    Pipeline -->|HTTP internal| Scraper
    Pipeline -->|HTTP internal| SBERT
    Pipeline -->|HTTP internal| NCF
    Pipeline -->|HTTP internal| DQN
    Scraper -->|HTTP external| JobBoards
    NCF -->|JSON file| WeightsVol["Docker Volume:<br/>weights"]
    DQN -->|JSON file| WeightsVol
    SBERT -->|Model files| WeightsVol
```

### Service Communication Matrix

| From | To | Protocol | Purpose |
|------|-----|----------|---------|
| Gateway | Pipeline | HTTP (httpx) | Recommendation requests, learning path |
| Gateway | Postgres | SQLAlchemy asyncpg | Auth, jobs, applications, profiles |
| Pipeline | Scraper | HTTP (httpx) | Fetch job candidates |
| Pipeline | SBERT | HTTP (httpx) | Encode profile + jobs, compute similarity |
| Pipeline | NCF | HTTP (httpx) | Score jobs via matrix factorization |
| Pipeline | DQN | HTTP (httpx) | Rerank jobs via Q-function |
| Scraper | Job boards | HTTP (httpx + BeautifulSoup) | Fetch live job listings |
| Frontend | Gateway | Fetch API | All data operations |

---

## 3. System Flowchart

### Full App Flow: User Action to Recommendation Result

```mermaid
flowchart LR
    A["User opens<br/>/recommendations"] --> B["Frontend<br/>Next.js page"]
    B --> C["Auth check:<br/>localStorage JWT"]
    C -->|"No token"| D["Redirect to /auth"]
    C -->|"Has token"| E["POST /api/recommendations<br/>with Bearer token"]
    E --> F["Gateway:<br/>1. Validate JWT<br/>2. Load user from DB<br/>3. Build profile payload"]
    F --> G["Gateway POST<br/>/pipeline/run"]
    G --> H["Pipeline Stage 1:<br/>Scrape or DB candidates"]
    H --> I["Pipeline Stage 2:<br/>SBERT encode + cosine similarity"]
    I --> J["Pipeline Stage 3:<br/>NCF predict scores"]
    J --> K["Pipeline Stage 4:<br/>DQN rank + Q-values"]
    K --> L["Pipeline Stage 5:<br/>Aggregate with skill alignment"]
    L --> M["Pipeline returns<br/>ranked jobs + scores"]
    M --> N["Gateway:<br/>1. Upsert jobs to DB<br/>2. Map to frontend schema"]
    N --> O["JSON response:<br/>recommendations[]"]
    O --> P["Frontend renders<br/>job cards + score bars"]
```

---

## 4. Data Flow Diagram

### How Data Moves Through the System

```mermaid
flowchart TD
    subgraph UserData["User Data"]
        UD1["Registration form:<br/>name, email, password"]
        UD2["Profile form:<br/>program_studi, university, skills"]
        UD3["Onboarding:<br/>step 1-3 data"]
    end

    subgraph JobData["Job Data"]
        JD1["Scraped HTML/JSON<br/>from job boards"]
        JD2["Normalized JobItem:<br/>title, company, location,<br/>description, tags, source_url"]
        JD3["Enriched job:<br/>+ salary_text, + full description"]
        JD4["DB jobs row:<br/>+ UUID, + match_data JSONB"]
    end

    subgraph MLData["ML / Interaction Data"]
        MD1["User profile text:<br/>name + program_studi + skills"]
        MD2["SBERT embeddings:<br/>384-dim float[]"]
        MD3["NCF factors:<br/>user_factors, item_factors,<br/>user_bias, item_bias"]
        MD4["DQN replay:<br/>state, action, reward,<br/>next_state, done"]
        MD5["Interaction events:<br/>view, click, apply, save,<br/>skip, dismiss"]
    end

    subgraph OutputData["Output Data"]
        OD1["Recommendations:<br/>job + hybrid_score +<br/>sbert_score + ncf_score +<br/>dqn_score + explanation"]
        OD2["Learning path:<br/>hardcoded skill sequence<br/>by target_role"]
        OD3["Job listings:<br/>paginated, filtered<br/>by location/experience"]
        OD4["Applications:<br/>user_id + job_id +<br/>status + applied_at"]
    end

    UD1 -->|"POST /api/auth/register"| DB_USERS["DB: users"]
    UD2 -->|"PUT /api/profile"| DB_USERS
    UD2 -->|"PUT /api/profile"| DB_SKILLS["DB: user_skills"]
    UD3 -->|"PUT /api/profile/onboarding"| DB_USERS

    JD1 -->|"httpx fetch"| Scraper
    Scraper -->|"extract_jobs()"| JD2
    JD2 -->|"_enrich_job_detail()"| JD3
    JD3 -->|"Pipeline / DB upsert"| JD4
    JD4 -->|"SELECT ... LIMIT/OFFSET"| GatewayJobs["Gateway /api/jobs"]

    MD1 -->|"/encode"| SBERT
    SBERT -->|"embeddings[]"| MD2
    MD2 -->|"cosine similarity"| PipelineEncode["Pipeline Stage 2"]
    PipelineEncode -->|"sbert_score"| PipelineNCF["Pipeline Stage 3"]
    PipelineNCF -->|"ncf_score"| PipelineDQN["Pipeline Stage 4"]
    PipelineDQN -->|"dqn_score"| PipelineAgg["Pipeline Stage 5"]

    MD5 -->|"POST /feedback"| NCF
    MD5 -->|"POST /feedback"| DQN
    MD5 -->|"INSERT"| DB_INTERACTIONS["DB: user_interactions"]

    PipelineAgg -->|"final_score + explanation"| OD1
    DQN -->|"/learning-path"| OD2
    DB_JOBS["DB: jobs"] -->|"Paginated query"| OD3
    DB_APPLICATIONS["DB: applications"] -->|"SELECT"| OD4
```

---

## 5. Sequence Diagram

### Runtime Interaction: User Opens Recommendations Page

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant FE as Frontend<br/>(Next.js /recommendations)
    participant GW as Gateway<br/>(FastAPI :8000)
    participant DB as PostgreSQL<br/>(:5432)
    participant PL as Pipeline<br/>(FastAPI :8005)
    participant SC as Scraper<br/>(FastAPI :8001)
    participant SB as SBERT<br/>(FastAPI :8002)
    participant NC as NCF<br/>(FastAPI :8003)
    participant DQ as DQN<br/>(FastAPI :8004)

    User->>FE: Navigate to /recommendations
    FE->>GW: POST /api/recommendations<br/>Authorization: Bearer {jwt}
    GW->>DB: SELECT users + user_skills<br/>WHERE id = token.sub
    DB-->>GW: user row + skills[]
    GW->>DB: SELECT COUNT(*) FROM user_interactions<br/>WHERE user_id = ?
    DB-->>GW: interaction_count
    GW->>PL: POST /pipeline/run<br/>{user_id, profile, interaction_count, limit}

    PL->>SC: GET /scrape/run?limit=250<br/>(or query DB jobs if refresh=false)
    SC-->>PL: ScrapeResponse {jobs[], count}
    PL->>PL: Build user profile text<br/>from program_studi + skills

    PL->>SB: POST /encode<br/>{texts: [profile_text, job_text1, ...]}
    SB-->>PL: EncodeResponse {embeddings[]}
    PL->>PL: Compute cosine similarity<br/>profile vs each job

    PL->>NC: POST /recommend/ncf<br/>{user_id, candidates[], profile_text, embedding}
    NC-->>PL: NCFResponse {recommendations[]}

    PL->>DQ: POST /rank<br/>{user_id, job_candidates[], session_ctx}
    DQ-->>PL: RankResponse {ranked[]}

    PL->>PL: Stage 5 Aggregate:<br/>dynamic weights + skill alignment<br/>+ penalty logic
    PL-->>GW: PipelineRunResponse<br/>{ranked[], timings_ms, stages}

    GW->>DB: INSERT/UPSERT jobs<br/>(ON CONFLICT DO UPDATE)
    DB-->>GW: OK
    GW-->>FE: {recommendations[], fairness_tpr_gap}
    FE-->>User: Render job cards<br/>with match % and score bars
```

---

## 6. Pipeline Flowchart

### ML and Scraping Pipeline (5 Stages)

```mermaid
flowchart TD
    Start["PipelineRunRequest<br/>{user_id, profile, limit}"] --> S1

    subgraph Stage1["Stage 1: Scrape / DB Candidates"]
        S1["run_scrape_stage"]
        S1a["If refresh=true:<br/>call Scraper /scrape/run"]
        S1b["If refresh=false:<br/>SELECT from DB jobs<br/>+ Indonesia filter"]
        S1 --> S1a
        S1 --> S1b
        S1a --> S1c["Normalize + deduplicate"]
        S1b --> S1c
    end

    subgraph Stage2["Stage 2: SBERT Encode"]
        S2["run_encode_stage"]
        S2a["POST /encode<br/>profile_text + job_texts"]
        S2b["Cosine similarity<br/>user_emb vs job_embs"]
        S2 --> S2a --> S2b
    end

    subgraph Stage3["Stage 3: NCF Score"]
        S3["run_ncf_score_stage"]
        S3a["POST /recommend/ncf<br/>{user_id, candidates}"]
        S3b["predict_one:<br/>sigmoid(dot(user_vec, item_vec) + bias)"]
        S3 --> S3a --> S3b
    end

    subgraph Stage4["Stage 4: DQN Rank"]
        S4["run_dqn_rank_stage"]
        S4a["POST /rank<br/>{user_id, candidates}"]
        S4b["Q-value per job<br/>normalize to [0,1]"]
        S4 --> S4a --> S4b
    end

    subgraph Stage5["Stage 5: Aggregate"]
        S5["run_aggregate_stage"]
        S5a["Dynamic weights:<br/>cold(0.75/0.2/0.05)<br/>warm(0.55/0.35/0.1)<br/>active(0.45/0.4/0.15)"]
        S5b["Skill alignment:<br/>token overlap + domain match<br/>+ penalty for mismatches"]
        S5c["Sort by final_score<br/>+ generate explanation"]
        S5 --> S5a --> S5b --> S5c
    end

    S1c --> S2
    S2b --> S3
    S3b --> S4
    S4b --> S5
    S5c --> End["PipelineRunResponse<br/>{ranked[], timings_ms, stages}"]
```

---

## 7. Database ERD

### Core Tables (from `db/models.py` and migrations 001-005)

```mermaid
erDiagram
    users ||--o{ user_skills : has
    users ||--o{ applications : has
    users ||--o{ user_interactions : has
    users ||--o{ user_job_interactions : has
    users ||--o{ dqn_session_logs : has
    users ||--o{ dqn_replay_archive : has
    jobs ||--o{ applications : receives
    jobs ||--o{ user_job_interactions : receives

    users {
        uuid id PK
        string name
        string email UK
        string password_hash
        string program_studi
        string university
        int completion_percent
        enum role
        boolean email_verified
        datetime last_login_at
        datetime created_at
        datetime updated_at
    }

    jobs {
        uuid id PK
        string title
        string company
        string company_logo
        string location
        enum type
        float min_salary
        float max_salary
        string salary_currency
        string salary_text
        enum employment_mode
        text description
        enum experience_level
        datetime posted_at
        enum source
        boolean is_active
        jsonb match_data
    }

    applications {
        uuid id PK
        uuid user_id FK
        uuid job_id FK
        enum status
        text cover_letter
        string resume_url
        string applied_via
        datetime applied_at
        datetime updated_at
    }

    user_skills {
        bigint id PK
        uuid user_id FK
        string skill
        enum category
        enum proficiency_level
        boolean endorsed
        datetime created_at
    }

    user_interactions {
        bigint id PK
        uuid user_id FK
        string action_type
        string target_type
        uuid target_id
        string session_id
        jsonb metadata
        datetime created_at
    }

    user_job_interactions {
        bigint id PK
        uuid user_id FK
        uuid job_id FK
        boolean clicked
        boolean saved
        boolean applied
        boolean dismissed
        float dwell_seconds
        datetime created_at
    }

    dqn_session_logs {
        bigint id PK
        string session_id
        uuid user_id FK
        jsonb session_history
        jsonb candidate_jobs
        jsonb rewards
        datetime created_at
    }

    dqn_replay_archive {
        bigint id PK
        uuid user_id FK
        float[] state
        int action
        float reward
        float[] next_state
        boolean done
        datetime created_at
    }

    hybrid_weights {
        bigint id PK
        float alpha
        float beta
        float gamma
        float ndcg_score
        boolean active
        datetime created_at
    }

    hybrid_request_log {
        bigint id PK
        string user_id
        int top_k
        int candidate_count
        int returned_count
        float latency_ms
        float estimated_cost_usd
        jsonb downstream_status
        datetime created_at
    }
```

### Table Summary

| Table | Source | Status | Notes |
|-------|--------|--------|-------|
| `users` | models.py + 001 | Active | Core auth/profile table |
| `jobs` | models.py + 001 + 004 + 005 | Active | `company_logo` added in 004, `salary_text` in 005 |
| `applications` | models.py + 001 | Active | User job applications |
| `user_skills` | models.py + 001 | Active | Many-to-one with users |
| `user_interactions` | models.py + 001 | Active | DQN training data (action logs) |
| `user_job_interactions` | 003 | Active | Fine-grained click/save/apply/dismiss |
| `dqn_session_logs` | 003 | Active | DQN session state |
| `dqn_replay_archive` | 003 | Active | DQN replay buffer persisted to DB |
| `hybrid_weights` | 003 | Exists but unused | No runtime code writes to this table |
| `hybrid_request_log` | 003 | Exists but unused | No runtime code writes to this table |

### Missing / Recommended Tables

| Table | Why Missing | Recommendation |
|-------|-------------|----------------|
| `cv_resumes` | No resume upload feature exists in frontend or gateway | Add if CV parsing is needed |
| `email_verifications` | Email verification flag exists but no email service is wired | Add SMTP integration first |
| `job_skills` | Skills are stored in `match_data` JSONB or inferred at runtime | Normalize if frequent skill queries needed |
| `career_paths` | DQN `/learning-path` returns hardcoded sequences | Persist user-generated paths if needed |

---

## 8. Focused Diagrams

### 8.1 Scraper Flow

```mermaid
flowchart TD
    A["SOURCE_QUERIES<br/>25+ queries (tech + non-tech)"] --> B["SOURCE_URL_TEMPLATES<br/>per-source URL generation"]
    B --> C["_configured_seed_urls()<br/>or SCRAPER_SEED_URLS env"]
    C --> D["async fetch<br/>httpx + User-Agent"]
    D --> E["_parse_fetched_content()<br/>HTML -> BeautifulSoup<br/>JSON -> direct parse"]
    E --> F["extract_jobs()<br/>JobItem {job_id, title, company,<br/>location, description, tags,<br/>source_url, content_hash}"]
    F --> G["Deduplicate by<br/>content_hash"]
    G --> H["_enrich_jobs_with_detail()<br/>Fetch source_url for full<br/>description + salary_text"]
    H -->|"Host allowlist check<br/>follow_redirects=False"| I["ScrapeResponse<br/>{count, jobs[], deduplicated}"]
```

**Key implementation details**

- `LOCAL_SOURCE_HOSTS` allowlist prevents SSRF in detail enrichment
- `INDONESIA_TERMS` filters for Indonesia-specific jobs
- `SOURCE_QUERIES` includes both tech (software engineer, python) and non-tech (HR, finance, marketing, nurse, teacher, legal)
- If no seeds configured, falls back to bundled HTML sample data
- Concurrency controlled by `SCRAPER_CONCURRENCY` semaphore (default 6)

### 8.2 SBERT Flow

```mermaid
flowchart TD
    A["User profile text:<br/>name + program_studi + skills"] --> B{"SBERT_ENABLE_TRANSFORMER=1?"}
    B -->|Yes| C["Load sentence-transformers<br/>paraphrase-multilingual-MiniLM-L12-v2"]
    B -->|No (default)| D["deterministic_embedding()<br/>Category scores + stable noise"]
    C --> E["model.encode(texts)<br/>384-dim float[]"]
    D --> F["_category_scores(tokens)<br/>+ _stable_noise(token)<br/>+ normalize"]
    E --> G["Cosine similarity<br/>profile_emb vs job_emb"]
    F --> G
    G --> H["Score in [0,1]<br/>via (cos + 1) / 2"]
    H --> I{"Redis configured?"}
    I -->|Yes| J["Cache embedding<br/>SHA256 key -> Redis"]
    I -->|No| K["Return directly"]
```

**Key implementation details**

- Two runtime modes: real transformer (requires `SBERT_ENABLE_TRANSFORMER=1`) or deterministic fallback
- Fallback uses 7 category aliases (communication, language, event, software, data, business, design) with Indonesian normalization
- Embedding dimension: 384
- Optional Redis caching with TTL (default 3600s)
- Endpoints: `POST /encode`, `POST /match/semantic`, `GET /metrics`

### 8.3 NCF Flow

```mermaid
flowchart TD
    A["POST /recommend/ncf<br/>{user_id, candidates[], profile_text}"] --> B["OnlineNCF.recommend()"]
    B --> C["_user_vector()<br/>If new user:<br/>seed from profile_text/embedding"]
    C --> D["_item_vector()<br/>For each candidate job:<br/>seed from job embedding/text"]
    D --> E["predict_one()<br/>sigmoid(dot(user_vec, item_vec)<br/>+ user_bias + item_bias + global_bias)"]
    E --> F["Sort by score<br/>Return top N"]
    F --> G["NCFResponse<br/>{recommendations[{job_id, score}]}"]

    H["POST /feedback<br/>{user_id, job_id, event}"] --> I["OnlineNCF.learn_one()<br/>SGD update"]
    I --> J["user_factors += lr * (error * item_vec - reg * user_factors)"]
    I --> K["item_factors += lr * (error * old_user - reg * item_factors)"]
    J --> L["model.save()<br/>-> online_ncf.json"]
    K --> L
```

**Key implementation details**

- Online matrix factorization with SGD on implicit feedback
- Factor dimension: 64 (configurable via `NCF_FACTOR_DIM`)
- Learning rate: 0.045, Regularization: 0.0005
- Event targets: apply=1.0, click=1.0, save=0.85, view=0.45, skip=0.02
- Persisted to `online_ncf.json` (JSON file, not DB)
- NeuralCF PyTorch class exists but is not used in the online path (numpy path is active)

### 8.4 DQN Flow

```mermaid
flowchart TD
    A["POST /rank<br/>{user_id, job_candidates[], session_ctx}"] --> B["OnlineDQN.rank()"]
    B --> C["Build feature vector<br/>per job:<br/>embedding[0:64] +<br/>6 hand-crafted features"]
    C --> D["Q = dot(weights, features)<br/>(linear Q-function)"]
    D --> E["Sort by Q-value<br/>Return ranked[]"]

    F["POST /feedback<br/>{user_id, job_id, event}"] --> G["OnlineDQN.learn()"]
    G --> H["Compute reward from<br/>EVENT_REWARDS table"]
    H --> I["Add to replay buffer<br/>(deque, max 5000)"]
    I --> J["SGD on MSE loss:<br/>weights += lr * error * feature"]
    J --> K["Soft update target_weights<br/>tau=0.05"]
    K --> L["agent.save()<br/>-> online_dqn.json"]
```

**Key implementation details**

- Linear Q-function (no hidden layers in production), not the QNetwork class
- Feature dimension: 64 + 6 = 70
- Replay buffer: deque(maxlen=5000)
- Learning rate: 0.03, Gamma: 0.92
- Persisted to `online_dqn.json`
- `/learning-path` is hardcoded skill sequences by role (data scientist, backend, frontend, business analyst, MC, etc.)

### 8.5 Hybrid / Aggregation Flow

```mermaid
flowchart TD
    A["Stage 5: run_aggregate_stage"] --> B["dynamic_weights()<br/>Based on interaction_count"]
    B --> C["Cold: 0.75 SBERT / 0.20 NCF / 0.05 DQN"]
    B --> D["Warm: 0.55 SBERT / 0.35 NCF / 0.10 DQN"]
    B --> E["Active: 0.45 SBERT / 0.40 NCF / 0.15 DQN"]
    C --> F["_alignment()<br/>Token overlap + domain match"]
    D --> F
    E --> F
    F --> G["final_score =<br/>base_score + 0.18*alignment<br/>- penalty"]
    G --> H["Sort descending<br/>Generate explanation[]"]
    H --> I["AggregateStageResult<br/>{ranked[], summary}"]
```

**Note on the standalone Hybrid service**

- `services/hybrid/main.py` exists as a standalone FastAPI service
- It has circuit breaker logic, fairness tracking, and fallback scoring
- **It is NOT in docker-compose.yml and is NOT called by the pipeline**
- The pipeline uses `stage_5_aggregate.py` for aggregation instead
- The hybrid service is effectively disconnected from the runtime architecture

### 8.6 API Endpoint Flow

#### Gateway Endpoints (`services/gateway/main.py`)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/` | root | Service info |
| GET | `/health` | health | Health check |
| GET | `/ready` | ready | Ready check (probes pipeline) |
| GET | `/api/company-logo` | proxy_company_logo | Logo proxy with host allowlist |
| POST | `/api/auth/register` | register | Create user + return JWT |
| POST | `/api/auth/login` | login | Verify password + return JWT |
| GET | `/api/auth/me` | me | Return current user + skills |
| PUT | `/api/profile` | update_profile | Update user profile + skills |
| PUT | `/api/profile/onboarding` | onboarding | Save onboarding step data |
| GET | `/api/jobs` | get_jobs | Paginated job listings (Indonesia filter in SQL) |
| GET | `/api/jobs/{job_id}` | get_job | Single job detail |
| GET | `/api/applications` | get_applications | User's applications |
| POST | `/api/applications` | create_applications | Submit applications |
| POST | `/api/learning-path` | learning_path | Calls DQN /learning-path directly |
| POST | `/api/recommendations` | run_pipeline | Calls Pipeline /pipeline/run |
| POST | `/pipeline/run` | run_pipeline_direct | Direct pipeline proxy |

#### Pipeline Endpoints (`services/pipeline/main.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health + downstream status |
| POST | `/pipeline/run` | Run full 5-stage pipeline |
| GET | `/training/status` | Continual training state |
| POST | `/training/run-once` | Trigger one training cycle |
| POST | `/feedback` | Forward feedback to NCF + DQN |

#### Scraper Endpoints (`services/scraper/main.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health + seed config |
| POST | `/scrape/html` | Extract jobs from provided HTML |
| POST | `/scrape/url` | Fetch URL then extract jobs |
| POST | `/scrape/run` | Run full scrape cycle |
| GET | `/sample` | Return bundled sample jobs |

#### SBERT Endpoints (`services/sbert/main.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/match/semantic` | Score user vs job descriptions |
| POST | `/encode` | Encode texts to embeddings |
| GET | `/metrics` | Service metrics |

#### NCF Endpoints (`services/ncf/main.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/jobs/upsert` | Add/update job item factors |
| POST | `/feedback` | Record feedback event + SGD update |
| POST | `/train` | Trigger training batch |
| POST | `/predict` | Predict score for single user-job pair |
| POST | `/recommend/ncf` | Recommend top-N for user |
| POST | `/users/{user_id}/invalidate` | Remove user factors (e.g., profile change) |
| GET | `/model/status` | Model metrics |

#### DQN Endpoints (`services/dqn/main.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/jobs/upsert` | Add/update job features |
| POST | `/rank` | Rank candidates by Q-value |
| POST | `/learning-path` | Return hardcoded skill sequence |
| POST | `/rerank` | Rerank with session history |
| POST | `/reward` | Record reward + learn |
| POST | `/feedback` | Alias for /reward |
| POST | `/train` | Soft update + save |
| GET | `/model/status` | Model metrics |

### 8.7 Frontend Page / Component Flow

```mermaid
flowchart TD
    subgraph Pages["App Router Pages"]
        P1["/ (Landing)"]
        P2["/auth (Login/Register)"]
        P3["/onboarding (3 steps)"]
        P4["/dashboard"]
        P5["/profile"]
        P6["/analytics (Job Listings)"]
        P7["/recommendations"]
        P8["/jobs/[id] (Detail)"]
        P9["/apply (Multi-select)"]
    end

    subgraph Layout["Shared Layout"]
        L1["AppLayout<br/>Navbar + Footer"]
        L2["AuthProvider<br/>(React Context)"]
        L3["api.ts<br/>(ApiClient singleton)"]
    end

    subgraph Components["UI Components"]
        C1["GlassCard, Button, Badge"]
        C2["CompanyLogo, Avatar"]
        C3["MatchScore, MatchDonut"]
        C4["Pagination"]
        C5["PageHeader"]
    end

    P2 -->|"JWT stored in<br/>localStorage"| L2
    L2 -->|"api.setToken()"| L3
    P4 -->|"GET /api/recommendations<br/>GET /api/applications"| L3
    P6 -->|"GET /api/jobs?page=&limit="| L3
    P7 -->|"POST /api/recommendations"| L3
    P8 -->|"GET /api/jobs/{id}"| L3
    P9 -->|"GET /api/jobs<br/>POST /api/applications"| L3
    P5 -->|"PUT /api/profile"| L3
```

**Frontend route mapping**

| Page | API Calls | Key Feature |
|------|-----------|-------------|
| `/` | None | Marketing landing |
| `/auth` | `POST /api/auth/login`, `POST /api/auth/register` | JWT auth |
| `/onboarding` | `PUT /api/profile/onboarding` | Step 1-3 wizard |
| `/dashboard` | `POST /api/recommendations`, `GET /api/applications`, `POST /api/learning-path` | Overview + quick actions |
| `/profile` | `GET /api/auth/me`, `PUT /api/profile` | Edit skills + program |
| `/analytics` | `GET /api/jobs` | Job listings + filters + pagination |
| `/recommendations` | `POST /api/recommendations` | ML recommendations with score breakdown |
| `/jobs/[id]` | `GET /api/jobs/{id}` | Job detail + apply link |
| `/apply` | `GET /api/jobs`, `POST /api/applications` | Multi-select application submit |

### 8.8 Docker / Runtime Flow

```mermaid
flowchart TD
    subgraph DockerHost["Docker Host"]
        subgraph ComposeFile["docker-compose.yml"]
            Postgres["postgres:15-alpine<br/>5432:5432<br/>Volume: postgres_data"]
            Gateway["gateway<br/>8000:8000<br/>DependsOn: postgres, pipeline"]
            Scraper["scraper<br/>8001:8001<br/>No depends_on"]
            SBERT["sbert<br/>8002:8002<br/>Volume: weights"]
            NCF["ncf<br/>8003:8003<br/>Volume: weights"]
            DQN["dqn<br/>8004:8004<br/>Volume: weights"]
            Pipeline["pipeline<br/>8005:8005<br/>DependsOn: scraper, sbert, ncf, dqn"]
        end
    end

    subgraph StartupOrder["Startup Order"]
        S1["1. Postgres<br/>healthcheck: pg_isready"]
        S2["2. Scraper, SBERT, NCF, DQN<br/>(in parallel)"]
        S3["3. Pipeline<br/>healthcheck: /health"]
        S4["4. Gateway<br/>healthcheck: /health"]
    end

    S1 --> S2
    S2 --> S3
    S3 --> S4
```

**Docker Compose services**

| Service | Image | Build Context | Ports | Environment Key |
|---------|-------|--------------|-------|----------------|
| postgres | postgres:15-alpine | N/A | 5432 | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| gateway | Dockerfile | `./services/gateway` | 8000 | `PIPELINE_URL`, `DATABASE_URL`, `JWT_SECRET` |
| scraper | Dockerfile | `./services/scraper` | 8001 | `SCRAPER_SEED_URLS`, `JOBS_TARGET` |
| sbert | Dockerfile | `./services/sbert` | 8002 | `MODEL_NAME`, `SBERT_ENABLE_TRANSFORMER` |
| ncf | Dockerfile | `./services/ncf` | 8003 | `MODEL_DIR` |
| dqn | Dockerfile | `./services/dqn` | 8004 | `MODEL_DIR` |
| pipeline | Dockerfile | `./services/pipeline` | 8005 | `SCRAPER_URL`, `SBERT_URL`, `NCF_URL`, `DQN_URL` |

**No Redis container** is defined in docker-compose.yml. Redis is optional in SBERT only.

**No Celery/RabbitMQ/Kafka** is used anywhere in the runtime.

### 8.9 Evaluation Metrics Flow

```mermaid
flowchart TD
    A["services/evaluation/<br/>recommendation_metrics.py"] --> B["precision_at_k()"]
    A --> C["recall_at_k()"]
    A --> D["hit_rate_at_k()"]
    A --> E["ndcg_at_k()"]
    A --> F["average_precision_at_k()"]

    B --> G["notebooks/<br/>evaluation_metrics_validation.ipynb"]
    C --> G
    D --> G
    E --> G
    F --> G

    G --> H["reports/<br/>evaluation_artifacts/"]
    G --> I["notebooks/training_runs/<br/>readiness_metrics.json"]
    G --> J["notebooks/training_runs/<br/>readiness_report.html"]
```

**Evaluation artifacts**

| Path | Type | Purpose |
|------|------|---------|
| `services/evaluation/recommendation_metrics.py` | Python module | Reusable metrics functions |
| `notebooks/evaluation_metrics_validation.ipynb` | Jupyter notebook | Metric validation with charts |
| `notebooks/scpa_ml_readiness_evaluation.ipynb` | Jupyter notebook | Full ML readiness evaluation |
| `notebooks/training_runs/readiness/` | Directory | PNG figures + JSON metrics |
| `reports/evaluation_artifacts/` | Directory | Generated evaluation reports |
| `reports/full_pipeline_artifacts/` | Directory | Full pipeline run outputs |

---

## 9. Legacy or Unused Components

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| Hybrid service | `services/hybrid/main.py` | Exists but disconnected | Not in docker-compose, not called by pipeline. Pipeline uses `stage_5_aggregate.py` instead. |
| Hybrid DB tables | `hybrid_weights`, `hybrid_request_log` | Created by migration 003 but unused | No code writes or reads these tables |
| Full pipeline scripts | `scripts/run_full_pipeline.py`, `scripts/retrain_pipeline.py`, `scripts/demo_pipeline.py` | Legacy | Pipeline now orchestrates via HTTP internally; scripts may be stale |
| Sample dataset | `data/sample/` | Legacy | Used by notebooks and old scripts; runtime uses live scraper + DB |
| Training scripts | `services/*/training/train*.py` | Offline only | Used to generate initial weights; not part of Docker runtime |
| Notebooks | `notebooks/*.ipynb` | Offline only | Training, evaluation, and validation notebooks |
| Kubernetes configs | `infra/k8s/` | Exists but unused | No evidence of K8s deployment |
| Nginx config | `infra/nginx.conf` | Exists but unused | No nginx container in compose |
| Browser E2E scripts | `browser_e2e.py`, `browser_screenshots/` | Temporary debug | Not part of the application |
| Insert scripts | `insert_scraped.py`, `check_scrape.py`, `check_overflow.py` | Temporary debug | One-off data operations |
| `services/shared/auth.py` | Shared module | Partially used | Contains auth utilities; gateway has its own auth logic too |
| PyTorch model classes | `NeuralCF` in `services/ncf/main.py`, `QNetwork` in `services/dqn/main.py` | Defined but not used in production | Runtime uses numpy-based online models |

---

## 10. Implementation Notes and Gotchas

### What is different from the "planned" architecture

1. **Hybrid service is not used**: The standalone `services/hybrid/main.py` exists but the pipeline uses `stage_5_aggregate.py` for scoring. The hybrid service's circuit breaker and fairness tracker are not in the active data path.

2. **DQN is a linear model, not a deep network**: The `QNetwork` PyTorch class is defined but never instantiated in production. The active `OnlineDQN` uses a simple linear weight vector and SGD.

3. **NCF is numpy-based matrix factorization, not the PyTorch NeuralCF**: Similar to DQN, the `NeuralCF` class exists but the runtime uses `OnlineNCF` with numpy arrays and SGD.

4. **SBERT defaults to deterministic fallback**: The transformer model is only loaded when `SBERT_ENABLE_TRANSFORMER=1`. By default, the service uses deterministic token-category scoring without downloading any model weights.

5. **Learning path is hardcoded**: The DQN `/learning-path` endpoint returns pre-defined skill sequences per role. It does not dynamically generate paths based on market data or user progress.

6. **No message queue**: There is no Celery, RabbitMQ, or Kafka. All inter-service communication is synchronous HTTP via httpx.

7. **No real email service**: SMTP configuration exists in `.env.example` but no email sending code exists in the gateway.

8. **No CV/resume parsing**: There is no upload endpoint, no CV table, and no parsing service.

9. **Analytics page shows job listings, not analytics**: The `/analytics` route in the frontend renders the job listing page with filters and pagination. There are no charts, dashboards, or skill-demand analytics.

10. **Continual training is just re-scraping**: The pipeline's `_continual_training_loop()` re-runs the scraper + encoder + upserts to NCF/DQN on a timer. It does not perform model retraining from scratch.

---

## 11. File Inventory

### Key source files by service

| Service | Key Files |
|---------|-----------|
| Gateway | `services/gateway/main.py` |
| Scraper | `services/scraper/main.py` |
| SBERT | `services/sbert/main.py` |
| NCF | `services/ncf/main.py` |
| DQN | `services/dqn/main.py` |
| Pipeline | `services/pipeline/main.py`, `services/pipeline/stages/stage_1_scrape.py` through `stage_5_aggregate.py` |
| Hybrid (unused) | `services/hybrid/main.py` |
| DB Models | `db/models.py` |
| Migrations | `db/migrations/001_initial_schema.py` through `005_add_salary_text.py` |
| Frontend API | `frontend/src/lib/api.ts` |
| Frontend Auth | `frontend/src/lib/auth-context.tsx` |
| Evaluation | `services/evaluation/recommendation_metrics.py` |

### Configuration files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | 7-service compose definition |
| `.env.example` | Environment variable template |
| `alembic.ini` | Database migration config |
| `requirements.txt` | Root Python dependencies |
| `frontend/package.json` | Next.js dependencies |
| `frontend/next.config.ts` | Next.js config |
| `frontend/tailwind.config.ts` | Tailwind CSS config |

---

*End of architecture documentation. This file was generated by auditing the actual codebase, not from an ideal or planned version of the system.*
