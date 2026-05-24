# SCPA Thesis-Grade Model-Flow Code Review

Review scope: logical fallacies, research-fit gaps, and implementation mismatches across the current SCPA project, with special focus on making the app defensible as a bachelor thesis about skill-career mismatch in Indonesia using real SBERT, real NCF, and real DQN.

Review date: 2026-05-25.

Local code evidence inspected: `services/sbert/`, `services/ncf/`, `services/dqn/`, `services/pipeline/`, `services/gateway/`, `frontend/src/`, `db/models.py`, `tests/`, `docs/`, `README.md`, and generated reports under `reports/`.

Research method: I used Python Playwright with local Chrome, web search, OpenAlex, Semantic Scholar, DOI landing pages, arXiv, ACM/IEEE/Elsevier/Springer/OECD/ILO pages, and local code inspection. The expanded browser-source artifact is saved at `reports/model_research_playwright.json`.

Quality gate for sources: I prioritized peer-reviewed journals and conferences indexed in Scopus or equivalent scholarly venues (ACM, IEEE, ACL, Springer, Elsevier, Nature, SIGIR, RecSys, WWW, KDD, UAI), plus institutional policy research from ILO/OECD/BPS/World Bank-grade organizations for Indonesian labor-market context. arXiv sources are marked as preprints when used.

## Executive Verdict

SCPA is directionally aligned with the thesis problem: Indonesia has an education, skills, and labor-market alignment problem, and a career recommender that combines semantic job-skill matching, behavior-based recommendation, and sequential skill-path optimization is a defensible solution direction.

The implementation is not yet defensible as "real SBERT + real NCF + real DQN" in the active user-facing path:

- SBERT can load a real SentenceTransformer at runtime, but the local "training" path trains a projection head over deterministic embeddings, not a fine-tuned SentenceTransformer.
- NCF defines a PyTorch `NeuralCF` model, but active serving uses `OnlineNCF`, a dot-product matrix-factor model.
- DQN defines a PyTorch `QNetwork`, but active serving uses a linear Q-style reranker, and the user-facing learning path in the gateway is rule-based.
- The browser UI does not send impression, click, skip, save, apply, or dwell feedback into the learning endpoints, so the online-learning story is mostly disconnected from real user behavior.

For thesis honesty today, the safest current claim is:

> SCPA currently implements a hybrid career recommendation prototype combining semantic matching, online matrix-factor collaborative filtering, and a Q-learning-inspired reranking signal, with offline PyTorch artifacts for NCF/DQN experiments.

For your stated graduation requirement, that wording is not enough. The app should be upgraded so the active runtime actually serves a fine-tuned SentenceTransformer/SBERT model, a neural collaborative filtering model, and a DQN agent with neural Q-values, replay, target-network updates, exploration policy, logged rewards, and reproducible evaluation.

## Source Register

| ID | Topic | Source | Quality | Used for |
|---|---|---|---|---|
| S01 | Indonesia skill mismatch | [ILO, The Skills Development and Employment Situation in Indonesia's Electronic Sector, 2024](https://www.ilo.org/publications/skills-development-and-employment-situation-indonesias-electronic-sector) | ILO policy research | Indonesia-specific reskilling/upskilling rationale. |
| S02 | Indonesia skills/jobs | [OECD, Investing in competences and skills and reforming the labour market to create better jobs in Indonesia, 2021](https://www.oecd.org/en/publications/investing-in-competences-and-skills-and-reforming-the-labour-market-to-create-better-jobs-in-indonesia_fd54e6be-en.html) | OECD working paper, DOI `10.1787/fd54e6be-en` | Indonesia education quality, upskilling, reskilling, and job-quality framing. |
| S03 | Indonesia economy/skills | [OECD Economic Surveys: Indonesia 2024](https://www.oecd-ilibrary.org/en/publications/oecd-economic-surveys-indonesia-2024_de87555a-en.html) | OECD report | Current Indonesia policy context and digital competence framing. |
| S04 | Indonesia mismatch | [Peta Ketidaksesuaian Kualifikasi Sektoral di Indonesia](https://journals.kemnaker.go.id/index.php/naker/article/view/69) | Indonesian labor journal, DOI `10.47198/naker.v15i2.69` | Sectoral qualification mismatch evidence. |
| S05 | Indonesia job-skill analytics | [Big Data Analysis of Skill Requirements in the Indonesian Manufacturing Sector](https://jurnalindustri.petra.ac.id/index.php/ind/article/view/32790) | Peer-reviewed Indonesian industrial engineering journal | Semantic analysis of Indonesian job-skill demand. |
| S06 | Workforce readiness | [Unlocking workforce readiness through digital employability skills in vocational education graduates](https://doi.org/10.1016/j.ssaho.2025.101625) | Elsevier journal | Workforce-readiness construct. |
| S07 | Indonesia green jobs | [ILO, Assessment of jobs and skill needs in the electric vehicle value chain](https://www.ilo.org/publications/assessment-jobs-and-skill-needs-electric-vehicle-value-chain) | ILO policy research | Dynamic sectoral skill needs in Indonesia. |
| S08 | VET and skills | [Skills for development and vocational education and training: Current and emergent trends](https://doi.org/10.1016/j.ijedudev.2023.102853) | Elsevier journal | Skill-development and VET research context. |
| S09 | Job recommender survey | [e-Recruitment recommender systems: a systematic review](https://doi.org/10.1007/s10115-020-01522-8) | Springer Knowledge and Information Systems | Job recommender requirements and literature baseline. |
| S10 | Job recommender survey | [A Challenge-based Survey of E-recruitment Recommendation Systems](https://doi.org/10.1145/3659942) | ACM Computing Surveys | E-recruitment challenges: reciprocal matching, cold start, fairness, explainability, scalability. |
| S11 | Job recommender survey | [A challenge-based survey of e-recruitment recommendation systems, arXiv](https://arxiv.org/abs/2209.05112) | Preprint of ACM CSUR article | Open version for method-challenge mapping. |
| S12 | Career skill RL | [Market-aware Long-term Job Skill Recommendation with Explainable Deep Reinforcement Learning](https://doi.org/10.1145/3704998) | ACM Transactions on Information Systems | Strongest direct fit for DQN-like career skill recommendation. |
| S13 | Career skill RL | [Cost-effective and interpretable job skill recommendation with deep reinforcement learning](https://doi.org/10.1145/3442381.3449985) | ACM DOI | Skill recommendation with DRL and interpretability. |
| S14 | Course/job-market alignment | [Course Recommender Systems Need to Consider the Job Market](https://arxiv.org/abs/2404.10876) | arXiv preprint | Linking learning recommendations to job-market demand. |
| S15 | NCF | [Neural Collaborative Filtering](https://doi.org/10.1145/3038912.3052569) | ACM WWW | Defines NCF as neural user-item interaction, not plain dot product. |
| S16 | Implicit feedback CF | [Collaborative Filtering for Implicit Feedback Datasets](https://doi.org/10.1109/ICDM.2008.22) | IEEE ICDM | Implicit feedback modeling, confidence, exposure ambiguity. |
| S17 | Implicit ranking | [BPR: Bayesian Personalized Ranking from Implicit Feedback](https://arxiv.org/abs/1205.2618) | UAI/arXiv | Ranking loss and negative sampling baseline. |
| S18 | Graph CF | [LightGCN](https://arxiv.org/abs/2002.02126) | SIGIR/arXiv | Strong modern collaborative-filtering baseline. |
| S19 | Deep recommender production | [Deep Neural Networks for YouTube Recommendations](https://doi.org/10.1145/2959100.2959190) | ACM RecSys | Two-stage candidate/ranking architecture and production-scale recsys pattern. |
| S20 | Neural CF baseline | [Variational Autoencoders for Collaborative Filtering](https://doi.org/10.1145/3178876.3186150) | ACM WWW | Neural implicit-feedback baseline. |
| S21 | SBERT | [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://arxiv.org/abs/1908.10084) | EMNLP/arXiv | Sentence embeddings, siamese/triplet training, cosine similarity. |
| S22 | BERT | [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding](https://aclanthology.org/N19-1423/) | ACL Anthology, NAACL | Transformer foundation behind SBERT. |
| S23 | Skill extraction | [A Survey on Skill Identification From Online Job Ads](https://doi.org/10.1109/ACCESS.2021.3106120) | IEEE Access, public metadata marks Scopus | Job-ad skill extraction requirements. |
| S24 | Job-candidate semantic matching | [Zero-Shot Recommendation AI Models for Efficient Job-Candidate Matching](https://doi.org/10.3390/app14062601) | Applied Sciences | Semantic job-candidate matching and limitations of zero-shot matching. |
| S25 | SBERT job matching | [conSultantBERT: Fine-tuned Siamese Sentence-BERT for Matching Jobs and Job Seekers](https://arxiv.org/abs/2109.06501) | arXiv industry preprint | Direct evidence that job matching needs domain fine-tuning pairs. |
| S26 | Job skill extraction | [Job description parsing with explainable transformer based ensemble models](https://doi.org/10.1016/j.nlp.2024.100102) | Elsevier NLP journal | Technical and non-technical skill extraction from job descriptions. |
| S27 | DQN foundation | [Human-level control through deep reinforcement learning](https://www.nature.com/articles/nature14236) | Nature | Canonical DQN: deep network, replay, target network, value learning. |
| S28 | DRL recommender survey | [Deep reinforcement learning in recommender systems: A survey and new perspectives](https://doi.org/10.1016/j.knosys.2023.110335) | Elsevier Knowledge-Based Systems | DRL recommender taxonomy and open issues. |
| S29 | DQN recommender | [DRN: A Deep Reinforcement Learning Framework for News Recommendation](https://doi.org/10.1145/3178876.3185994) | ACM WWW | DQN-style recommendation with user feedback and dynamic environment. |
| S30 | List-wise RL recsys | [Deep Reinforcement Learning for List-wise Recommendations](https://arxiv.org/abs/1801.00209) | arXiv preprint | Recommender interaction as MDP and list-wise rewards. |
| S31 | DQN slate recsys | [Scalable Deep Q-Learning for Session-Based Slate Recommendation](https://doi.org/10.1145/3604915.3608843) | ACM RecSys | Deep Q-learning for slate/session recommendation. |
| S32 | RL slate recsys | [Generative Slate Recommendation with Reinforcement Learning](https://arxiv.org/abs/2301.08632) | WSDM/arXiv | Slate recommendation and long-term engagement concerns. |
| S33 | Negative feedback RL | [Recommendations with Negative Feedback via Pairwise Deep Reinforcement Learning](https://doi.org/10.1145/3219819.3219886) | ACM KDD | Negative feedback and pairwise DRL for recommendation. |
| S34 | Off-policy recsys | [Top-K Off-Policy Correction for a REINFORCE Recommender System](https://doi.org/10.1145/3289600.3290999) | ACM WSDM | Logged-feedback bias and off-policy correction. |
| S35 | Recsys reproducibility | [Are We Really Making Much Progress?](https://arxiv.org/abs/1907.06902) | ACM RecSys/arXiv | Baseline strength and reproducibility warning for neural recommenders. |
| S36 | Recsys bias | [Bias and Debias in Recommender System](https://arxiv.org/abs/2010.03240) | arXiv survey | Bias categories and debiasing threats. |

## Research Synthesis for This Thesis

### Why the Indonesia skill-mismatch problem is valid

The thesis problem is legitimate. Indonesia-facing labor research and policy sources frame skills and competences as central to future job quality and productivity. OECD's Indonesia working paper explicitly treats skills, education quality, upskilling, and reskilling as increasingly important for Indonesia's living standards and labor-market outcomes (S02). ILO's Indonesia electronics-sector assessment frames technological change as requiring sector-specific upskilling and reskilling responses (S01). Indonesian labor research also treats mismatch as a serious labor-market problem and maps sectoral qualification mismatch with BPS Sakernas data (S04).

What this means for SCPA: the app should not only rank jobs by text similarity. It should expose the missing skills, explain the skill gap, prioritize learning actions, and connect recommendations to observable Indonesian job-market demand.

### What career/job recommender research expects

Job recommendation is not the same as movie or product recommendation. E-recruitment recommender surveys emphasize reciprocal matching, heterogeneous entities, cold start, incomplete profiles, multiple interaction types, explainability, fairness, and scalability (S09, S10, S11). Skill recommendation work also argues that job-market demand should shape learning recommendations, not only learner history (S12, S13, S14).

What this means for SCPA: the architecture should explicitly model:

- job seeker profile and skills,
- job requirements and extracted skills,
- missing-skill gap,
- implicit and explicit feedback,
- labor-market demand,
- explanation and fairness constraints,
- evaluation beyond a single top-K score.

### What "real SBERT" should mean here

SBERT is not just any embedding function. The SBERT paper modifies BERT with siamese/triplet structures so sentence embeddings can be compared efficiently with cosine similarity (S21), building on BERT's contextual transformer foundation (S22). Job matching research using Siamese SBERT shows that domain-specific resume-vacancy pairs are valuable for matching jobs and job seekers (S25). Skill identification research shows that job ads are unstructured and need robust skill extraction and normalization before they become reliable labor-market signals (S23, S26).

For SCPA, a thesis-grade SBERT implementation should:

- load a real `SentenceTransformer` in active serving,
- fine-tune or at least evaluate on Indonesian profile-job pairs,
- compare profile, job, and skill-gap text with normalized embeddings,
- keep deterministic fallback only for tests/demo, not thesis claims,
- report retrieval metrics such as Recall@K, MRR@K, NDCG@K, plus qualitative skill-gap examples.

### What "real NCF" should mean here

The NCF paper's central contribution is replacing matrix-factorization inner product with a neural architecture for the user-item interaction function (S15). Implicit feedback recommenders need careful interpretation because clicks, views, applies, skips, and missing interactions are not the same as explicit ratings (S16). BPR and related work show the importance of pairwise ranking objectives and negative sampling for implicit ranking (S17). Modern baselines such as LightGCN are strong enough that a thesis should compare against at least one non-neural and one neural/graph baseline if claiming neural superiority (S18, S35).

For SCPA, a thesis-grade NCF implementation should:

- serve a neural interaction model, for example NeuMF/GMF+MLP,
- train on normalized user-job interactions with negative sampling or confidence weighting,
- distinguish impression, click, source-click, save, apply, skip, and dwell time,
- persist user/item ID maps and model checkpoints,
- evaluate against matrix factorization, SBERT-only, and hybrid baselines.

### What "real DQN" should mean here

Canonical DQN uses a deep neural network to approximate action values, experience replay, and a separated target network (S27). DRL recommender literature models recommendation as sequential interaction where actions affect future feedback and data collection (S28, S29, S30). Slate and session-based recommendation research shows that real recommendation actions often return lists, not single actions, which complicates state, reward, and off-policy evaluation (S31, S32). Logged feedback is biased by the policy that collected it, so off-policy correction or careful offline simulation matters (S34). Career-skill recommendation papers are especially relevant because they use long-term skill utility and explainability rather than one-step item clicks (S12, S13).

For SCPA, a thesis-grade DQN implementation should:

- define an MDP clearly: state, action, reward, transition, terminal condition,
- use a real neural `QNetwork` in active serving,
- store replay transitions durably,
- sample replay mini-batches,
- maintain a target network,
- use exploration during data collection or a defensible offline-policy strategy,
- evaluate skill-path quality with offline simulator labels, delayed outcomes, or expert-validated paths,
- not present static role templates as DQN output.

## Findings

### P0 - The active runtime does not yet satisfy the thesis requirement of real SBERT, real NCF, and real DQN

The repo has strong pieces, but they do not line up with the claim. `services/sbert/main.py:306-327` can use a real SentenceTransformer when `SBERT_ENABLE_TRANSFORMER` is enabled. `services/ncf/main.py:52-79` defines a PyTorch `NeuralCF`. `services/dqn/main.py:68-83` defines a PyTorch `QNetwork`.

The active user-facing paths are different:

- NCF active serving instantiates `OnlineNCF` at `services/ncf/main.py:329`.
- DQN active serving instantiates `OnlineDQN` at `services/dqn/main.py:283`.
- Gateway learning path is hardcoded at `services/gateway/main.py:964-995`.
- Frontend copy says "calls real DQN service" at `frontend/src/lib/api.ts:134`, but that API calls the gateway rule-based endpoint.

Research mismatch: NCF requires a neural interaction function (S15), DQN requires a neural Q-value learner with replay and target-network separation (S27), and career-skill RL should optimize long-term skill utility (S12, S13). The current active path is a hybrid prototype, not the real three-model thesis system.

Required fix: treat this as the top thesis blocker. Either downgrade all claims, or wire the real neural paths into serving and evaluation. Because you explicitly need real DQN, SBERT, and NCF for graduation, do the second option.

### P1 - Gateway learning path is rule-based, not DQN-backed

`frontend/src/lib/api.ts:134-137` says the learning path calls a real DQN service, but it calls `POST /api/learning-path`. That gateway endpoint is implemented at `services/gateway/main.py:964-995` as a static list of Python, SQL, FastAPI, Docker, Kubernetes, Machine Learning, and TensorFlow steps filtered by user skills. It does not call `services/dqn/main.py`.

Even the DQN service's own `/learning-path` endpoint at `services/dqn/main.py:315-362` is a hardcoded role-to-skill sequence, not a neural policy. It checks strings such as `"data scientist"`, `"backend"`, `"business"`, and `"mc"`, then returns a preselected sequence.

Logical fallacy: because the service is named DQN and exposes `/learning-path`, the app can appear to have a DQN learning path. In the active code, the user-facing path is rule-based.

Why research says this is wrong: skill recommendation with DRL should optimize long-term skill utility and career goals with a learned policy, not only filter a static checklist (S12, S13). DQN requires learned action-values from state-action-reward transitions (S27).

Required fix:

1. Add a gateway client call from `/api/learning-path` to `DQN_URL + "/learning-path"` or a new DQN endpoint.
2. Replace role templates with DQN actions from a real action space such as `skill_id`, `course_id`, or `career_step_id`.
3. Define state as current skills, target role, profile embedding, completed learning steps, prior interactions, and labor-market demand features.
4. Define reward as a weighted outcome: skill-gap reduction, job-match improvement, user completion, application/click/apply signal, and expert-validated role relevance.
5. Persist transitions in `dqn_session_logs` and `dqn_replay_archive`.

### P1 - Active DQN reranking is linear Q-learning style, not a deep Q-network

`services/dqn/main.py:68-83` defines a real feed-forward `QNetwork`, but active serving uses `OnlineDQN`. `OnlineDQN` stores `self.weights` and `self.target_weights` as NumPy vectors at `services/dqn/main.py:176-180`. `q_value()` is a dot product at `services/dqn/main.py:240-241`. `rank()` blends a sigmoid of that dot product with SBERT/NCF priors at `services/dqn/main.py:243-252`. `learn()` applies a TD-like linear update at `services/dqn/main.py:254-281`.

This is useful engineering, but it is not a DQN in the Nature sense. DQN is a deep neural approximator trained with replay and target-network separation (S27). DRL recommender papers also care about sequential user feedback, slate/list actions, off-policy bias, and exploration (S28, S30, S31, S34).

Logical fallacy: "has a `QNetwork` class" is not the same as "the app serves a DQN." The class exists, but the active HTTP path does not use it for inference or training.

Required fix:

1. Make `OnlineDQN` own `policy_net: QNetwork` and `target_net: QNetwork`, not NumPy weights.
2. Store transitions as `(state_vector, action_id, reward, next_state_vector, done, behavior_policy_prob, timestamp)`.
3. On feedback, append to replay and train mini-batches with TD loss.
4. Update target network every fixed step or with soft update over neural parameters.
5. Add epsilon-greedy or constrained exploration. For thesis/demo safety, exploration can be offline/simulated, but it must be described.
6. Evaluate DQN separately from job ranking: skill-path success, cumulative reward, action accuracy, and improvement in later job-match metrics.

### P1 - Active NCF serving is matrix factorization, not Neural Collaborative Filtering

`services/ncf/main.py:52-79` defines a PyTorch GMF+MLP-style `NeuralCF`, but active serving instantiates `OnlineNCF` at `services/ncf/main.py:329`. The active score is `sigmoid(dot(user_vec, item_vec) + user_bias + item_bias + global_bias)` at `services/ncf/main.py:256-268`.

That formula is a matrix-factor collaborative filtering scorer. It is not the NCF paper's neural interaction function. The NCF paper explicitly frames its contribution as replacing inner product with a neural architecture that learns user-item interaction functions (S15).

Logical fallacy: "NCF-style online scorer" is acceptable in docs if clearly qualified. It is not acceptable if the thesis claims real NCF.

Required fix:

1. Use `NeuralCF` or a NeuMF model in active `/recommend/ncf`.
2. Create stable `user_id -> index` and `job_id -> index` mappings.
3. Train with implicit feedback using BCE/BPR and negative sampling.
4. Include item/profile text embeddings as side features only if the model architecture explicitly supports them.
5. Keep the current dot-product model as a baseline named `OnlineMF`, not as the main NCF result.

### P1 - Browser behavior does not feed NCF/DQN learning

The pipeline has `/feedback` at `services/pipeline/main.py:318-359`, and it forwards feedback to NCF and DQN. NCF has `/feedback` at `services/ncf/main.py:351-363`. DQN has `/reward` and `/feedback` at `services/dqn/main.py:374-384`.

The frontend API does not expose a feedback method in `frontend/src/lib/api.ts:126-161`. The recommendation card displays source links and job detail links at `frontend/src/app/recommendations/page.tsx:92-136`, but it does not log impressions, source clicks, detail clicks, saves, skips, applications, or dwell time to the model feedback path.

Logical fallacy: the architecture says "online learning from user behavior," but the active browser flow does not emit the behavior events needed to learn.

Why research says this matters: implicit feedback recommenders must know which items were exposed and which actions occurred (S16, S17). DRL recommenders are especially sensitive to logged-policy bias and reward design (S28, S34). Without impression logs, a skip or non-click cannot be distinguished from an item the user never saw.

Required fix:

1. Add `api.trackRecommendationEvent(event)` in `frontend/src/lib/api.ts`.
2. Fire `impression` when a card enters the viewport.
3. Fire `detail_click`, `source_click`, `save`, `skip`, `apply`, and `dwell_10s`.
4. Add a gateway `/api/recommendations/feedback` endpoint that authenticates the user and forwards to pipeline `/feedback`.
5. Persist events in `user_job_interactions` and DQN replay tables before forwarding to model services.

### P1 - SBERT is real at runtime only when enabled, but the local training path is not fine-tuning SBERT

`services/sbert/main.py:33-42` checks `SBERT_ENABLE_TRANSFORMER`, and `services/sbert/main.py:306-327` loads `SentenceTransformer` only when that variable is true. That part can be real SBERT.

The training script `services/sbert/training/train_sbert.py:14-31` imports `deterministic_embedding` and trains `SimilarityHead` over frozen deterministic vectors. It does not fine-tune `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` or any transformer model. Serving also does not load the `SimilarityHead`.

Docs mention `SBERT_FORCE_FALLBACK` in several places, but active code only checks `SBERT_ENABLE_TRANSFORMER`.

Logical fallacy: "trained SBERT" or "fine-tuned SBERT" is not proven by this training script. Current active SBERT is either a pretrained SentenceTransformer or deterministic fallback.

Why research says this matters: SBERT's value comes from a transformer encoder trained/fine-tuned for semantically meaningful sentence embeddings (S21). Job matching benefits from domain-specific resume-vacancy fine-tuning pairs (S25). Skill extraction from job ads is a separate hard problem (S23, S26).

Required fix:

1. Use `sentence_transformers.SentenceTransformer` training APIs.
2. Build pairs/triplets from Indonesian profile-job matches, skill-overlap labels, application outcomes, and negative samples.
3. Save a real SentenceTransformer model directory.
4. Make `MODEL_DIR` point to that directory in Docker.
5. Add startup health fields: `model_loaded`, `fallback_mode`, `model_name_or_path`, and `fine_tuned=true/false`.
6. Remove or implement `SBERT_FORCE_FALLBACK`.

### P1 - The pipeline overclaims DQN and NCF interpretability in explanations

Gateway explanations are generated at `services/gateway/main.py:1046-1050` as if SBERT, NCF, and DQN scores are comparable percentages:

- "SBERT semantic similarity"
- "NCF interaction pattern"
- "DQN career-action signal"

Stage 5 aggregation explains DQN similarly at `services/pipeline/stages/stage_5_aggregate.py:150-154`.

Logical fallacy: these are not calibrated probabilities. SBERT cosine similarity, NCF sigmoid score, and DQN blended Q-score have different meanings. Presenting all three as percentages makes the output look more scientifically precise than it is.

Why research says this matters: e-recruitment recommender systems require explainability, but explanations must reflect the actual method and data (S10). Recommender evaluation work warns against overclaiming neural progress without strong baselines and reproducibility (S35).

Required fix:

1. Replace "percent" wording with "signal strength" unless scores are calibrated.
2. Return `weights: {sbert, ncf, dqn}` and raw score fields separately.
3. Add explanation provenance: `semantic_match`, `behavior_match`, `skill_path_signal`, `skill_gap`.
4. Add calibration plots or reliability checks if you want to call scores probabilities.

### P2 - `alpha_used` is mathematically misleading

Gateway maps `alpha_used` at `services/gateway/main.py:1058` as:

```text
dqn_weight * 0.65 + ncf_weight * 0.35
```

This is not the SBERT weight, not the DQN weight, and not the full hybrid blend. Stage 5 returns actual weights at `services/pipeline/stages/stage_5_aggregate.py:166-178`, but gateway collapses them into a confusing scalar.

Tests still encode older expectations such as `alpha_used == 1.0` or `0.5`, while active Stage 5 returns `strategy: "hybrid_scores_with_skill_alignment"` in `tests/test_e2e_pipeline.py:116-117` and another test expects stale `strategy: "learned_scores_no_static_domain_cap"` in `tests/test_online_recommender_learning.py:68-70`.

Required fix: remove `alpha_used` or replace it with:

```json
{
  "weights": {"sbert": 0.55, "ncf": 0.35, "dqn": 0.10},
  "segment": "warm",
  "strategy": "hybrid_scores_with_skill_alignment"
}
```

### P2 - Skill mismatch is not yet measured as a first-class outcome

The thesis problem is skill-career mismatch, but the active recommendation output mostly ranks jobs. There is some skill-alignment logic in Stage 5, but the app needs a first-class "skill gap" evaluation target:

- extracted required skills per job,
- user current skills,
- missing skills,
- skill criticality,
- learning-path actions,
- before/after predicted job-fit lift.

Why research says this matters: skill mismatch research is about mismatch between education/skills and occupational demand (S01, S02, S04). Skill identification from job ads is a separate extraction task (S23, S26). Career skill recommendation research explicitly optimizes future skill utility (S12, S13).

Required fix:

1. Add a `job_required_skills` table or JSON field populated by an extractor.
2. Add a normalized skill taxonomy, even a small thesis-local one.
3. Add `missing_skills` to every recommendation.
4. Make DQN actions recommend missing skills with highest expected career utility.
5. Evaluate skill-gap reduction, not only job ranking.

### P2 - The app lacks a defensible reciprocal e-recruitment model

Job recommendation in recruitment is reciprocal: a job should fit the candidate, but the candidate should also fit the employer's requirements. SCPA currently focuses on job seeker preference/fit. It does not model employer-side constraints deeply enough, such as minimum education, experience, hard skill requirements, language, location, or salary constraints.

Why research says this matters: e-recruitment recommender surveys identify reciprocal recommendation and suitability as domain-specific challenges (S09, S10, S11).

Required fix:

1. Split scores into `candidate_preference_score` and `employer_requirement_fit_score`.
2. Hard-filter must-have requirements before scoring.
3. Explain rejected/low-score jobs as skill/requirement gaps.
4. Evaluate both relevance and suitability.

### P2 - Pipeline failures become silent empty recommendations

`services/gateway/main.py:1026-1030` catches pipeline 502/503/504 failures and returns:

```json
{"recommendations": [], "fairness_tpr_gap": 0.0}
```

Logical fallacy: users and evaluators can interpret "no recommendations" as a model result, when it may be an infrastructure failure.

Required fix: include `degraded: true`, `source_status: "pipeline_unavailable"`, and a frontend message that the ML pipeline is unavailable.

### P2 - DQN replay/session tables exist but are not used by the active runtime

`db/models.py:573-617` defines `dqn_session_logs` and `dqn_replay_archive`. Active `OnlineDQN` stores replay in an in-memory deque at `services/dqn/main.py:180` and serializes only weights/jobs/state JSON at `services/dqn/main.py:202-215`.

Logical fallacy: the schema suggests durable replay learning, but the active DQN service does not use the database archive.

Required fix:

1. On every feedback event, write replay to PostgreSQL.
2. On DQN startup, load replay or the last checkpoint metadata.
3. Save policy and target network checkpoints with replay metadata.
4. Add a test that feedback creates a `dqn_replay_archive` row.

### P2 - Evaluation is too sample/demo-heavy for thesis claims

The repo has useful generated metrics and smoke tests, but thesis claims need stronger evaluation:

- SBERT-only baseline,
- matrix factorization baseline,
- NCF baseline,
- DQN/skill-path baseline,
- hybrid ablation,
- cold/warm/active-user segmentation,
- Indonesian job-source coverage,
- skill-gap explanation accuracy,
- latency and failure-mode reporting,
- statistical comparison or at least repeated splits.

Why research says this matters: neural recommender papers often fail to beat tuned baselines or suffer reproducibility problems (S35). Logged implicit feedback is biased and needs careful evaluation (S16, S34). Bias and fairness risks are common in recommender systems (S36).

Required fix: write an evaluation protocol before changing model code. Treat it as a thesis chapter artifact.

### P3 - Hybrid service is present but disconnected from the active runtime

`services/hybrid/main.py` exists, but `docker-compose.yml` does not run it in the active stack. Active recommendations use `services/pipeline/stages/stage_5_aggregate.py`.

Logical fallacy: old docs that describe an active hybrid service are stale. The active hybrid logic is pipeline Stage 5.

Required fix: either delete/stale-mark the standalone hybrid service docs, or add it back to Compose and route traffic through it.

## Thesis-Grade Implementation Target

### 1. Real SBERT target

Minimum defensible target:

- Use `SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")` or a stronger multilingual/Indonesian model.
- Fine-tune with `MultipleNegativesRankingLoss`, `CosineSimilarityLoss`, or triplet loss on profile-job/skill-gap pairs.
- Store model under `services/sbert/weights/fine_tuned_sentence_transformer/`.
- Serve that model in `services/sbert/main.py`.
- Keep deterministic fallback only for unit tests.

Acceptance checks:

- `/health` says `fallback_mode=false`.
- `MODEL_DIR` contains a valid SentenceTransformer config.
- A test compares two Indonesian profile-job pairs and verifies aligned pairs score higher than hard negatives.

### 2. Real NCF target

Minimum defensible target:

- Rename current `OnlineNCF` to `OnlineMF`.
- Serve `NeuralCF` or `NeuMF` for `/recommend/ncf`.
- Train on `user_job_interactions`, with negative samples drawn from impressed-but-not-clicked jobs and sampled unobserved jobs.
- Use event weights: impression < view < detail_click/source_click < save < apply, with skip as negative.
- Persist checkpoints and ID mappings.

Acceptance checks:

- `/health` reports `model_type: "NeuMF"` or `"NeuralCF"`.
- `/recommend/ncf` calls the PyTorch model.
- A test fails if recommendation scoring only uses `np.dot(user_vec, item_vec)`.
- NCF beats the matrix-factor baseline on at least one offline ranking metric or the thesis honestly reports it does not.

### 3. Real DQN target

Minimum defensible target:

- Define the MDP:
  - State: user skills, target role, profile embedding, interaction history, current skill gaps, market-demand features.
  - Action: recommend a next skill/course/career step, or rerank a candidate job action.
  - Reward: user action reward plus skill-gap reduction and target-role relevance.
  - Transition: updated skill state/interactions after the action.
  - Done: target role achieved, no gap remains, or fixed horizon ends.
- Use `QNetwork` for action values in active serving.
- Use replay mini-batches and a target network.
- Save replay to PostgreSQL and model checkpoints to disk.
- Evaluate on simulated/offline trajectories before live feedback is available.

Acceptance checks:

- DQN endpoint returns the selected action with `q_value`, `epsilon`, `model_version`, and `policy_source`.
- Feedback inserts replay and runs a neural TD update.
- A test fails if `/api/learning-path` returns the hardcoded gateway list.
- DQN skill-path metrics are reported separately from job ranking metrics.

## Repair Roadmap

1. Rename the current model claims in docs/UI immediately to prevent thesis overclaim while implementation is being fixed.
2. Build a normalized interaction event pipeline from frontend to gateway to pipeline to NCF/DQN.
3. Implement real SBERT fine-tuning and serving.
4. Rename current `OnlineNCF` to `OnlineMF`; wire `NeuralCF` into training and serving.
5. Replace `OnlineDQN` linear weights with neural policy/target networks and replay sampling.
6. Make skill gap a first-class object in recommendations and learning-path output.
7. Add thesis evaluation scripts with baselines, ablations, and source-backed metrics.
8. Update stale docs and tests in one pass after the runtime behavior changes.

## Code Review Conclusion

SCPA has the right thesis ambition and a promising service layout, but the current active implementation is not yet the real three-model system your graduation framing requires. The biggest risk is not that the idea is weak. The biggest risk is that the code and docs currently use research model names more strongly than the active runtime supports.

If you need to defend this as a bachelor thesis, prioritize implementation truth:

- SBERT must be a served transformer sentence-embedding model, preferably fine-tuned for Indonesian career matching.
- NCF must be a served neural collaborative filtering model, not only a dot-product factor model.
- DQN must be a neural Q-learning agent with replay, target network, and a real MDP, not a static role-skill checklist.

Once those are wired into the actual browser workflow and evaluated against clear baselines, the thesis story becomes much stronger: SCPA addresses Indonesian skill-career mismatch by combining semantic understanding of job requirements, behavior-based personalization, and sequential skill-path optimization.
