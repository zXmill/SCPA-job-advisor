# SCPA Thesis Benchmark Report

Generated: `2026-06-16T15:38:29+00:00` · git `99e01fe98d`

## 0. Disclosure & Evidence Provenance

- **Main numbers** come from a *grounded simulated* behavioral benchmark: interactions are sampled from a documented click model whose preference is derived from **real** profile/job domain, occupation_group, and skill attributes. These are **offline simulation evidence**, not real-user evidence, and are disclosed as such.
- **Readiness floor** uses the real (tiny) runtime smoke set, reported honestly as `insufficient_for_generalization`.
- Models are the **real deployed classes** (`OnlineNCF` NeuMF+MF, `OnlineDQN` Q-network), trained fresh on each train split (no deployed-weight leakage).

## Benchmark: `simulated_grounded`

- provenance: `simulated_grounded` · users=300 · jobs=3818 · interactions=14400 · positive_rate=0.4367 · sessions=900

- evidence_type: `real_evaluation` · dataset_status: `sufficient_for_preliminary_evaluation`

### Split: `temporal`

- leakage guarantee: test timestamps are all >= max train timestamp — holds: `True`

- counts: {'train': 10080, 'validation': 2160, 'test': 2160} · test users scored: 135


| Variant | P@10 | R@10 | NDCG@10 | HitRate@10 | MAP@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| popularity | 0.4466 | 0.6712 | 0.5308 | 0.9925 | 0.4192 | 0.6628 |
| content | 0.5248 | 0.7783 | 0.6868 | 0.9850 | 0.5827 | 0.7979 |
| ncf | 0.3977 | 0.5718 | 0.4389 | 0.9699 | 0.3242 | 0.5768 |
| content_ncf | 0.5120 | 0.7679 | 0.6865 | 0.9850 | 0.5638 | 0.8268 |
| full_scpa | 0.5211 | 0.7879 | 0.6943 | 0.9925 | 0.5812 | 0.8212 |

Significance (full_scpa vs variant, NDCG@10):

- `full_scpa_vs_popularity_ndcg_at_10`: Δ effect=0.735, p=0.0000, significant=`True` (paired_t_test, n=133)
- `full_scpa_vs_content_ndcg_at_10`: Δ effect=0.082, p=0.3470, significant=`False` (paired_t_test, n=133)
- `full_scpa_vs_ncf_ndcg_at_10`: Δ effect=0.902, p=0.0000, significant=`True` (paired_t_test, n=133)
- `full_scpa_vs_content_ncf_ndcg_at_10`: Δ effect=0.072, p=0.4110, significant=`False` (paired_t_test, n=133)

### Split: `user_holdout`

- leakage guarantee: no user appears in both train and test — holds: `True`

- counts: {'train': 10080, 'validation': 1440, 'test': 2880} · test users scored: 60


| Variant | P@10 | R@10 | NDCG@10 | HitRate@10 | MAP@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| popularity | 0.4983 | 0.2292 | 0.3589 | 0.9833 | 0.3243 | 0.6422 |
| content | 0.6833 | 0.3184 | 0.5762 | 1.0000 | 0.5677 | 0.8579 |
| ncf | 0.5067 | 0.2285 | 0.3860 | 1.0000 | 0.3513 | 0.6863 |
| content_ncf | 0.6783 | 0.3145 | 0.5774 | 1.0000 | 0.5706 | 0.8763 |
| full_scpa | 0.6950 | 0.3230 | 0.5971 | 1.0000 | 0.5874 | 0.8745 |

Significance (full_scpa vs variant, NDCG@10):

- `full_scpa_vs_popularity_ndcg_at_10`: Δ effect=1.206, p=0.0000, significant=`True` (paired_t_test, n=60)
- `full_scpa_vs_content_ndcg_at_10`: Δ effect=0.327, p=0.0140, significant=`True` (paired_t_test, n=60)
- `full_scpa_vs_ncf_ndcg_at_10`: Δ effect=1.099, p=0.0000, significant=`True` (paired_t_test, n=60)
- `full_scpa_vs_content_ncf_ndcg_at_10`: Δ effect=0.335, p=0.0120, significant=`True` (paired_t_test, n=60)

### DQN reward stability (multi-seed)

- seeds: [1, 7, 13, 23, 42] · NDCG@10 mean=0.685466 std=0.00293 CV=0.004274 · stable=`True`
- CV < 0.10 across seeds indicates a reproducible policy (reward signal is stable, not seed noise).

### DQN held-out session rerank proxy

- sessions scored: 135 of 135 held-out sessions · event rows: 2160 · mean ΔNDCG@10=0.003714 · mean positive Δrank=-0.032009
- `positive means relevant events moved upward after DQN`. This is an offline proxy, not full off-policy evaluation.

## Readiness Floor (real smoke data)

```json
{
  "provenance": "real_readiness_smoke",
  "ncf_readiness": {
    "n_interactions": 48,
    "n_users": 8,
    "n_jobs": 6,
    "evidence_quality": {
      "evidence_type": "demo_sample_only",
      "dataset_status": "insufficient_for_generalization",
      "users_count": 8,
      "jobs_count": 6,
      "interactions_count": 48,
      "is_generalization_evidence": false,
      "evaluation_blockers": [
        "users_count 8 < minimum 30",
        "jobs_count 6 < minimum 100",
        "interactions_count 48 < minimum 300"
      ],
      "baseline_type": "real_readiness_smoke",
      "baseline_is_mock": false,
      "baseline_is_valid_for_thesis": false,
      "limitations": [
        "Dataset is below preliminary thesis-evidence thresholds."
      ],
      "minimum_thresholds": {
        "users": 30,
        "jobs": 100,
        "interactions": 300
      }
    }
  },
  "dqn_readiness": {
    "n_sessions": 12,
    "mean_dqn_reward": 2.063333,
    "mean_random_reward": 1.031667,
    "reward_lift": 2.0,
    "evidence_quality": "insufficient_for_generalization (smoke readiness set)"
  }
}
```

## What can / cannot be claimed

- CAN: the hybrid (SBERT-content + NCF + DQN) ablation is computed with the real model classes over leak-free splits; each component's marginal contribution and its statistical significance are reported on a held-out set.
- CAN: the DQN policy is reproducible across seeds (low CV).
- CANNOT: claim real-user personalization gains — the behavioral data is simulated (grounded) and must be disclosed as offline simulation in Bab IV.
- CANNOT: claim production generalization from the readiness floor (insufficient).
