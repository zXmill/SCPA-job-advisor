"""Fine-tune a SentenceTransformer on Indonesian profile-job pairs.

Uses a multilingual base model suitable for Indonesian (paraphrase-multilingual-
MiniLM-L12-v2) and trains with MultipleNegativesRankingLoss on anchor-positive-
negative triplets mined from the labeled dataset.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Lazy-import heavy dependencies inside functions to keep CLI --help fast


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n\r")
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _build_triplets(records: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Return (anchor, positive, negative) triplets from labeled pairs."""

    triplets: list[tuple[str, str, str]] = []
    for r in records:
        if r.get("pair_kind") != "positive":
            continue
        anchor = str(r.get("profile_text", "")).strip()
        positive = str(r.get("job_text", "")).strip()
        negative = str(r.get("hard_negative_text", "")).strip()
        if anchor and positive and negative:
            triplets.append((anchor, positive, negative))
    return triplets


def _build_pair_examples(records: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    """Return (text_a, text_b, label) examples for contrastive training."""

    examples: list[tuple[str, str, float]] = []
    for r in records:
        anchor = str(r.get("profile_text", "")).strip()
        other = str(r.get("job_text", "")).strip()
        label = float(r.get("label", 0.0))
        if anchor and other:
            examples.append((anchor, other, label))
    return examples


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.dot(a, b))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return dot / norm if norm > 0 else 0.0


def _rank_jobs_for_profile(
    profile_text: str,
    job_texts: list[str],
    embed_fn: Any,
) -> list[tuple[str, float]]:
    profile_emb = embed_fn(profile_text)
    scored: list[tuple[str, float]] = []
    for job_text in job_texts:
        job_emb = embed_fn(job_text)
        score = _cosine_similarity(profile_emb, job_emb)
        scored.append((job_text, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def fine_tune_sbert(
    data_path: Path,
    output_dir: Path,
    *,
    base_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
    epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 2e-5,
    warmup_fraction: float = 0.1,
    max_seq_length: int = 256,
    device: str | None = None,
) -> dict[str, Any]:
    """Fine-tune a multilingual SentenceTransformer on Indonesian profile-job pairs."""

    # Heavy imports deferred
    import torch
    from sentence_transformers import InputExample, SentenceTransformer
    from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss
    from torch.utils.data import DataLoader

    records = load_jsonl(data_path)
    triplets = _build_triplets(records)
    if not triplets:
        raise ValueError("no training triplets found; ensure dataset has positive pairs with hard_negative_text")

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    model = SentenceTransformer(base_model, device=device)
    model.max_seq_length = max_seq_length

    train_examples = [
        InputExample(texts=[anchor, positive, negative])
        for anchor, positive, negative in triplets
    ]
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=batch_size)
    train_loss = MultipleNegativesRankingLoss(model)

    steps_per_epoch = max(1, math.ceil(len(train_examples) / batch_size))
    warmup_steps = max(1, int(steps_per_epoch * epochs * warmup_fraction))

    output_dir.mkdir(parents=True, exist_ok=True)

    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=epochs,
        warmup_steps=warmup_steps,
        optimizer_params={"lr": learning_rate},
        show_progress_bar=True,
        output_path=str(output_dir),
        save_best_model=True,
    )

    # Compute post-training validation metrics on the training triplets
    # (lightweight sanity check using cosine similarity)
    def _embed(text: str) -> np.ndarray:
        return model.encode(text, convert_to_numpy=True, show_progress_bar=False)

    margins: list[float] = []
    for anchor, positive, negative in triplets:
        pos_score = _cosine_similarity(_embed(anchor), _embed(positive))
        neg_score = _cosine_similarity(_embed(anchor), _embed(negative))
        margins.append(pos_score - neg_score)

    metrics = {
        "base_model": base_model,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "train_triplets": len(triplets),
        "mean_margin": round(sum(margins) / len(margins), 6) if margins else 0.0,
        "min_margin": round(min(margins), 6) if margins else 0.0,
        "positive_outranks_negative_rate": round(
            sum(1 for m in margins if m > 0) / len(margins), 6
        ) if margins else 0.0,
        "output_dir": str(output_dir),
    }
    (output_dir / "finetune_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    return metrics


def evaluate_finetuned_model(
    data_path: Path,
    model_dir: Path,
    output_dir: Path,
    *,
    k_values: tuple[int, ...] = (5, 10),
    device: str | None = None,
) -> dict[str, Any]:
    """Evaluate a fine-tuned SentenceTransformer using ranking metrics."""

    import torch
    from sentence_transformers import SentenceTransformer
    from services.evaluation.recommendation_metrics import (
        recall_at_k,
        ndcg_at_k,
        reciprocal_rank_at_k,
        mean_metric,
    )

    records = load_jsonl(data_path)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = SentenceTransformer(str(model_dir), device=device)

    # Group by profile: each profile has a set of relevant jobs and a candidate pool
    profile_to_relevant: dict[str, set[str]] = {}
    profile_to_candidates: dict[str, set[str]] = {}
    profile_texts: dict[str, str] = {}

    for r in records:
        profile_id = str(r.get("profile_id", ""))
        job_id = str(r.get("job_id", ""))
        profile_text = str(r.get("profile_text", "")).strip()
        job_text = str(r.get("job_text", "")).strip()
        label = float(r.get("label", 0.0))
        if not profile_id or not job_id or not profile_text or not job_text:
            continue
        profile_texts[profile_id] = profile_text
        profile_to_candidates.setdefault(profile_id, set()).add(job_text)
        if label >= 0.7:
            profile_to_relevant.setdefault(profile_id, set()).add(job_text)

    # Embed all unique texts
    all_texts: list[str] = []
    text_to_emb: dict[str, np.ndarray] = {}
    for profile_id, job_texts in profile_to_candidates.items():
        all_texts.append(profile_texts[profile_id])
        all_texts.extend(job_texts)
    all_texts = list(dict.fromkeys(all_texts))  # dedup preserve order

    embs = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=True, batch_size=32)
    for text, emb in zip(all_texts, embs):
        text_to_emb[text] = emb

    rankings: dict[str, list[str]] = {}
    relevant_by_profile: dict[str, set[str]] = {}
    for profile_id, candidates in profile_to_candidates.items():
        profile_emb = text_to_emb[profile_texts[profile_id]]
        scored = [
            (job_text, _cosine_similarity(profile_emb, text_to_emb[job_text]))
            for job_text in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        rankings[profile_id] = [job_text for job_text, _ in scored]
        relevant_by_profile[profile_id] = profile_to_relevant.get(profile_id, set())

    report: dict[str, Any] = {
        "dataset": str(data_path),
        "model_dir": str(model_dir),
        "n_profiles": len(rankings),
    }
    for k in k_values:
        report[f"recall_at_{k}"] = round(
            mean_metric(
                recall_at_k(rankings.get(pid, []), relevant_by_profile.get(pid, set()), k)
                for pid in rankings
            ),
            6,
        )
        report[f"mrr_at_{k}"] = round(
            mean_metric(
                reciprocal_rank_at_k(rankings.get(pid, []), relevant_by_profile.get(pid, set()), k)
                for pid in rankings
            ),
            6,
        )
        report[f"ndcg_at_{k}"] = round(
            mean_metric(
                ndcg_at_k(rankings.get(pid, []), relevant_by_profile.get(pid, set()), k)
                for pid in rankings
            ),
            6,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "finetuned_sbert_evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def generate_skill_gap_examples(
    data_path: Path,
    model_dir: Path,
    output_dir: Path,
    *,
    top_k: int = 3,
    device: str | None = None,
) -> list[dict[str, Any]]:
    """Generate qualitative skill-gap examples from model predictions.

    For each profile, compare top-K predicted jobs against the ground-truth
    relevant jobs to surface missing skills.
    """

    import torch
    from sentence_transformers import SentenceTransformer

    records = load_jsonl(data_path)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = SentenceTransformer(str(model_dir), device=device)

    # Build profile -> relevant jobs mapping
    profile_to_relevant: dict[str, set[str]] = {}
    profile_to_relevant_skills: dict[str, set[str]] = {}
    profile_to_candidates: dict[str, list[tuple[str, str, list[str]]]] = {}
    profile_texts: dict[str, str] = {}
    profile_skills: dict[str, set[str]] = {}

    for r in records:
        profile_id = str(r.get("profile_id", ""))
        profile_text = str(r.get("profile_text", "")).strip()
        job_text = str(r.get("job_text", "")).strip()
        label = float(r.get("label", 0.0))
        job_skills = [s.lower() for s in (r.get("job_skills") or [])]
        p_skills = [s.lower() for s in (r.get("profile_skills") or [])]
        if not profile_id or not profile_text or not job_text:
            continue
        profile_texts[profile_id] = profile_text
        profile_skills.setdefault(profile_id, set()).update(p_skills)
        profile_to_candidates.setdefault(profile_id, []).append((job_text, r.get("job_id", ""), job_skills))
        if label >= 0.7:
            profile_to_relevant.setdefault(profile_id, set()).add(job_text)
            profile_to_relevant_skills.setdefault(profile_id, set()).update(job_skills)

    all_texts = list(dict.fromkeys([
        *list(profile_texts.values()),
        *[jt for items in profile_to_candidates.values() for jt, _, _ in items],
    ]))
    embs = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=False, batch_size=32)
    text_to_emb = dict(zip(all_texts, embs))

    examples: list[dict[str, Any]] = []
    for profile_id, candidates in profile_to_candidates.items():
        profile_emb = text_to_emb[profile_texts[profile_id]]
        scored = [
            (_cosine_similarity(profile_emb, text_to_emb[job_text]), job_text, job_id, job_skills)
            for job_text, job_id, job_skills in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        top_predicted = scored[:top_k]
        relevant = profile_to_relevant.get(profile_id, set())
        relevant_skills = profile_to_relevant_skills.get(profile_id, set())
        p_skills = profile_skills.get(profile_id, set())

        # Skill gap: skills in relevant jobs but not in profile
        missing_skills = sorted(relevant_skills - p_skills)
        # False positive skills: skills in top predicted but not in relevant
        fp_skills: set[str] = set()
        for _, _, _, job_skills in top_predicted:
            fp_skills.update(set(job_skills) - relevant_skills)

        examples.append({
            "profile_id": profile_id,
            "profile_text": profile_texts[profile_id],
            "profile_skills": sorted(p_skills),
            "relevant_jobs": sorted(relevant),
            "top_predicted_jobs": [
                {"job_id": jid, "job_text": jt, "score": round(float(sc), 6)}
                for sc, jt, jid, _ in top_predicted
            ],
            "skill_gaps": missing_skills,
            "false_positive_skills": sorted(fp_skills),
            "hit_in_top_k": any(jt in relevant for _, jt, _, _ in top_predicted),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "skill_gap_examples.json").write_text(
        json.dumps(examples, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return examples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fine-tune SBERT on Indonesian profile-job pairs")
    subparsers = parser.add_subparsers(dest="command")

    # train
    train_parser = subparsers.add_parser("train", help="Fine-tune the model")
    train_parser.add_argument("--data", type=Path, default=Path("services/sbert/training/data/indonesian_profile_job_pairs.jsonl"))
    train_parser.add_argument("--output-dir", type=Path, default=Path("services/sbert/models/finetuned_indonesian"))
    train_parser.add_argument("--base-model", default="paraphrase-multilingual-MiniLM-L12-v2")
    train_parser.add_argument("--epochs", type=int, default=3)
    train_parser.add_argument("--batch-size", type=int, default=8)
    train_parser.add_argument("--lr", type=float, default=2e-5)
    train_parser.add_argument("--device", default=None)

    # eval
    eval_parser = subparsers.add_parser("eval", help="Evaluate the fine-tuned model")
    eval_parser.add_argument("--data", type=Path, default=Path("services/sbert/training/data/indonesian_profile_job_pairs.jsonl"))
    eval_parser.add_argument("--model-dir", type=Path, default=Path("services/sbert/models/finetuned_indonesian"))
    eval_parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/finetuned_sbert"))
    eval_parser.add_argument("--k", type=int, nargs="+", default=[5, 10])
    eval_parser.add_argument("--device", default=None)

    # skill-gaps
    gap_parser = subparsers.add_parser("skill-gaps", help="Generate qualitative skill-gap examples")
    gap_parser.add_argument("--data", type=Path, default=Path("services/sbert/training/data/indonesian_profile_job_pairs.jsonl"))
    gap_parser.add_argument("--model-dir", type=Path, default=Path("services/sbert/models/finetuned_indonesian"))
    gap_parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation/finetuned_sbert"))
    gap_parser.add_argument("--top-k", type=int, default=3)
    gap_parser.add_argument("--device", default=None)

    args = parser.parse_args(argv)
    if args.command == "train":
        metrics = fine_tune_sbert(
            args.data,
            args.output_dir,
            base_model=args.base_model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.lr,
            device=args.device,
        )
        print(json.dumps(metrics, indent=2))
    elif args.command == "eval":
        report = evaluate_finetuned_model(
            args.data,
            args.model_dir,
            args.output_dir,
            k_values=tuple(args.k),
            device=args.device,
        )
        print(json.dumps(report, indent=2))
    elif args.command == "skill-gaps":
        examples = generate_skill_gap_examples(
            args.data,
            args.model_dir,
            args.output_dir,
            top_k=args.top_k,
            device=args.device,
        )
        print(f"Generated {len(examples)} skill-gap examples")
        print(json.dumps(examples[:3], indent=2, ensure_ascii=False))
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
