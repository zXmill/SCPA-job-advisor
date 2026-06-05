# Thesis Claim Boundaries

Date: 2026-06-05

This document defines safe, conditional, and forbidden claims for the SCPA thesis. It should be used when writing Bab 1 through Bab 5 and when presenting the demo.

## Core Thesis Framing

SCPA is a decision-support system for career and job recommendation. It helps users compare their skills with job requirements, receive job recommendations, and understand individual skill gaps.

SCPA uses skill mismatch as background motivation only. The measurable object is individual-level recommendation relevance and user-job skill gap, not national labor-market transformation.

## Safe Claims

The thesis may claim:

- SCPA supports career decision-making.
- SCPA identifies individual skill gaps between a user's skills and a job's requirements.
- SCPA reduces the information gap between user skills and job requirements.
- SCPA provides explainable job recommendations with matched and missing skills.
- SBERT supports semantic matching between profile text and job text.
- NCF supports personalization when user-job interaction history exists.
- DQN supports intra-session reranking if session feedback exists and the runtime is aligned to the session-reranker contract.
- The current sample/demo pipeline can generate recommendations and compute offline metrics.
- Offline interaction rate can be used as a proxy metric when clearly labeled.
- SUS is not available unless user survey data is collected.

## Conditional Claims

Use these only when the listed evidence exists.

### SBERT improvement

Allowed only if evidence includes baseline and fine-tuned comparison with retrieval metrics:

- Recall@20
- Recall@50
- Recall@100
- NDCG@10
- NDCG@50
- MRR@10
- MAP@100

Safe wording:

"Fine-tuned SBERT improved semantic candidate retrieval on the evaluated dataset."

Unsafe wording:

"SBERT proves the system recommends the best jobs."

### NCF personalization

Allowed only if interaction data is sufficient and provenance is clear.

Safe wording:

"NCF contributes a personalization signal when historical interactions are available."

Unsafe wording:

"NCF is proven strong for all users" when the evidence is sample-scale or synthetic.

### DQN session adaptation

Allowed only if DQN runtime is aligned and evidence includes before/after session reranking.

Required evidence:

- Rank before DQN.
- Rank after DQN.
- Reward trace.
- Session Adaptation Gain.
- NDCG@K before and after DQN.

Safe wording:

"DQN provides a session-based reranking signal from observed session feedback."

Unsafe wording:

"DQN plans long-term career paths" or "DQN learns perfectly in real time."

### Hybrid model contribution

Allowed only if a controlled ablation exists.

Required variants:

- TF-IDF/BM25 baseline.
- Base SBERT.
- Fine-tuned SBERT.
- SBERT + NCF.
- SBERT + NCF + DQN.

Safe wording:

"The hybrid configuration achieved the reported metric values under the documented offline evaluation setup."

Unsafe wording:

"The hybrid model is better because it combines more algorithms."

### Latency

Allowed only for the tested environment.

Safe wording:

"Local p95 latency in the tested environment was below the configured target."

Unsafe wording:

"The system is production-ready at scale" without deployment evidence.

### Fairness

Allowed only as exploratory unless dataset size and demographic coverage are sufficient.

Safe wording:

"Fairness gap was monitored as an exploratory guardrail in the sample evaluation."

Unsafe wording:

"The system is fair" from small sample data.

### CTR or interaction rate

Use "interaction rate" unless there is actual production click-through data.

Safe wording:

"Offline interaction-rate proxy was computed from logged sample events."

Unsafe wording:

"Production CTR improved" without production traffic.

## Forbidden Claims

Do not claim:

- SCPA solves national skill mismatch.
- SCPA transforms Indonesia's labor market.
- SCPA provides a national skill-mismatch measurement.
- DQN plans long-term career paths.
- DQN is a career mentor.
- DQN uses modules, quizzes, or dropout prediction as core scope.
- DQN selects jobs directly from the raw database.
- DQN learns perfectly in real time.
- NCF is proven strong without enough interaction data.
- Simulated, sample, or fallback numbers are actual production results.
- Offline interaction proxy is production CTR.
- Fairness is proven from a tiny sample.
- Kubernetes production readiness exists unless Kubernetes was deployed and tested.
- 5,000 valid jobs exist unless a data quality report proves it.
- SBERT Top-5 results alone prove semantic candidate generation.
- More model components automatically mean better recommendations.

## Safe Bab 1 Framing

Bab 1 may say:

"SCPA is motivated by the difficulty users face when interpreting job requirements and comparing them with their own skills. The system is designed as an individual decision-support artifact that recommends jobs and explains skill gaps."

Bab 1 must not say:

"SCPA solves national skill mismatch in Indonesia."

## Safe Bab 2 Framing

Bab 2 may discuss:

- Recommender systems.
- Semantic text matching.
- Collaborative filtering.
- Reinforcement learning for reranking.
- Explainable recommendations.
- Skill-gap analysis.

Bab 2 must separate:

- Background labor-market mismatch literature.
- The actual measurable system artifact.

## Safe Bab 3 Framing

Bab 3 should define:

- SBERT as semantic candidate generator.
- NCF as historical personalization scorer.
- DQN as session-based dynamic reranker.
- Hybrid scoring formula and modes.
- Explanation layer.
- Evaluation protocol and evidence provenance.

Bab 3 must not define DQN as a learning-path planner in the core architecture.

## Safe Bab 4 Framing

Bab 4 may report:

- Dataset quality results.
- SBERT retrieval metrics.
- NCF interaction and personalization metrics.
- DQN session adaptation metrics.
- Ablation results.
- Latency results.
- User-testing and SUS results if collected.

Bab 4 must label:

- sample data
- synthetic data
- offline simulation
- fallback mode
- local-machine measurements
- missing SUS

Bab 4 must not present sample/demo metrics as production results.

## Safe Bab 5 Framing

Bab 5 should include limitations:

- Dataset size and provenance.
- Interaction-data limitations.
- Missing or limited user testing.
- No national-scale labor-market claim.
- No Kubernetes production claim unless tested.
- DQN session-reranker evidence boundaries.
- Fairness as exploratory unless supported by larger data.

Bab 5 may propose future work:

- Learning path generation.
- Career mentor features.
- Module/quiz/dropout planning.
- Kubernetes production deployment.
- Larger user study and SUS analysis.
- Larger-scale labor-market analysis.

## Demo Script Boundaries

Safe demo explanation:

"The system ranks jobs by combining semantic fit, historical interaction signals where available, and session reranking when available. It then explains matched and missing skills for each recommendation."

Unsafe demo explanation:

"The system solves the skill mismatch problem" or "DQN plans your full career path."

## Logical Fallacy Checklist

Before finalizing any thesis text, check:

- Hasty generalization: do not generalize from SCPA to national labor-market outcomes.
- Causal oversimplification: do not imply recommendations solve structural employment problems.
- Unsupported conclusion: do not report simulated results as actual results.
- Appeal to complexity: do not claim SBERT + NCF + DQN is better just because it is more complex.
- Category error: do not mix DQN learning path with DQN session reranking.
- False equivalence: do not treat limited testing interaction rate as production CTR.
- Conflation: do not confuse individual skill gap with national skill mismatch.
- Composition fallacy: do not assume component improvement guarantees end-to-end improvement.
- False precision: do not overstate precise metrics without reproducible experiment details.
- Appeal to novelty: do not claim contribution only because the model combination sounds new.

## What Was Inspected

- Revised thesis architecture from the user request.
- Current reports and docs that mention DQN career milestones, learning paths, sample metrics, SUS, fallback, and proxy CTR.
- Phase 0 audit outputs.

## What Was Changed

- This thesis claim boundary document was created.
- No runtime code or thesis chapter draft was changed.

## What Was Not Changed

- Existing `docs/THESIS_WRITING_NOTES.md`, `docs/MODELS.md`, `docs/ARCHITECTURE.md`, and reports were not rewritten in this phase.

## Commands Run

See `docs/audit/PROJECT_STATE_AUDIT.md`.

## Tests Run

No runtime tests were run for this documentation-only phase.

## Remaining Risks

- Existing project docs still contain old DQN learning-path framing.
- Runtime code still contains active learning-path endpoints.
- Bab 4 and Bab 5 should not be finalized until evidence-hardening phases are complete.
