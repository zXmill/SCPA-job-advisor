# SCPA Model-Flow Code Review

Review scope: logical fallacies and model-flow mismatches across the current SCPA project, with special focus on SBERT, NCF, and DQN.

Research method: I used Python Playwright with local Chrome to inspect primary model references and saved the extraction to `reports/model_research_playwright.json`. I also checked the active local code paths in `services/`, `frontend/`, `scripts/`, `docs/`, and `tests/`.

## Research Baseline

| Topic | Primary source | Baseline used for review |
|---|---|---|
| SBERT | https://arxiv.org/abs/1908.10084 | SBERT is a siamese/triplet BERT-style sentence embedding approach whose embeddings can be compared with cosine similarity. |
| Sentence Transformers | https://huggingface.co/docs/hub/sentence-transformers | Sentence Transformers produce dense embeddings where similar texts are close, supporting semantic search and sentence similarity. |
| NCF | https://arxiv.org/abs/1708.05031 | NCF is specifically about replacing matrix-factorization inner product with a neural architecture for user-item interaction functions. |
| DQN | https://www.nature.com/articles/nature14236 and https://arxiv.org/abs/1312.5602 | DQN uses deep Q-learning to learn value functions; the canonical approach includes a deep network, replay, and target-network separation. |

## Findings

### P1 - Gateway learning path is not DQN-backed

`frontend/src/lib/api.ts:135-137` calls `POST /api/learning-path`. That endpoint is implemented in `services/gateway/main.py:964-995` as a static list of Python, SQL, FastAPI, Docker, Kubernetes, Machine Learning, and TensorFlow steps filtered by existing skills. It does not call `services/dqn/main.py:315-362`, and even the DQN service endpoint itself is a hardcoded role-to-skill sequence.

Logical fallacy: the UI and docs can imply "DQN learning path" while the active user-facing gateway path is rule-based. The safer claim is "rule-based suggested skills" unless the gateway is changed to call a real adaptive DQN-backed service.

Recommended fix: either rename the user-facing feature to rule-based learning path, or route gateway `/api/learning-path` through the DQN service and replace the hardcoded sequence with a state/action/reward policy that is evaluated separately.

### P1 - Active NCF serving is matrix factorization, not Neural Collaborative Filtering

`services/ncf/main.py:52-79` defines a PyTorch `NeuralCF` model, but the active HTTP path instantiates `OnlineNCF` at `services/ncf/main.py:329` and serves `model.recommend()` at `services/ncf/main.py:385-387`. The active prediction formula at `services/ncf/main.py:256-268` is `sigmoid(dot(user_vec, item_vec) + biases)`.

That is a useful online collaborative filtering model, but it is not the neural interaction function described by the NCF paper. The NCF paper's main point is replacing the inner product with a neural architecture, while this runtime path uses the inner product directly.

Recommended fix: for thesis/model correctness, either wire `NeuralCF` into serving/training/evaluation or rename the active model to "online matrix factorization" and reserve "NCF" for the offline PyTorch checkpoint path.

### P1 - Active DQN serving is a linear Q-style reranker, not a deep Q-network

`services/dqn/main.py:68-83` defines a PyTorch `QNetwork`, but active serving instantiates `OnlineDQN` at `services/dqn/main.py:283`. Ranking uses `OnlineDQN.rank()` at `services/dqn/main.py:243-252`, where `q_raw` is a dot product over linear weights and the final `q_value` is blended with SBERT/NCF prior. The update path at `services/dqn/main.py:254-281` applies a TD-like linear weight update and soft target update.

This is not wrong as an engineering shortcut, but calling it DQN overstates the implementation. The original DQN sources describe deep Q-learning with a neural network value function, replay, and target-network separation; the active path is a linear contextual scorer with a Q-learning-inspired update.

Recommended fix: rename active serving to "online Q-style reranker" or actually serve the `QNetwork` with replay sampling, exploration policy, target network updates, and evaluation against a logged recommendation environment.

### P1 - Frontend has no feedback loop into NCF/DQN learning

The pipeline has a feedback endpoint in `services/pipeline/main.py:318-359`, and NCF/DQN have feedback endpoints in `services/ncf/main.py:351-363` and `services/dqn/main.py:374-384`. But `frontend/src/lib/api.ts:126-161` only exposes recommendations, learning path, applications, profile, jobs, and onboarding. `frontend/src/app/recommendations/page.tsx:92-136` only opens source links or job detail; it does not record view/click/save/skip feedback.

Logical fallacy: "online learning from user behavior" is mostly theoretical in the active browser flow. Application submissions increase interaction count indirectly via `applications`, but they are not forwarded as reward/feedback events to the model services.

Recommended fix: add explicit feedback capture for recommendation impression, detail click, source click, save, skip/dismiss, and application submit. Send those through a gateway endpoint to pipeline `/feedback`, and persist a normalized interaction row.

### P2 - SBERT fallback, training, and docs are easy to misstate

`docker-compose.yml:75-83` sets `SBERT_ENABLE_TRANSFORMER: "1"`, so Docker intends real SentenceTransformer loading. But local docs and tests frequently set fallback flags, and `README.md:14-15` mentions `SBERT_FORCE_FALLBACK`, while `services/sbert/main.py:33-42` only checks `SBERT_ENABLE_TRANSFORMER`. The offline training script `services/sbert/training/train_sbert.py:14-31` trains a projection head over `deterministic_embedding`, not over a loaded SentenceTransformer, and `services/sbert/main.py:318-327` does not load that projection head in active serving.

Logical fallacy: "fine-tuned SBERT" or "trained SBERT" is not proven by the active code. The active service is either a configured pretrained SentenceTransformer or deterministic fallback; the local projection-head artifact is separate.

Recommended fix: remove `SBERT_FORCE_FALLBACK` from docs or implement it, document Docker vs local fallback explicitly, and either load the trained projection head in serving or call it an offline smoke artifact.

### P2 - `alpha_used` is not the hybrid alpha users/tests expect

Gateway maps `alpha_used` at `services/gateway/main.py:1058` as `(dqn_weight * 0.65 + ncf_weight * 0.35)`. That is neither the SBERT weight, nor the full aggregation weights, nor the classic hybrid alpha from the old hybrid service. Tests under `tests/test_edge_cases.py` still expect values like `1.0` or `0.5`, which belong to an older contract.

Logical fallacy: a field named `alpha_used` suggests a meaningful blend parameter, but current value is an arbitrary derived value from two weights. This can confuse frontend users and metric reviewers.

Recommended fix: replace `alpha_used` with `weights: {sbert, ncf, dqn}` in the gateway response, or define alpha precisely and update tests/docs to match.

### P2 - Pipeline failures become silent empty recommendation lists

`services/gateway/main.py:1026-1030` catches pipeline 502/503/504 failures and returns `{"recommendations": [], "fairness_tpr_gap": 0.0}`. This is user-friendly but hides whether no jobs matched or the ML stack failed.

Logical fallacy: "empty result" can be interpreted as a model decision, when it may be infrastructure failure.

Recommended fix: include a non-breaking status field such as `source_status: "pipeline_unavailable"` or `degraded: true`, and let the frontend render a retry/degraded-state message.

### P2 - Test suite contains contradictory model-flow expectations

`tests/test_e2e_pipeline.py:117` expects the active aggregator strategy `hybrid_scores_with_skill_alignment`, while `tests/test_online_recommender_learning.py:70` expects the older `learned_scores_no_static_domain_cap`. This is a strong signal that implementation changed but part of the test contract did not.

Logical fallacy: passing a subset of tests can create false confidence when tests encode two different architectures.

Recommended fix: update stale tests to the current contract or split legacy tests into a marked legacy suite that is not used for active validation.

### P2 - Database tables imply persistence that DQN runtime does not use

`db/models.py:573-617` defines `dqn_session_logs` and `dqn_replay_archive`, but active DQN runtime stores state in `online_dqn.json` and an in-memory replay deque in `services/dqn/main.py:168-215`. The pipeline feedback endpoint does not write to the DQN archive tables.

Logical fallacy: the schema suggests durable replay/session learning, but the active service does not persist replay transitions into PostgreSQL.

Recommended fix: either wire the feedback path to `dqn_session_logs`/`dqn_replay_archive`, or mark those tables as planned/offline in all docs.

### P3 - Hybrid service is present but disconnected from active runtime

`services/hybrid/main.py` exists, and older docs still describe a hybrid service. However, `docker-compose.yml` includes postgres, gateway, scraper, sbert, ncf, dqn, and pipeline only. Active recommendations use `services/pipeline/stages/stage_5_aggregate.py`.

Logical fallacy: "we have a hybrid service" can sound like the deployed path uses it. It does not.

Recommended fix: keep documentation explicit: active hybrid logic is Stage 5 aggregation; standalone hybrid service is disconnected unless added to Compose and called by pipeline/gateway.

## Highest-Value Repair Plan

1. Fix naming honesty first: change docs/UI copy from "NCF/DQN" to "NCF-style/online CF" and "DQN-style Q reranker" unless you wire the real neural paths.
2. Add frontend feedback calls and persistence so NCF/DQN can actually learn from browser behavior.
3. Decide whether gateway learning path should be rule-based or DQN-backed, then remove the other story.
4. Replace `alpha_used` with explicit weights.
5. Update stale tests and docs in one pass so the project has one source of truth.

## Review Verdict

The project has a coherent recommendation pipeline, but the model naming is currently stronger than the active implementation. The safest thesis/demo framing is:

> SCPA combines semantic text matching, online collaborative filtering, and a Q-learning-inspired reranker, with offline PyTorch artifacts for NCF/DQN experiments.

That statement matches the code more closely than claiming fully active SBERT fine-tuning, neural collaborative filtering, and deep Q-network serving.
