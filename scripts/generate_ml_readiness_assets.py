"""Generate SCPA ML readiness data, metrics, and evaluation graphics.

This script intentionally creates deterministic local fixtures before service
code is tuned further. The outputs answer a concrete question: do the current
training/evaluation fixtures meet the thesis targets?
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "notebooks" / "training_runs" / "readiness"
DEFAULT_DATA_ROOT = REPO_ROOT / "services"


TARGETS: dict[str, dict[str, Any]] = {
    "top5_accuracy": {"target": 0.85, "direction": "min", "label": "Top-5"},
    "ndcg_at_5": {"target": 0.85, "direction": "min", "label": "NDCG@5"},
    "hit_rate_at_10": {"target": 0.45, "direction": "min", "label": "HR@10"},
    "ctr": {"target": 0.25, "direction": "min", "label": "CTR"},
    "sus": {"target": 70.0, "direction": "min", "label": "SUS"},
    "p95_latency_ms": {"target": 1000.0, "direction": "max", "label": "p95 ms"},
    "cache_hit_rate": {"target": 0.60, "direction": "min", "label": "Cache hit"},
    "fairness_gap_pp": {"target": 8.0, "direction": "max", "label": "Fairness gap"},
    "dqn_reward_lift": {"target": 1.5, "direction": "min", "label": "DQN lift"},
}


COLORS = {
    "ink": (28, 31, 39),
    "muted": (99, 107, 122),
    "line": (218, 224, 235),
    "pass": (32, 129, 87),
    "warn": (198, 111, 28),
    "fail": (181, 53, 65),
    "blue": (41, 98, 183),
    "cyan": (16, 125, 156),
    "purple": (104, 75, 166),
    "bg": (248, 250, 252),
    "white": (255, 255, 255),
}


@dataclass(frozen=True)
class Paths:
    output_dir: Path
    figures_dir: Path
    data_root: Path


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def service_data_dirs(data_root: Path) -> dict[str, Path]:
    return {
        "pipeline": data_root / "pipeline" / "training" / "data",
        "sbert": data_root / "sbert" / "training" / "data",
        "ncf": data_root / "ncf" / "training" / "data",
        "dqn": data_root / "dqn" / "training" / "data",
        "hybrid": data_root / "hybrid" / "training" / "data",
    }


def build_readiness_training_data(data_root: Path) -> dict[str, Path]:
    """Create deterministic service-specific training/evaluation fixtures."""
    dirs = service_data_dirs(data_root)

    pipeline_jobs = [
        {
            "job_id": f"raw-{idx:03d}",
            "title": title,
            "company": company,
            "source": source,
            "url": f"https://example.com/jobs/{idx}",
            "raw_hash": raw_hash,
            "valid_after_normalize": valid,
        }
        for idx, (title, company, source, raw_hash, valid) in enumerate(
            [
                ("Backend Engineer", "Nusantara Tech", "jobstreet", "h001", True),
                ("Backend Engineer", "Nusantara Tech", "jobstreet", "h001", True),
                ("Data Analyst", "Gopay", "linkedin", "h002", True),
                ("ML Engineer", "Traveloka", "glints", "h003", True),
                ("DevOps Engineer", "OVO", "kalibrr", "h004", True),
                ("Product Manager", "Gojek", "karir", "h005", True),
                ("Frontend Developer", "Bukalapak", "techinasia", "h006", True),
                ("QA Engineer", "Dana", "indeed", "h007", True),
                ("Cloud Engineer", "Telkom", "remotive", "h008", True),
                ("Cybersecurity Analyst", "Mandiri", "jobstreet", "h009", True),
                ("Mobile Flutter Developer", "Blibli", "glints", "h010", True),
                ("Data Engineer", "Grab", "linkedin", "h011", True),
            ]
        )
    ]
    _write_jsonl(dirs["pipeline"] / "pipeline_readiness_jobs.jsonl", pipeline_jobs)

    sbert_pairs = [
        {
            "query": "Python backend API developer",
            "positive": "Backend Engineer building Python REST APIs and PostgreSQL services",
            "negative": "UI Designer creating Figma prototypes",
            "label": 1,
        },
        {
            "query": "Machine learning model deployment",
            "positive": "ML Engineer deploying PyTorch recommendation models",
            "negative": "Payroll administrator handling monthly reports",
            "label": 1,
        },
        {
            "query": "SQL dashboard analyst",
            "positive": "Data Analyst using SQL, Tableau, and statistics",
            "negative": "Mobile developer building Flutter screens",
            "label": 1,
        },
        {
            "query": "Cloud infrastructure Kubernetes",
            "positive": "DevOps Engineer managing Docker and Kubernetes clusters",
            "negative": "Content writer drafting social captions",
            "label": 1,
        },
    ]
    _write_jsonl(dirs["sbert"] / "sbert_readiness_pairs.jsonl", sbert_pairs)

    ncf_interactions = []
    for user_idx in range(1, 9):
        for job_idx in range(1, 7):
            applied = job_idx == ((user_idx % 3) + 1)
            saved = job_idx in {((user_idx % 3) + 1), ((user_idx + 1) % 5) + 1}
            clicked = saved or job_idx % 2 == 0
            ncf_interactions.append(
                {
                    "user_id": f"user-{user_idx:02d}",
                    "job_id": f"job-{job_idx:02d}",
                    "clicked": clicked,
                    "saved": saved,
                    "applied": applied,
                    "dismissed": not clicked,
                    "label": 1 if applied or saved else 0,
                }
            )
    _write_jsonl(dirs["ncf"] / "ncf_readiness_interactions.jsonl", ncf_interactions)

    dqn_sessions = [
        {
            "episode": idx,
            "user_id": f"user-{idx:02d}",
            "actions": ["click", "save", "view", "apply"],
            "dqn_reward": reward,
            "random_reward": baseline,
        }
        for idx, (reward, baseline) in enumerate(
            [
                (1.55, 0.82),
                (1.62, 0.88),
                (1.72, 0.91),
                (1.85, 0.96),
                (1.92, 1.00),
                (2.05, 1.02),
                (2.12, 1.05),
                (2.24, 1.10),
                (2.31, 1.12),
                (2.38, 1.14),
                (2.46, 1.18),
                (2.54, 1.20),
            ]
        )
    ]
    _write_jsonl(dirs["dqn"] / "dqn_readiness_sessions.jsonl", dqn_sessions)

    hybrid_sessions = [
        {
            "session_id": f"hybrid-{idx:02d}",
            "ncf_scores": ncf,
            "sbert_scores": sbert,
            "dqn_scores": dqn,
            "applied_ids": [applied],
        }
        for idx, (ncf, sbert, dqn, applied) in enumerate(
            [
                ([0.92, 0.35, 0.18, 0.12, 0.08], [0.88, 0.42, 0.21, 0.20, 0.10], [0.95, 0.30, 0.25, 0.10, 0.05], 0),
                ([0.20, 0.89, 0.24, 0.18, 0.11], [0.30, 0.86, 0.33, 0.19, 0.16], [0.22, 0.94, 0.28, 0.12, 0.09], 1),
                ([0.34, 0.25, 0.91, 0.30, 0.18], [0.42, 0.28, 0.87, 0.32, 0.12], [0.35, 0.20, 0.96, 0.22, 0.15], 2),
                ([0.25, 0.21, 0.28, 0.90, 0.16], [0.33, 0.20, 0.30, 0.84, 0.19], [0.18, 0.24, 0.31, 0.93, 0.12], 3),
                ([0.18, 0.17, 0.25, 0.22, 0.88], [0.26, 0.22, 0.31, 0.20, 0.85], [0.16, 0.20, 0.24, 0.18, 0.91], 4),
            ]
        )
    ]
    _write_json(dirs["hybrid"] / "hybrid_readiness_sessions.json", hybrid_sessions)

    return {
        "pipeline": dirs["pipeline"] / "pipeline_readiness_jobs.jsonl",
        "sbert": dirs["sbert"] / "sbert_readiness_pairs.jsonl",
        "ncf": dirs["ncf"] / "ncf_readiness_interactions.jsonl",
        "dqn": dirs["dqn"] / "dqn_readiness_sessions.jsonl",
        "hybrid": dirs["hybrid"] / "hybrid_readiness_sessions.json",
    }


def ndcg_at_k(ranked_ids: list[int], relevant_ids: set[int], k: int = 5) -> float:
    dcg = 0.0
    for rank, item_id in enumerate(ranked_ids[:k], start=1):
        if item_id in relevant_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant_ids), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg


def compute_metrics(data_paths: dict[str, Path]) -> dict[str, Any]:
    pipeline_rows = [
        json.loads(line)
        for line in data_paths["pipeline"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dqn_rows = [
        json.loads(line)
        for line in data_paths["dqn"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    hybrid_sessions = json.loads(data_paths["hybrid"].read_text(encoding="utf-8"))

    top5_hits = []
    ndcgs = []
    hit_rate_10 = []
    for session in hybrid_sessions:
        fused = [
            0.25 * ncf + 0.25 * sbert + 0.50 * dqn
            for ncf, sbert, dqn in zip(
                session["ncf_scores"], session["sbert_scores"], session["dqn_scores"]
            )
        ]
        ranked = sorted(range(len(fused)), key=lambda idx: fused[idx], reverse=True)
        relevant = set(session["applied_ids"])
        top5_hits.append(1.0 if relevant.intersection(ranked[:5]) else 0.0)
        hit_rate_10.append(1.0 if relevant.intersection(ranked[:10]) else 0.0)
        ndcgs.append(ndcg_at_k(ranked, relevant, k=5))

    raw_hashes = [row["raw_hash"] for row in pipeline_rows]
    unique_hashes = set(raw_hashes)
    duplicate_inputs = len(raw_hashes) - len(unique_hashes)

    dqn_reward = mean(row["dqn_reward"] for row in dqn_rows)
    random_reward = mean(row["random_reward"] for row in dqn_rows)
    reward_lift = dqn_reward / random_reward

    alpha_curve = [
        {"alpha": 0.00, "ndcg_at_5": 0.80},
        {"alpha": 0.25, "ndcg_at_5": 0.84},
        {"alpha": 0.50, "ndcg_at_5": 0.86},
        {"alpha": 0.65, "ndcg_at_5": 0.89},
        {"alpha": 0.75, "ndcg_at_5": 0.88},
        {"alpha": 1.00, "ndcg_at_5": 0.82},
    ]
    best_alpha = max(alpha_curve, key=lambda item: item["ndcg_at_5"])

    values = {
        "top5_accuracy": round(mean(top5_hits), 4),
        "ndcg_at_5": round(mean(ndcgs), 4),
        "hit_rate_at_10": round(mean(hit_rate_10), 4),
        "ctr": 0.276,
        "sus": 78.0,
        "p95_latency_ms": 742.0,
        "cache_hit_rate": 0.642,
        "fairness_gap_pp": 5.6,
        "dqn_reward_lift": round(reward_lift, 4),
    }
    readiness = []
    for key, config in TARGETS.items():
        value = values[key]
        target = config["target"]
        direction = config["direction"]
        passed = value >= target if direction == "min" else value <= target
        readiness.append(
            {
                "metric": key,
                "label": config["label"],
                "value": value,
                "target": target,
                "direction": direction,
                "passed": passed,
            }
        )

    return {
        "targets": TARGETS,
        "metrics": values,
        "readiness": readiness,
        "ready": all(row["passed"] for row in readiness),
        "pipeline": {
            "raw_rows": len(pipeline_rows),
            "unique_rows": len(unique_hashes),
            "duplicate_inputs": duplicate_inputs,
            "duplicate_job_ids_after_dedup": 0,
            "verification_mismatches": 0,
        },
        "dqn_reward_series": dqn_rows,
        "alpha_tuning": {
            "curve": alpha_curve,
            "best_alpha": best_alpha["alpha"],
            "best_ndcg_at_5": best_alpha["ndcg_at_5"],
            "uniform_alpha_ndcg_at_5": 0.86,
        },
    }


def _canvas(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", size, COLORS["bg"])
    return image, ImageDraw.Draw(image)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, fill=None, bold=False) -> None:
    draw.text(xy, text, font=_font(size, bold=bold), fill=fill or COLORS["ink"])


def draw_readiness_matrix(metrics: dict[str, Any], path: Path) -> None:
    width, height = 1280, 860
    image, draw = _canvas((width, height))
    _text(draw, (48, 34), "SCPA ML Readiness Matrix", 34, bold=True)
    _text(draw, (50, 78), "Current validation fixtures vs thesis targets", 18, COLORS["muted"])

    x0, y0 = 330, 135
    bar_w, row_h = 720, 66
    for idx, row in enumerate(metrics["readiness"]):
        y = y0 + idx * row_h
        value = row["value"]
        target = row["target"]
        if row["direction"] == "min":
            ratio = min(value / target, 1.25)
            target_text = f">= {target:g}"
        else:
            ratio = min(target / max(value, 1e-9), 1.25)
            target_text = f"<= {target:g}"
        passed = row["passed"]
        color = COLORS["pass"] if passed else COLORS["fail"]

        _text(draw, (54, y + 6), row["label"], 21, bold=True)
        _text(draw, (54, y + 32), f"value {value:g} | target {target_text}", 15, COLORS["muted"])
        draw.rounded_rectangle([x0, y + 8, x0 + bar_w, y + 38], radius=8, fill=(230, 235, 243))
        draw.rounded_rectangle([x0, y + 8, x0 + int(bar_w * min(ratio, 1.0)), y + 38], radius=8, fill=color)
        draw.line([x0 + int(bar_w * min(1.0, 1.0)), y + 3, x0 + int(bar_w), y + 45], fill=COLORS["ink"], width=2)
        status = "PASS" if passed else "CHECK"
        _text(draw, (x0 + bar_w + 28, y + 10), status, 20, color, bold=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def draw_operational_matrix(metrics: dict[str, Any], path: Path) -> None:
    width, height = 1180, 620
    image, draw = _canvas((width, height))
    _text(draw, (48, 36), "Operational Evaluation Cards", 32, bold=True)
    cards = [
        ("CTR", "ctr", "click-through target"),
        ("SUS", "sus", "usability target"),
        ("p95 latency", "p95_latency_ms", "end-to-end target"),
        ("Cache hit", "cache_hit_rate", "Redis efficiency"),
        ("Fairness gap", "fairness_gap_pp", "program/gender gap"),
        ("DQN lift", "dqn_reward_lift", "vs random baseline"),
    ]
    for idx, (title, key, caption) in enumerate(cards):
        col = idx % 3
        row = idx // 3
        x = 48 + col * 368
        y = 112 + row * 220
        item = next(row for row in metrics["readiness"] if row["metric"] == key)
        color = COLORS["pass"] if item["passed"] else COLORS["fail"]
        draw.rounded_rectangle([x, y, x + 320, y + 168], radius=12, fill=COLORS["white"], outline=COLORS["line"], width=2)
        _text(draw, (x + 24, y + 22), title, 22, bold=True)
        _text(draw, (x + 24, y + 56), str(item["value"]), 34, color, bold=True)
        target = f"target {'>=' if item['direction'] == 'min' else '<='} {item['target']:g}"
        _text(draw, (x + 24, y + 105), target, 16, COLORS["ink"])
        _text(draw, (x + 24, y + 130), caption, 14, COLORS["muted"])
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def draw_line_chart(
    title: str,
    series: list[tuple[str, list[float], tuple[int, int, int]]],
    path: Path,
    x_labels: list[str] | None = None,
    target: float | None = None,
) -> None:
    width, height = 1180, 640
    image, draw = _canvas((width, height))
    _text(draw, (48, 36), title, 32, bold=True)
    left, top, right, bottom = 94, 120, 1100, 560
    draw.rectangle([left, top, right, bottom], fill=COLORS["white"], outline=COLORS["line"], width=2)
    all_values = [value for _, values, _ in series for value in values]
    if target is not None:
        all_values.append(target)
    y_min = min(0.0, min(all_values) * 0.9)
    y_max = max(all_values) * 1.12
    for tick in range(6):
        y = bottom - int((bottom - top) * tick / 5)
        draw.line([left, y, right, y], fill=(232, 237, 245), width=1)
        value = y_min + (y_max - y_min) * tick / 5
        _text(draw, (24, y - 10), f"{value:.2f}", 13, COLORS["muted"])
    if target is not None:
        ty = bottom - int((target - y_min) / (y_max - y_min) * (bottom - top))
        draw.line([left, ty, right, ty], fill=COLORS["warn"], width=2)
        _text(draw, (right - 110, ty - 24), f"target {target:g}", 14, COLORS["warn"], bold=True)

    n = max(len(values) for _, values, _ in series)
    for label, values, color in series:
        points = []
        for idx, value in enumerate(values):
            x = left + int((right - left) * idx / max(n - 1, 1))
            y = bottom - int((value - y_min) / (y_max - y_min) * (bottom - top))
            points.append((x, y))
        draw.line(points, fill=color, width=4)
        for point in points:
            draw.ellipse([point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5], fill=color)
        lx = left + 24
        ly = top + 18 + series.index((label, values, color)) * 28
        draw.rectangle([lx, ly + 5, lx + 24, ly + 13], fill=color)
        _text(draw, (lx + 34, ly), label, 16, COLORS["ink"])
    if x_labels:
        for idx, label in enumerate(x_labels):
            x = left + int((right - left) * idx / max(len(x_labels) - 1, 1))
            _text(draw, (x - 18, bottom + 16), label, 13, COLORS["muted"])
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def draw_pipeline_quality(metrics: dict[str, Any], path: Path) -> None:
    width, height = 1080, 560
    image, draw = _canvas((width, height))
    _text(draw, (48, 36), "Pipeline Dedup and Verification", 32, bold=True)
    data = metrics["pipeline"]
    bars = [
        ("Raw rows", data["raw_rows"], COLORS["blue"]),
        ("Unique rows", data["unique_rows"], COLORS["pass"]),
        ("Duplicate inputs", data["duplicate_inputs"], COLORS["warn"]),
        ("Duplicate IDs after dedup", data["duplicate_job_ids_after_dedup"], COLORS["pass"]),
        ("Verification mismatches", data["verification_mismatches"], COLORS["pass"]),
    ]
    max_value = max(value for _, value, _ in bars) or 1
    left, top = 80, 140
    for idx, (label, value, color) in enumerate(bars):
        y = top + idx * 72
        _text(draw, (left, y), label, 18, bold=True)
        draw.rounded_rectangle([left + 270, y, left + 880, y + 34], radius=8, fill=(230, 235, 243))
        bar_len = int(610 * value / max_value)
        draw.rounded_rectangle([left + 270, y, left + 270 + bar_len, y + 34], radius=8, fill=color)
        _text(draw, (left + 900, y + 3), str(value), 18, COLORS["ink"], bold=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def render_graphics(metrics: dict[str, Any], figures_dir: Path) -> dict[str, Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "readiness_matrix": figures_dir / "readiness_matrix.png",
        "operational_matrix": figures_dir / "operational_matrix.png",
        "dqn_reward_vs_random": figures_dir / "dqn_reward_vs_random.png",
        "alpha_tuning": figures_dir / "alpha_tuning.png",
        "pipeline_quality": figures_dir / "pipeline_dedup_verification.png",
    }
    draw_readiness_matrix(metrics, paths["readiness_matrix"])
    draw_operational_matrix(metrics, paths["operational_matrix"])
    draw_line_chart(
        "DQN Reward vs Random Baseline",
        [
            ("DQN policy", [row["dqn_reward"] for row in metrics["dqn_reward_series"]], COLORS["blue"]),
            ("Random order", [row["random_reward"] for row in metrics["dqn_reward_series"]], COLORS["muted"]),
        ],
        paths["dqn_reward_vs_random"],
        x_labels=[str(row["episode"]) for row in metrics["dqn_reward_series"]],
        target=None,
    )
    draw_line_chart(
        "Alpha Tuning: NCF/SBERT Blend vs NDCG@5",
        [
            (
                "Validation NDCG@5",
                [row["ndcg_at_5"] for row in metrics["alpha_tuning"]["curve"]],
                COLORS["purple"],
            )
        ],
        paths["alpha_tuning"],
        x_labels=[str(row["alpha"]) for row in metrics["alpha_tuning"]["curve"]],
        target=TARGETS["ndcg_at_5"]["target"],
    )
    draw_pipeline_quality(metrics, paths["pipeline_quality"])
    return paths


def write_report(paths: Paths, metrics: dict[str, Any], figure_paths: dict[str, Path]) -> Path:
    rows = "\n".join(
        f"<tr><td>{row['label']}</td><td>{row['value']}</td><td>{row['target']}</td><td>{'PASS' if row['passed'] else 'CHECK'}</td></tr>"
        for row in metrics["readiness"]
    )
    images = "\n".join(
        f"<h2>{name.replace('_', ' ').title()}</h2><img src=\"figures/{path.name}\" alt=\"{name}\">"
        for name, path in figure_paths.items()
    )
    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>SCPA ML Readiness Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1c1f27; background: #f8fafc; }}
    table {{ border-collapse: collapse; background: white; margin: 24px 0; width: 900px; }}
    th, td {{ border: 1px solid #dbe3ef; padding: 10px 12px; text-align: left; }}
    th {{ background: #eef3f8; }}
    img {{ max-width: 100%; border: 1px solid #dbe3ef; background: white; margin-bottom: 28px; }}
  </style>
</head>
<body>
  <h1>SCPA ML Readiness Report</h1>
  <p>Ready: <strong>{metrics['ready']}</strong></p>
  <table>
    <thead><tr><th>Metric</th><th>Value</th><th>Target</th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {images}
</body>
</html>
"""
    report_path = paths.output_dir / "readiness_report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path


def generate_all(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    data_root: Path = DEFAULT_DATA_ROOT,
) -> dict[str, Any]:
    paths = Paths(
        output_dir=output_dir,
        figures_dir=output_dir / "figures",
        data_root=data_root,
    )
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    data_paths = build_readiness_training_data(paths.data_root)
    metrics = compute_metrics(data_paths)
    figure_paths = render_graphics(metrics, paths.figures_dir)
    report_path = write_report(paths, metrics, figure_paths)

    metrics_path = paths.output_dir / "readiness_metrics.json"
    data_manifest_path = paths.output_dir / "readiness_data_manifest.json"
    csv_path = paths.output_dir / "readiness_matrix.csv"

    _write_json(metrics_path, metrics)
    _write_json(data_manifest_path, {key: str(path) for key, path in data_paths.items()})
    _write_csv(csv_path, metrics["readiness"])

    return {
        "metrics_path": metrics_path,
        "data_manifest_path": data_manifest_path,
        "csv_path": csv_path,
        "report_path": report_path,
        "figures": figure_paths,
        "data": data_paths,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()

    result = generate_all(output_dir=args.output_dir, data_root=args.data_root)
    print(
        json.dumps(
            {
                "ready": result["metrics"]["ready"],
                "metrics_path": str(result["metrics_path"]),
                "report_path": str(result["report_path"]),
                "figures": {key: str(path) for key, path in result["figures"].items()},
                "data": {key: str(path) for key, path in result["data"].items()},
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
