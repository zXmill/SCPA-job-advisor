# SCPA Detailed System Diagram

This document explains the current SCPA project as it exists in code today.
It is written for two audiences at the same time:

- Non-technical readers can follow the plain-language story and the simple diagrams.
- Technical reviewers can trace each feature to the service, endpoint, data store, and model path that implements it.

## How to Read This File

SCPA means Smart Career Pathway Assistant. The app helps a student or job seeker create a profile, find Indonesian job listings, and receive ranked job recommendations.

The project uses service names such as SBERT, NCF, and DQN. Those names are useful shorthand, but the current implementation has important runtime differences:

| Label in this document | Meaning |
|---|---|
| Active runtime | Used by the frontend, gateway, Docker Compose, or the pipeline API. |
| Optional runtime | Can be enabled by environment variable or manual command. |
| Offline/demo | Used by scripts, notebooks, generated reports, or thesis/demo runs. |
| Disconnected | Code exists, but is not currently called by the active runtime path. |
| Risk | A behavior that may mislead users, evaluators, or future developers if not documented. |

## One-Screen Summary

```mermaid
flowchart LR
    Person["Student or job seeker"] --> Browser["Browser UI<br/>Next.js frontend"]
    Browser --> Gateway["API Gateway<br/>FastAPI"]
    Gateway --> DB["PostgreSQL<br/>users, jobs, skills, applications"]
    Gateway --> Pipeline["Recommendation Pipeline<br/>FastAPI"]
    Pipeline --> Scraper["Scraper<br/>collects job candidates"]
    Pipeline --> SBERT["SBERT service<br/>semantic text matching"]
    Pipeline --> NCF["NCF service<br/>online user-item factor scoring"]
    Pipeline --> DQN["DQN service<br/>online Q-style reranking"]
    Pipeline --> Aggregator["Stage 5 aggregator<br/>final score and explanation"]
    Aggregator --> Gateway
    Gateway --> Browser
```

Plain-language version:

1. The user logs in and fills out a profile.
2. The frontend asks the gateway for recommendations.
3. The gateway loads the user's profile and skills from the database.
4. The gateway asks the pipeline to rank jobs.
5. The pipeline gathers job candidates, scores them with SBERT, NCF, and DQN-style signals, then combines the scores.
6. The gateway stores or updates the recommended jobs in PostgreSQL.
7. The frontend shows job cards with match percentage, score breakdown, company logo, and explanation text.

## Project Map

| Area | Path | What it owns | Runtime status |
|---|---|---|---|
| Frontend app | `frontend/src/app/` | Pages for auth, onboarding, dashboard, profile, jobs, applications, recommendations | Active runtime |
| Frontend API client | `frontend/src/lib/api.ts` | Browser-to-gateway calls and JWT storage | Active runtime |
| Gateway | `services/gateway/main.py` | Auth, profile, jobs, applications, recommendation proxy, logo proxy | Active runtime |
| Pipeline | `services/pipeline/main.py` | Orchestrates scraper -> SBERT -> NCF -> DQN -> aggregate | Active runtime |
| Pipeline stages | `services/pipeline/stages/` | Individual recommendation stages | Active runtime |
| Scraper | `services/scraper/main.py` | Extracts and normalizes job listings | Active runtime |
| SBERT service | `services/sbert/main.py` | Text embeddings and semantic similarity | Active runtime, with optional transformer |
| NCF service | `services/ncf/main.py` | Online matrix-factor user-job scoring | Active runtime |
| DQN service | `services/dqn/main.py` | Online Q-style job reranking and its own hardcoded learning path endpoint | Active runtime, but not used by gateway learning path |
| Hybrid service | `services/hybrid/main.py` | Separate hybrid API with circuit-breaker/fairness ideas | Disconnected from Docker and active pipeline |
| Database models | `db/models.py` | SQLAlchemy model definitions | Active for gateway and migrations |
| Migrations | `db/migrations/` | PostgreSQL schema changes | Active setup path |
| Evaluation | `services/evaluation/recommendation_metrics.py` | Ranking metrics such as Precision@K, Recall@K, NDCG@K | Offline/demo |
| Scripts | `scripts/` | Training, full pipeline demo, verification, reports | Offline/demo |
| Notebooks | `notebooks/` | ML readiness and metric reports | Offline/demo |
| Reports | `reports/` | Generated metrics, recommendations, artifacts, research extraction | Offline/demo |

## Feature Inventory

| Feature | User-facing result | Primary code path | Data touched | Current caveat |
|---|---|---|---|---|
| Registration | User creates account and receives JWT | `POST /api/auth/register` in gateway | `users` | No email verification flow is wired. |
| Login | User receives access token | `POST /api/auth/login` | `users.last_login_at` | Token is stored in browser localStorage. |
| Current user | Frontend gets profile and skills | `GET /api/auth/me` | `users`, `user_skills` | Skills are returned as structured rows. |
| Profile edit | User updates name, study program, university, skills | `PUT /api/profile` | `users`, `user_skills` | Gateway invalidates NCF user factor best-effort. |
| Onboarding | Three-step profile completion | `PUT /api/profile/onboarding` | `users`, `user_skills` | Step 3 only updates completion percent. |
| Job listing | User browses paginated jobs | `GET /api/jobs` | `jobs.match_data` | SQL filters for Indonesian sources/locations. |
| Job detail | User opens a job page | `GET /api/jobs/{job_id}` | `jobs` | String job IDs are mapped to stable UUIDs. |
| Apply to jobs | User submits selected jobs | `POST /api/applications` | `applications` | Application creation is not forwarded as model feedback. |
| Recommendations | User sees ranked jobs and score bars | `POST /api/recommendations` -> pipeline | `users`, `user_skills`, `jobs`, model JSON weights | Gateway returns an empty list if pipeline is unavailable. |
| Learning path | Dashboard suggests skills to learn | `POST /api/learning-path` in gateway | `user_skills` | Gateway uses hardcoded rule-based list, not the DQN service. |
| Company logo proxy | Browser loads safe company logos | `GET /api/company-logo` | External image host | Only allowlisted HTTPS logo hosts are proxied. |
| Background scraping/training | Pipeline periodically refreshes job candidates | `_continual_training_loop()` in pipeline | `jobs`, NCF/DQN JSON files | This refreshes/upserts jobs and model inputs; it is not full retraining. |
| Offline reports | Thesis/demo metrics and artifacts | `scripts/run_full_pipeline.py`, notebooks | `reports/`, `notebooks/training_runs/` | Metrics are sample/demo dependent. |

## Runtime Architecture

```mermaid
flowchart TB
    subgraph External["Outside Docker / Browser"]
        User["User"]
        Browser["Next.js frontend<br/>localhost:3000 in dev"]
        JobBoards["Public job boards<br/>LinkedIn, JobStreet, Glints,<br/>Kalibrr, Karir, TechInAsia, Indeed"]
    end

    subgraph Compose["Docker Compose services"]
        Gateway["gateway<br/>FastAPI :8000"]
        Pipeline["pipeline<br/>FastAPI :8005"]
        Scraper["scraper<br/>FastAPI :8001"]
        SBERT["sbert<br/>FastAPI :8002"]
        NCF["ncf<br/>FastAPI :8003"]
        DQN["dqn<br/>FastAPI :8004"]
        Postgres["postgres<br/>PostgreSQL 15 :5432"]
        Weights["weights volume<br/>/app/weights"]
        PgData["postgres_data volume"]
    end

    subgraph Offline["Offline or disconnected assets"]
        Hybrid["services/hybrid/main.py<br/>not in docker-compose"]
        Scripts["scripts/<br/>demo, retrain, verify"]
        Notebooks["notebooks/<br/>evaluation and readiness"]
        Reports["reports/<br/>metrics and artifacts"]
    end

    User --> Browser
    Browser -->|"Fetch API + Bearer JWT"| Gateway
    Gateway -->|"SQLAlchemy async"| Postgres
    Gateway -->|"HTTP /pipeline/run"| Pipeline
    Pipeline -->|"HTTP /scrape/run"| Scraper
    Pipeline -->|"HTTP /encode"| SBERT
    Pipeline -->|"HTTP /recommend/ncf"| NCF
    Pipeline -->|"HTTP /rank"| DQN
    Scraper -->|"httpx + parsing"| JobBoards
    Postgres --> PgData
    SBERT --> Weights
    NCF -->|"online_ncf.json"| Weights
    DQN -->|"online_dqn.json"| Weights
    Scripts --> Reports
    Notebooks --> Reports
```

### Service Communication Matrix

| Caller | Target | Protocol | Main request | Main response |
|---|---|---|---|---|
| Frontend | Gateway | HTTP/JSON | Auth, profile, jobs, applications, recommendations | User/job/recommendation JSON |
| Gateway | PostgreSQL | SQLAlchemy async | User, skill, job, application reads/writes | Rows and counts |
| Gateway | Pipeline | HTTP/JSON | `/pipeline/run`, `/pipeline/invalidate-user/{id}` | Ranked jobs, stage summaries |
| Pipeline | Scraper | HTTP/JSON | `/scrape/run` | Normalized job candidates |
| Pipeline | SBERT | HTTP/JSON | `/encode` | User/job embeddings |
| Pipeline | NCF | HTTP/JSON | `/recommend/ncf`, `/feedback`, `/jobs/upsert` | User-job scores and training status |
| Pipeline | DQN | HTTP/JSON | `/rank`, `/reward`, `/jobs/upsert` | Q-style ranking scores and training status |
| Scraper | Job boards | HTTP/HTML/JSON | Search/result pages and optional detail pages | Raw page content |

## User Journey: Recommendation Request

```mermaid
flowchart TD
    A["User opens /recommendations"] --> B{"Does browser have JWT?"}
    B -->|"No"| C["Redirect to /auth"]
    B -->|"Yes"| D["Frontend calls<br/>POST /api/recommendations"]
    D --> E["Gateway validates JWT"]
    E --> F["Gateway loads user and skills<br/>from PostgreSQL"]
    F --> G["Gateway counts interactions<br/>applications + user_interactions + user_job_interactions"]
    G --> H["Gateway sends PipelineRunRequest<br/>user_id, profile, interaction_count, limit"]
    H --> I["Pipeline Stage 1<br/>candidate jobs"]
    I --> J["Pipeline Stage 2<br/>semantic embeddings and SBERT score"]
    J --> K["Pipeline Stage 3<br/>NCF score"]
    K --> L["Pipeline Stage 4<br/>DQN-style rerank score"]
    L --> M["Pipeline Stage 5<br/>weighted aggregate and explanation"]
    M --> N["Gateway upserts jobs to DB"]
    N --> O["Gateway maps response to frontend schema"]
    O --> P["Frontend renders ranked cards"]
```

### Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant FE as Frontend
    participant GW as Gateway :8000
    participant DB as PostgreSQL
    participant PL as Pipeline :8005
    participant SC as Scraper :8001
    participant SB as SBERT :8002
    participant NC as NCF :8003
    participant DQ as DQN :8004

    User->>FE: Open /recommendations
    FE->>GW: POST /api/recommendations with Bearer JWT
    GW->>GW: Decode and validate JWT
    GW->>DB: SELECT user row and skills
    DB-->>GW: Profile data
    GW->>DB: Count applications and interaction rows
    DB-->>GW: interaction_count
    GW->>PL: POST /pipeline/run
    PL->>SC: POST /scrape/run or use DB/cache candidates
    SC-->>PL: jobs[]
    PL->>SB: POST /encode profile + job texts
    SB-->>PL: embeddings[]
    PL->>PL: Compute cosine similarity as sbert_score
    PL->>NC: POST /recommend/ncf candidates + embeddings
    NC-->>PL: ncf_score per job
    PL->>DQ: POST /rank candidates + session context
    DQ-->>PL: q_value per job
    PL->>PL: Aggregate final_score and explanation
    PL-->>GW: ranked[]
    GW->>DB: INSERT/UPDATE recommended jobs
    GW-->>FE: recommendations[]
    FE-->>User: Job cards with score bars
```

## Recommendation Pipeline: Six-Stage Interpretation

The active pipeline is implemented as five code stages. In recommendation-system language, it behaves like a candidate pipeline:

| Recsys concept | SCPA stage | Code | What happens |
|---|---|---|---|
| Source | Stage 1 | `stage_1_scrape.py` | Load candidate jobs from database, in-memory cache, scraper, or fallback jobs. |
| Hydrator | Stage 2 | `stage_2_encode.py` | Add embeddings and semantic scores. |
| Scorer | Stage 3 | `stage_3_ncf_score.py` | Add NCF score. |
| Scorer/reranker | Stage 4 | `stage_4_dqn_rank.py` | Add DQN-style rank score. |
| Selector | Stage 5 | `stage_5_aggregate.py` | Compute final score, sort, return top K. |
| Side effect | Gateway and pipeline feedback endpoints | `gateway/main.py`, `pipeline/main.py` | Upsert jobs, optional feedback forwarding. Frontend feedback is not wired yet. |

```mermaid
flowchart TD
    Start["PipelineRunRequest"] --> S1["Stage 1: Candidate source"]
    S1 --> S1a{"refresh_jobs true?"}
    S1a -->|"No + DB has jobs"| DBJobs["Use active DB jobs"]
    S1a -->|"No + cache has jobs"| CacheJobs["Use pipeline JOB_CACHE"]
    S1a -->|"Yes or no DB/cache"| ScrapeJobs["Call scraper /scrape/run"]
    ScrapeJobs --> Upsert["Upsert scraped jobs to PostgreSQL when DB is configured"]
    DBJobs --> Merge["Normalized candidate list"]
    CacheJobs --> Merge
    Upsert --> Merge

    Merge --> S2["Stage 2: SBERT encode"]
    S2 --> E1["Build profile_text and job_texts"]
    E1 --> E2["POST /encode"]
    E2 --> E3["Cosine similarity -> sbert_score"]

    E3 --> S3["Stage 3: NCF scoring"]
    S3 --> N1["POST /recommend/ncf"]
    N1 --> N2["score = sigmoid(dot(user,item)+biases)"]

    N2 --> S4["Stage 4: DQN-style rerank"]
    S4 --> D1["POST /rank"]
    D1 --> D2["q_value from linear weights + SBERT/NCF prior"]

    D2 --> S5["Stage 5: Aggregate"]
    S5 --> W["Choose weights by interaction_count"]
    W --> A["Add skill alignment and penalties"]
    A --> Sort["Sort by final_score"]
    Sort --> End["PipelineRunResponse ranked[]"]
```

### Active Aggregation Weights

| User segment | Condition | SBERT weight | NCF weight | DQN weight | Meaning |
|---|---:|---:|---:|---:|---|
| Cold | `interaction_count <= 0` | 0.75 | 0.20 | 0.05 | Trust profile text and skill alignment most. |
| Warm | `1 <= interaction_count <= 20` | 0.55 | 0.35 | 0.10 | Start trusting interaction patterns. |
| Active | `interaction_count > 20` | 0.45 | 0.40 | 0.15 | Give learned feedback more influence. |

The final score is:

```text
base_score = SBERT*w_sbert + NCF*w_ncf + DQN*w_dqn
final_score = clamp(base_score + 0.18*skill_alignment - penalty, 0, 1)
```

## Model-Service Truth Table

| Service name | What the name suggests | What the active code does | Correct way to describe it now |
|---|---|---|---|
| SBERT | Sentence-BERT semantic embeddings | Uses `SentenceTransformer` only when `SBERT_ENABLE_TRANSFORMER=1`; otherwise uses deterministic category/token embeddings. Docker Compose sets the transformer flag to `1`. Local tests often force fallback mode. | "SBERT service with optional real SentenceTransformer and deterministic fallback." |
| NCF | Neural Collaborative Filtering with neural user-item interaction function | Defines a PyTorch `NeuralCF` class, but the active HTTP path uses `OnlineNCF`, an online matrix-factorization model with dot product and biases. | "Online collaborative filtering / matrix factor scorer." |
| DQN | Deep Q-Network reinforcement-learning agent | Defines a PyTorch `QNetwork`, but active `/rank` uses `OnlineDQN`, a linear Q-style scorer over job features with TD update support. | "Online Q-style reranker; not a full deep Q-network in active serving." |
| Hybrid | Separate hybrid service | `services/hybrid/main.py` exists, but Docker Compose and the active pipeline use `stage_5_aggregate.py` instead. | "Stage 5 aggregation is active; standalone hybrid service is disconnected." |

## SBERT Flow

```mermaid
flowchart TD
    A["Profile text<br/>study program + skills"] --> B["Job texts<br/>title + company + location + description + experience"]
    A --> C{"SBERT_ENABLE_TRANSFORMER?"}
    B --> C
    C -->|"1 / true / yes"| D["Load SentenceTransformer<br/>MODEL_DIR if populated, else MODEL_NAME"]
    C -->|"not enabled or load fails"| E["Deterministic fallback embedding<br/>category aliases + hashed token features"]
    D --> F["model.encode(..., normalize_embeddings=True)"]
    E --> G["deterministic_embedding(text)"]
    F --> H["Normalized embeddings"]
    G --> H
    H --> I["Pipeline computes cosine similarity"]
    I --> J["sbert_score in [0,1]"]
```

### SBERT Implementation Details

| Detail | Current behavior |
|---|---|
| Default model name | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Embedding dimension | 384 |
| Optional real model flag | `SBERT_ENABLE_TRANSFORMER=1` |
| Docker Compose setting | Sets `SBERT_ENABLE_TRANSFORMER: "1"` |
| Local fallback | Category aliases for communication, language, event, software, data, business, design, plus stable hashed token features |
| Optional cache | Redis if `REDIS_URL` exists |
| Main endpoint used by pipeline | `POST /encode` |
| Separate semantic endpoint | `POST /match/semantic` |
| Key risk | Some docs mention `SBERT_FORCE_FALLBACK`, but the service code only checks `SBERT_ENABLE_TRANSFORMER`. |

## NCF Flow

```mermaid
flowchart TD
    A["Pipeline sends candidates<br/>id, title, description, tags, embedding"] --> B["OnlineNCF.recommend"]
    B --> C{"Known user?"}
    C -->|"No"| D["Create user factor<br/>from profile embedding or stable seed"]
    C -->|"Yes"| E["Reuse user factor"]
    D --> F["Item factor lookup"]
    E --> F
    F --> G{"Known item?"}
    G -->|"No"| H["Create item factor<br/>from job embedding or stable seed"]
    G -->|"Yes"| I["Reuse item factor"]
    H --> J["Predict"]
    I --> J
    J --> K["sigmoid(dot(user,item) + user_bias + item_bias + global_bias)"]
    K --> L["ncf_score"]

    M["Feedback event"] --> N["target from event value<br/>apply/click/save/view/skip"]
    N --> O["SGD updates user factor,<br/>item factor, biases, global bias"]
    O --> P["Save online_ncf.json"]
```

### NCF Implementation Details

| Detail | Current behavior |
|---|---|
| Active class | `OnlineNCF` |
| Factor dimension | `NCF_FACTOR_DIM`, default 64 |
| Learning rate | `NCF_LEARNING_RATE`, default 0.045 |
| Regularization | `NCF_REGULARIZATION`, default 0.0005 |
| Persistence | JSON file `online_ncf.json` in model directory |
| PyTorch `NeuralCF` class | Exists and can be used by training scripts, but is not the active HTTP serving path |
| Key risk | Calling the active path "NCF" can overclaim neural collaborative filtering because active inference uses a dot product, which the NCF paper specifically tried to move beyond. |

## DQN Flow

```mermaid
flowchart TD
    A["Pipeline sends candidates<br/>with embedding, SBERT score, NCF score"] --> B["OnlineDQN.rank"]
    B --> C["Build feature vector<br/>projected embedding + 6 dense features"]
    C --> D["Linear q_raw = dot(weights, features)"]
    D --> E["Prior = 0.55*SBERT + 0.35*NCF"]
    E --> F["q_value = 0.65*sigmoid(q_raw) + 0.35*prior"]
    F --> G["Sort by q_value"]
    G --> H["dqn_score after pipeline normalization"]

    I["Feedback event"] --> J["Compute reward<br/>click/apply/view positive, skip negative"]
    J --> K["TD target = reward + gamma*max(target Q)"]
    K --> L["weights += learning_rate * td_error * features"]
    L --> M["Every 10 steps: soft update target weights"]
    M --> N["Save online_dqn.json"]
```

### DQN Implementation Details

| Detail | Current behavior |
|---|---|
| Active class | `OnlineDQN` |
| Feature dimension | `DQN_EMBED_DIM + 6`, default 70 |
| Learning rate | `DQN_LEARNING_RATE`, default 0.03 |
| Discount | `DQN_GAMMA`, default 0.92 |
| Persistence | JSON file `online_dqn.json` |
| Replay storage | In-memory deque during service life; only summary is saved to JSON |
| PyTorch `QNetwork` class | Exists and is used by training scripts, but not by active `/rank` |
| Learning path endpoint in DQN service | Hardcoded role-to-skill sequences |
| Gateway learning path endpoint | Does not call DQN service; it uses a separate hardcoded list |
| Key risk | This is a Q-style online reranker, not a full deep Q-network serving path. |

## Data Flow

```mermaid
flowchart TB
    subgraph Profile["User profile data"]
        Register["Register<br/>name, email, password"]
        ProfileForm["Profile/onboarding<br/>study program, university, skills"]
        JWT["JWT access token"]
    end

    subgraph Jobs["Job data"]
        ExternalPages["External job pages"]
        Scraped["Scraped job rows<br/>title, company, location, description"]
        Normalized["Normalized candidate<br/>id, skills, tags, source_url, logo"]
        JobRows["PostgreSQL jobs rows<br/>UUID + match_data JSONB"]
    end

    subgraph ModelData["Model/runtime data"]
        ProfileText["profile_text"]
        Embeddings["embeddings"]
        Scores["sbert_score, ncf_score, dqn_score"]
        WeightsJson["online_ncf.json<br/>online_dqn.json"]
    end

    subgraph Output["User-visible output"]
        Recs["recommendations[]"]
        JobCards["job cards with match percent"]
        Apps["applications[]"]
        Skills["learning path skill suggestions"]
    end

    Register --> JWT
    Register --> DBUsers["users"]
    ProfileForm --> DBUsers
    ProfileForm --> DBSkills["user_skills"]
    ExternalPages --> Scraped
    Scraped --> Normalized
    Normalized --> JobRows
    DBUsers --> ProfileText
    DBSkills --> ProfileText
    JobRows --> Normalized
    ProfileText --> Embeddings
    Normalized --> Embeddings
    Embeddings --> Scores
    Scores --> Recs
    WeightsJson --> Scores
    Recs --> JobCards
    JobRows --> Apps
    DBSkills --> Skills
```

## Database ERD

```mermaid
erDiagram
    users ||--o{ user_skills : owns
    users ||--o{ applications : submits
    users ||--o{ user_interactions : generates
    users ||--o{ user_job_interactions : generates
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
        float_array state
        int action
        float reward
        float_array next_state
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

### Database Table Status

| Table | Current role |
|---|---|
| `users` | Active auth/profile table. |
| `user_skills` | Active profile-skill table. |
| `jobs` | Active job listing table. |
| `applications` | Active application table. |
| `user_interactions` | Counted by gateway, but frontend does not currently insert rows. |
| `user_job_interactions` | Counted by gateway, but no active frontend path writes it. |
| `dqn_session_logs` | Schema exists for DQN history, but active DQN runtime stores JSON file state. |
| `dqn_replay_archive` | Schema exists for DQN replay archive, but active DQN runtime does not write it. |
| `hybrid_weights` | Schema exists, but active aggregator uses hardcoded dynamic weights. |
| `hybrid_request_log` | Schema exists, but active runtime does not write request logs here. |

## Frontend Route Map

```mermaid
flowchart TB
    subgraph Routes["Next.js pages"]
        Landing["/"]
        Auth["/auth"]
        Onboarding["/onboarding"]
        Dashboard["/dashboard"]
        Profile["/profile"]
        Analytics["/analytics"]
        Recs["/recommendations"]
        JobDetail["/jobs/[id]"]
        Apply["/apply"]
    end

    subgraph Client["frontend/src/lib"]
        Api["api.ts<br/>ApiClient"]
        AuthCtx["auth-context.tsx<br/>AuthProvider"]
    end

    Auth -->|"login/register"| Api
    Auth --> AuthCtx
    Onboarding -->|"save profile steps"| Api
    Dashboard -->|"recommendations, applications,<br/>learning path, current user"| Api
    Profile -->|"get/update profile<br/>get applications"| Api
    Analytics -->|"job list"| Api
    Recs -->|"recommendations"| Api
    JobDetail -->|"job detail"| Api
    Apply -->|"jobs + submit applications"| Api
    AuthCtx -->|"JWT from localStorage"| Api
```

| Page | User sees | Gateway calls |
|---|---|---|
| `/` | Landing page | None |
| `/auth` | Login/register form | `/api/auth/login`, `/api/auth/register` |
| `/onboarding` | Profile wizard | `/api/profile/onboarding` |
| `/dashboard` | Overview, top recommendations, applications, suggested skills | `/api/recommendations`, `/api/applications`, `/api/learning-path`, `/api/auth/me` |
| `/profile` | Profile edit and application list | `/api/auth/me`, `/api/profile`, `/api/applications` |
| `/analytics` | Job listings with filters | `/api/jobs` |
| `/recommendations` | Ranked recommendations with score bars | `/api/recommendations` |
| `/jobs/[id]` | Single job detail | `/api/jobs/{id}` |
| `/apply` | Multi-select application flow | `/api/jobs`, `/api/applications` |

## API Surface

### Gateway Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | No | Gateway service info |
| GET | `/health` | No | Gateway health |
| GET | `/ready` | No | Gateway + pipeline readiness |
| GET | `/api/company-logo` | No | Logo proxy for allowlisted hosts |
| POST | `/api/auth/register` | No | Register and return JWT |
| POST | `/api/auth/login` | No | Login and return JWT |
| GET | `/api/auth/me` | Yes | Current user and skills |
| PUT | `/api/profile` | Yes | Update profile and skills |
| PUT | `/api/profile/onboarding` | Yes | Save onboarding step |
| GET | `/api/jobs` | No | Paginated Indonesian job list |
| GET | `/api/jobs/{job_id}` | No | Job detail |
| GET | `/api/applications` | Yes | User applications |
| POST | `/api/applications` | Yes | Create applications |
| POST | `/api/learning-path` | Yes | Rule-based suggested skills |
| POST | `/api/recommendations` | Yes | Authenticated recommendation run |
| POST | `/recommendations` | Yes | Alias for recommendation run |
| POST | `/pipeline/run` | No explicit auth dependency | Direct pipeline proxy |

### Pipeline Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Pipeline health and downstream URLs |
| POST | `/pipeline/run` | Full recommendation pipeline |
| GET | `/training/status` | Continual training/scrape cycle status |
| POST | `/training/run-once` | Trigger one scrape/embedding/upsert cycle |
| POST | `/feedback` | Forward feedback to NCF and DQN |
| POST | `/pipeline/invalidate-user/{user_id}` | Forward user factor invalidation to NCF |

### Model and Scraper Endpoints

| Service | Method | Path | Purpose |
|---|---|---|---|
| Scraper | GET | `/health` | Health and seed config |
| Scraper | POST | `/scrape/html` | Extract jobs from provided HTML |
| Scraper | POST | `/scrape/url` | Fetch and extract one URL |
| Scraper | POST | `/scrape/run` | Run scraping cycle |
| Scraper | GET | `/sample` | Return bundled sample jobs |
| SBERT | GET | `/health` | Health, model mode, embedding dimension |
| SBERT | POST | `/encode` | Encode text list |
| SBERT | POST | `/match/semantic` | Direct semantic score endpoint |
| SBERT | GET | `/metrics` | Operational metadata |
| NCF | GET | `/health` | Health and item/user counts |
| NCF | POST | `/jobs/upsert` | Add/update candidate item factors |
| NCF | POST | `/recommend/ncf` | Score candidates |
| NCF | POST | `/predict` | Alias to recommendation scoring |
| NCF | POST | `/feedback` | Learn from feedback event |
| NCF | POST | `/train` | Demo training batch |
| NCF | POST | `/users/{user_id}/invalidate` | Clear user factor/bias |
| NCF | GET | `/model/status`, `/metrics` | Model metadata |
| DQN | GET | `/health` | Health and training steps |
| DQN | POST | `/jobs/upsert` | Add/update job features |
| DQN | POST | `/rank` | Rank job candidates |
| DQN | POST | `/rerank` | Rank with session history |
| DQN | POST | `/reward`, `/feedback` | Learn from reward event |
| DQN | POST | `/learning-path` | Hardcoded role-skill path from DQN service |
| DQN | POST | `/train` | Soft update/save |
| DQN | GET | `/model/status`, `/metrics` | Model metadata |

## Background Training and Feedback

```mermaid
flowchart TD
    A["Pipeline starts"] --> B{"CONTINUAL_TRAINING_ENABLED?"}
    B -->|"false"| C["No background loop"]
    B -->|"true"| D["Start _continual_training_loop"]
    D --> E["Call scraper for fresh jobs"]
    E --> F["Call SBERT /encode"]
    F --> G["Update JOB_CACHE"]
    G --> H["POST jobs to NCF /jobs/upsert"]
    H --> I["POST jobs to DQN /jobs/upsert"]
    I --> J["Sleep interval"]
    J --> D

    K["Optional feedback call<br/>POST /pipeline/feedback"] --> L["Encode profile/job"]
    L --> M["Forward to NCF /feedback"]
    L --> N["Forward to DQN /reward"]
```

Important current limitation: the frontend API client has no `feedback` method. Users can view recommendation cards, open job detail, and apply, but those actions are not automatically sent to `/pipeline/feedback`.

## Docker Compose Startup Flow

```mermaid
flowchart LR
    Postgres["1. postgres<br/>healthcheck pg_isready"] --> Models["2. scraper, sbert,<br/>ncf, dqn"]
    Models --> Pipeline["3. pipeline<br/>waits for service health"]
    Pipeline --> Gateway["4. gateway<br/>waits for postgres + pipeline"]
    Gateway --> Frontend["5. frontend dev server<br/>manual npm run dev"]
```

| Compose service | Port | Main environment variables |
|---|---:|---|
| postgres | 5432 | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| gateway | 8000 | `PIPELINE_URL`, `DATABASE_URL`, `JWT_SECRET`, `JWT_REFRESH_SECRET` |
| scraper | 8001 | `SCRAPER_SEED_URLS`, `JOBS_TARGET`, source enable flags |
| sbert | 8002 | `SBERT_ENABLE_TRANSFORMER`, `MODEL_NAME`, `MODEL_DIR` |
| ncf | 8003 | `MODEL_DIR` |
| dqn | 8004 | `MODEL_DIR` |
| pipeline | 8005 | `SCRAPER_URL`, `SBERT_URL`, `NCF_URL`, `DQN_URL`, `DATABASE_URL` |

Docker Compose does not include:

- Redis
- Celery
- RabbitMQ
- Kafka
- Nginx
- `services/hybrid`

## Offline Evaluation and Reports

```mermaid
flowchart TB
    Sample["data/sample<br/>users, jobs, interactions, milestones"] --> Validate["validate_sample_dataset"]
    Validate --> Retrain["scripts/retrain_models.py"]
    Retrain --> SBERTArtifact["sbert_similarity_head.pt"]
    Retrain --> NCFArtifact["online_ncf.json"]
    Retrain --> DQNArtifact["dqn_model.pt"]
    Validate --> Full["scripts/run_full_pipeline.py"]
    Full --> Metrics["services/evaluation/recommendation_metrics.py"]
    Metrics --> CSV["reports/full_pipeline_metrics.csv"]
    Full --> JSON["reports/full_pipeline_summary.json<br/>reports/full_pipeline_recommendations.json"]
    Full --> NotebookInputs["notebooks/training_runs/readiness/"]
```

| Artifact | Purpose | Caveat |
|---|---|---|
| `reports/full_pipeline_metrics.csv` | Offline metric comparison | Depends on sample/demo labels. |
| `reports/full_pipeline_summary.json` | Full pipeline summary | Not the same as live frontend behavior. |
| `reports/full_pipeline_recommendations.json` | Demo recommendation output | Uses script-level flow. |
| `reports/retraining_artifacts/retraining_manifest.json` | Retraining summary | DQN checkpoint training is synthetic. |
| `reports/model_research_playwright.json` | Browser-backed source extraction for this review | Research artifact, not app runtime. |
| `notebooks/scpa_ml_readiness_evaluation.ipynb` | ML readiness notebook | Generated notebook should be regenerated from scripts when changed. |

## Failure and Fallback Paths

```mermaid
flowchart TD
    A["Recommendation request"] --> B["Gateway calls pipeline"]
    B --> C{"Pipeline reachable?"}
    C -->|"No: 502/503/504"| D["Gateway returns empty recommendations[]"]
    C -->|"Yes"| E["Pipeline Stage 1"]
    E --> F{"DB jobs available and no refresh?"}
    F -->|"Yes"| G["Use DB jobs"]
    F -->|"No"| H{"JOB_CACHE available?"}
    H -->|"Yes and no DB"| I["Use in-memory cache"]
    H -->|"No"| J["Call scraper"]
    J --> K{"Scraper succeeds?"}
    K -->|"No"| L["Use fallback jobs"]
    K -->|"Yes"| M["Use scraped jobs"]
    G --> N["Continue scoring"]
    I --> N
    L --> N
    M --> N
    N --> O{"SBERT transformer available?"}
    O -->|"Yes"| P["Use SentenceTransformer"]
    O -->|"No"| Q["Use deterministic fallback"]
    P --> R["Return scored ranking"]
    Q --> R
```

## Non-Technical Glossary

| Term | Meaning in SCPA |
|---|---|
| Frontend | The website the user clicks. |
| Gateway | The public backend API that checks login and talks to the database. |
| Pipeline | The internal service that decides how jobs should be ranked. |
| Scraper | The service that collects job listings from public sources. |
| SBERT score | A score for how similar the user's profile text is to the job text. |
| NCF score | A score based on learned user-job factors and feedback-like labels. |
| DQN score | A Q-style reranking signal based on job features and reward updates. |
| Hybrid/final score | The combined score shown as match percentage. |
| Cold start | A user with no prior interactions. The system trusts profile text more. |
| Warm/active user | A user with interaction history. The system trusts behavior scores more. |
| Fallback | A simpler path used when a model, service, or external source is unavailable. |

## Current Logical Risks Summary

The full code review is in `diagram/code_review.md`. The biggest flow-level risks are:

1. The gateway learning-path endpoint is rule-based and does not call the DQN service.
2. The active NCF serving path is matrix factorization, not neural collaborative filtering.
3. The active DQN serving path is a linear Q-style reranker, not a deep Q-network.
4. The frontend does not send click/view/save/skip feedback to the pipeline feedback endpoint.
5. Several docs/tests still describe older or planned behavior instead of active runtime behavior.

## Research Baseline Used for This Diagram

Browser-backed research was collected with Python Playwright using local Chrome and saved to `reports/model_research_playwright.json`.

Primary sources used:

- Sentence-BERT paper: https://arxiv.org/abs/1908.10084
- Hugging Face Sentence Transformers docs: https://huggingface.co/docs/hub/sentence-transformers
- Neural Collaborative Filtering paper: https://arxiv.org/abs/1708.05031
- DQN Nature paper: https://www.nature.com/articles/nature14236
- Original Atari DQN arXiv paper: https://arxiv.org/abs/1312.5602

## Maintenance Checklist

When this project changes, update this diagram if any of these changes:

- A new frontend page is added.
- A gateway endpoint changes response shape.
- Docker Compose adds/removes a service.
- `services/pipeline/stages/` changes scoring order or weights.
- `services/sbert/main.py` changes model loading behavior.
- `services/ncf/main.py` changes from `OnlineNCF` to real neural serving.
- `services/dqn/main.py` changes from `OnlineDQN` linear serving to real deep Q-network serving.
- Frontend starts sending feedback events.
- Hybrid service becomes part of Docker Compose or active routing.
