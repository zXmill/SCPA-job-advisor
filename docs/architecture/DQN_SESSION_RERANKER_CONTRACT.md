# DQN Session Reranker Contract



## Purpose



Deep Q-Network (DQN) in SCPA is used as a reinforcement-learning based session reranker for job recommendations.



DQN is not a learning-path generator, career-path planner, or long-term skill-gap planner. Its purpose is to adapt the order of job candidates during the current user session based on short-term behavioral signals.



## Position in Recommendation Pipeline



The recommendation pipeline follows this sequence:



1\. SBERT generates semantic candidate jobs from profile-job text similarity.

2\. NCF reranks candidates using collaborative and interaction-based signals.

3\. DQN reranks the Top-M candidates using current-session behavioral events.

4\. Stage 5 computes the final transparent recommendation score.



DQN receives candidates that have already been processed by SBERT and NCF. DQN does not fetch jobs directly and does not own the final score.



## Canonical DQN Objective



The canonical policy objective is `session_rerank`.



The old objectives below are not active DQN behavior:



* `skill_path`

* `learning_path`

* `career_path`

* `market_demand_path`



## Canonical DQN Input



DQN receives session behavior through `session_events`.



Examples of session events include:



* `click`

* `save`

* `apply`

* `valid_dwell`

* `skip`

* `dismiss`



The gateway or pipeline may keep backward-compatible aliases internally, but the canonical DQN contract should use `session_events`.



## Canonical DQN Output



The public DQN rerank endpoint returns:



* `policy_objective`

* `ranked_jobs`

* `dqn_session_score`

* `rank`

* `rerank_reason`

* `reward_trace`



Each ranked job should include a DQN session signal through `dqn_session_score`.



## Final Score Ownership



DQN must not expose or own the final recommendation score.



The final recommendation score is owned by Stage 5 aggregation:



`final_score = alpha*sbert_score + beta*ncf_score + gamma*dqn_session_score`



This separation keeps the recommendation architecture explainable and prevents double-counting DQN output.



## Cold Start Behavior



When no useful session behavior exists, DQN contribution is disabled:



`gamma = 0.00`



In cold-start mode, the recommendation system relies on SBERT and NCF until enough session behavior is available.



## Deprecated Learning Path Route



The legacy learning-path route is not active recommendation behavior.



Authenticated requests to `/api/learning-path` should return `410 Gone`.



Unauthenticated requests should still return an authentication error such as `401 Unauthorized`.



## Thesis Explanation



In this thesis, DQN is positioned as a reinforcement learning component that performs dynamic reranking over job candidates based on user behavior in the active session. DQN learns short-term user preference signals from interactions such as clicking, saving, applying, dwelling, skipping, or dismissing a job recommendation.



DQN improves adaptivity but does not replace SBERT or NCF. SBERT provides semantic relevance, NCF provides collaborative interaction relevance, and DQN provides session-level behavioral adjustment.



