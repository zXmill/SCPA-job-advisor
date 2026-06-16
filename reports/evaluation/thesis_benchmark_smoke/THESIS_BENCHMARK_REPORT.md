# SCPA Thesis Benchmark Report

Generated: `2026-06-16T15:09:12+00:00` · git `99e01fe98d`

## 0. Disclosure & Evidence Provenance

- **Main numbers** come from a *grounded simulated* behavioral benchmark: interactions are sampled from a documented click model whose preference is derived from **real** profile/job domain, occupation_group, and skill attributes. These are **offline simulation evidence**, not real-user evidence, and are disclosed as such.
- **Readiness floor** uses the real (tiny) runtime smoke set, reported honestly as `insufficient_for_generalization`.
- Models are the **real deployed classes** (`OnlineNCF` NeuMF+MF, `OnlineDQN` Q-network), trained fresh on each train split (no deployed-weight leakage).

## Benchmark: `simulated_grounded`

- provenance: `simulated_grounded` · users=25 · jobs=382 · interactions=1250 · positive_rate=0.4384 · sessions=50

- evidence_type: `demo_sample_only` · dataset_status: `insufficient_for_generalization`

### Split: `temporal`

- leakage guarantee: test timestamps are all >= max train timestamp — holds: `True`

- counts: {'train': 876, 'validation': 187, 'test': 187} · test users scored: 8


| Variant | P@10 | R@10 | NDCG@10 | HitRate@10 | MAP@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| popularity | 0.4875 | 0.5392 | 0.4351 | 1.0000 | 0.3653 | 0.6188 |
| content | 0.5625 | 0.5929 | 0.6224 | 1.0000 | 0.5504 | 0.8167 |
| ncf | 0.3875 | 0.4258 | 0.4070 | 1.0000 | 0.3228 | 0.6375 |
| content_ncf | 0.5000 | 0.5515 | 0.5444 | 1.0000 | 0.4445 | 0.7500 |
| full_scpa | 0.5375 | 0.5779 | 0.5512 | 1.0000 | 0.4658 | 0.7292 |

Significance (full_scpa vs variant, NDCG@10):

- `full_scpa_vs_popularity_ndcg_at_10`: Δ effect=0.835, p=0.0687, significant=`False` (wilcoxon_signed_rank, n=8)
- `full_scpa_vs_content_ndcg_at_10`: Δ effect=-0.453, p=0.1614, significant=`False` (wilcoxon_signed_rank, n=8)
- `full_scpa_vs_ncf_ndcg_at_10`: Δ effect=0.585, p=0.1614, significant=`False` (wilcoxon_signed_rank, n=8)
- `full_scpa_vs_content_ncf_ndcg_at_10`: Δ effect=0.066, p=1.0000, significant=`False` (wilcoxon_signed_rank, n=8)

### Split: `user_holdout`

- leakage guarantee: no user appears in both train and test — holds: `True`

- counts: {'train': 900, 'validation': 100, 'test': 250} · test users scored: 5


| Variant | P@10 | R@10 | NDCG@10 | HitRate@10 | MAP@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| popularity | 0.3600 | 0.2258 | 0.3063 | 1.0000 | 0.2377 | 0.5786 |
| content | 0.5600 | 0.2910 | 0.4920 | 1.0000 | 0.4862 | 0.8400 |
| ncf | 0.3200 | 0.1732 | 0.2466 | 0.8000 | 0.1938 | 0.6000 |
| content_ncf | 0.5800 | 0.2860 | 0.4849 | 0.8000 | 0.5137 | 0.8000 |
| full_scpa | 0.6000 | 0.3193 | 0.5291 | 1.0000 | 0.5226 | 0.8333 |

Significance (full_scpa vs variant, NDCG@10):

- `full_scpa_vs_popularity_ndcg_at_10`: Δ effect=0.733, p=0.2249, significant=`False` (wilcoxon_signed_rank, n=5)
- `full_scpa_vs_content_ndcg_at_10`: Δ effect=0.704, p=0.2249, significant=`False` (wilcoxon_signed_rank, n=5)
- `full_scpa_vs_ncf_ndcg_at_10`: Δ effect=1.529, p=0.0431, significant=`True` (wilcoxon_signed_rank, n=5)
- `full_scpa_vs_content_ncf_ndcg_at_10`: Δ effect=1.204, p=0.0431, significant=`True` (wilcoxon_signed_rank, n=5)

### DQN reward stability (multi-seed)

- seeds: [1, 7, 13, 23, 42] · NDCG@10 mean=0.595057 std=0.018736 CV=0.031486 · stable=`True`
- CV < 0.10 across seeds indicates a reproducible policy (reward signal is stable, not seed noise).

### DQN held-out session rerank proxy

- sessions scored: 7 of 7 held-out sessions · event rows: 175 · mean ΔNDCG@10=-0.060398 · mean positive Δrank=0.1
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
