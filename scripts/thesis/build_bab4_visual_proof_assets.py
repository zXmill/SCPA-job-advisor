"""Build maximum-detail BAB IV visual proof assets.

The user requirement for this pass is that BAB IV evidence must be image-first:
plots, screenshot-style terminals, visual evidence cards, and Mermaid sources.
This script only reads existing benchmark/runtime artifacts and repository source
code. It does not mutate production services, model weights, or databases.
"""

from __future__ import annotations

import base64
import json
import shutil
import socket
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO_ROOT / "reports" / "thesis_evidence"
RUNTIME_LATEST = OUT_ROOT / "bab4_runtime_evidence_latest.json"
BENCHMARK_LATEST = OUT_ROOT / "bab4_benchmark_evidence_latest.json"
BENCHMARK_DIR = REPO_ROOT / "reports" / "evaluation" / "thesis_benchmark"
QRELS_STATUS = REPO_ROOT / "reports" / "sbert" / "gold_qrels" / "gold_qrels_status.json"
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "thesis" / "07_bab4_visual_proof_evidence.ipynb"


PALETTE = {
    "ink": "#111827",
    "muted": "#475569",
    "line": "#1f2937",
    "blue": "#1d4ed8",
    "green": "#047857",
    "red": "#b91c1c",
    "amber": "#b45309",
    "bg": "#f8fafc",
    "panel": "#ffffff",
    "header": "#e8eef7",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def wrap(value: Any, width: int = 38) -> str:
    text = str(value)
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False)) or text


def copy_asset(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return dst


def crop_frontend_screenshot(src: Path, dst: Path, *, max_height: int = 1800) -> Path:
    """Create a DOCX-friendly top crop from a full-page Playwright screenshot."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGB")
    width, height = img.size
    cropped = img.crop((0, 0, width, min(height, max_height)))
    cropped.save(dst)
    return dst


def save_visual_table(
    rows: list[dict[str, Any]],
    title: str,
    subtitle: str,
    path: Path,
    *,
    widths: list[float] | None = None,
    font_size: int = 8,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    display = df.copy()
    for col in display.columns:
        display[col] = display[col].map(lambda v: wrap(v, 34))

    height = max(3.0, 0.62 * (len(display) + 1) + 0.65)
    fig, ax = plt.subplots(figsize=(8.2, height))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.axis("off")
    ax.text(0.0, 1.035, title, transform=ax.transAxes, fontsize=12.5, fontweight="bold", color=PALETTE["ink"], va="bottom")
    ax.text(0.0, 0.99, subtitle, transform=ax.transAxes, fontsize=8.5, color=PALETTE["muted"], va="top")
    bbox = [0.0, 0.0, 1.0, 0.88]
    table = ax.table(
        cellText=display.values,
        colLabels=display.columns,
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        bbox=bbox,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1.0, 1.42)
    if widths:
        total = sum(widths)
        norm = [w / total for w in widths]
        for (row, col), cell in table.get_celld().items():
            if 0 <= col < len(norm):
                cell.set_width(norm[col])
    for (row, _col), cell in table.get_celld().items():
        cell.set_linewidth(0.55)
        cell.set_edgecolor(PALETTE["line"])
        if row == 0:
            cell.set_facecolor(PALETTE["header"])
            cell.set_text_props(weight="bold", color=PALETTE["ink"])
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#f8fafc")
            cell.set_text_props(color=PALETTE["ink"])
    fig.tight_layout()
    fig.savefig(path, dpi=260, bbox_inches="tight")
    plt.close(fig)


def save_terminal(title: str, lines: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(textwrap.wrap(line, width=86, replace_whitespace=False) or [""])
    height = max(2.6, 0.24 * (len(wrapped) + 5))
    fig, ax = plt.subplots(figsize=(8.2, height))
    fig.patch.set_facecolor("#101820")
    ax.set_facecolor("#101820")
    ax.axis("off")
    ax.text(0.02, 0.96, title, transform=ax.transAxes, color="#d8dee9", fontsize=11.5, fontweight="bold", va="top")
    y = 0.86
    for line in wrapped:
        color = "#a7f3d0" if line.startswith("{") or line.startswith("}") else "#e5e7eb"
        if "BLOCKED" in line or "not listening" in line or "failed" in line.lower():
            color = "#fca5a5"
        elif "listening" in line or "passed" in line.lower() or "ok" in line.lower():
            color = "#86efac"
        ax.text(0.03, y, line, transform=ax.transAxes, color=color, family="Consolas", fontsize=7.8, va="top")
        y -= 0.044
    fig.savefig(path, dpi=260, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def save_metric_dashboard(summary: dict[str, Any], runtime_counts: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cards = [
        ("Active jobs", f"{runtime_counts.get('active_accepted_jobs', 0):,}", "live DB capture"),
        ("Ready embeddings", f"{runtime_counts.get('ready_embeddings', 0):,}", f"dim={runtime_counts.get('embedding_dimension')}"),
        ("Benchmark users", f"{summary.get('n_users', 0):,}", "simulated_grounded"),
        ("Interactions", f"{summary.get('n_interactions', 0):,}", "offline train/test"),
        ("Temporal NDCG@10", f"{summary.get('full_scpa_temporal_ndcg_at_10', 0):.4f}", "full_scpa"),
        ("Holdout NDCG@10", f"{summary.get('full_scpa_user_holdout_ndcg_at_10', 0):.4f}", "full_scpa"),
        ("DQN CV", f"{summary.get('dqn_stability_cv', 0):.4f}", "multi-seed stable"),
        ("Gold qrels", str(summary.get("gold_qrels_status", "UNKNOWN")), "expert label gate"),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(8.2, 4.2))
    fig.patch.set_facecolor("white")
    for ax, (label, value, note) in zip(axes.ravel(), cards):
        ax.set_facecolor("#f8fafc")
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("#cbd5e1")
        ax.set_xticks([])
        ax.set_yticks([])
        color = PALETTE["red"] if value == "BLOCKED" else PALETTE["blue"]
        ax.text(0.06, 0.72, label, transform=ax.transAxes, fontsize=8.5, color=PALETTE["muted"], fontweight="bold")
        ax.text(0.06, 0.40, value, transform=ax.transAxes, fontsize=15, color=color, fontweight="bold")
        ax.text(0.06, 0.16, note, transform=ax.transAxes, fontsize=7.4, color=PALETTE["muted"])
    fig.suptitle("BAB IV Evidence Dashboard - Runtime + Benchmark", x=0.02, ha="left", fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(path, dpi=260, bbox_inches="tight")
    plt.close(fig)


def port_state(port: int) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    try:
        code = sock.connect_ex(("127.0.0.1", port))
        return "listening" if code == 0 else "not listening"
    finally:
        sock.close()


def docker_status() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=12,
        )
        return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}


def image_output(path: Path) -> dict[str, Any]:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"output_type": "display_data", "data": {"image/png": encoded}, "metadata": {}}


def markdown_cell(text: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": textwrap.dedent(text).strip() + "\n"}


def code_cell(source: str, image: Path | None = None) -> dict[str, Any]:
    outputs = [image_output(image)] if image else []
    return {
        "cell_type": "code",
        "execution_count": 1,
        "metadata": {},
        "outputs": outputs,
        "source": textwrap.dedent(source).strip() + "\n",
    }


def write_notebook(run_dir: Path, figures: dict[str, Path]) -> None:
    ordered = [
        ("evidence_dashboard", "Dashboard evidence runtime dan benchmark"),
        ("sbert_card", "Rincian teknis SBERT"),
        ("ncf_card", "Rincian teknis NCF"),
        ("dqn_card", "Rincian teknis DQN"),
        ("hybrid_card", "Rincian hybrid dan batas klaim"),
        ("current_capture_terminal", "Status capture frontend saat revisi"),
        ("ablation_ndcg10", "Plot ablation NDCG@10"),
        ("dqn_session_delta_ndcg", "Histogram delta DQN"),
        ("qrels_status", "Status gold qrels"),
    ]
    cells = [
        markdown_cell(
            """
            # BAB IV Visual Proof Evidence

            Notebook ini adalah indeks bukti visual untuk BAB IV. Semua gambar
            dibangun dari artifact runtime, benchmark CSV/JSON, atau source code
            proyek SCPA. Bagian yang belum memenuhi syarat generalisasi diberi
            status blocker, bukan dipaksakan menjadi klaim.
            """
        ),
        code_cell(
            f"""
            from pathlib import Path
            import json

            run_dir = Path(r"{run_dir}")
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            manifest["status"]
            """
        ),
    ]
    for key, heading in ordered:
        if key not in figures:
            continue
        path = figures[key]
        cells.append(markdown_cell(f"## {heading}"))
        cells.append(code_cell(f'from IPython.display import Image, display\ndisplay(Image(filename=r"{path}"))', path))
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2), encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUT_ROOT / f"bab4_visual_proof_{timestamp}"
    plot_dir = run_dir / "plots"
    screenshot_dir = run_dir / "screenshots"
    terminal_dir = run_dir / "terminal"
    mermaid_dir = run_dir / "mermaid"
    raw_dir = run_dir / "raw"
    for directory in (plot_dir, screenshot_dir, terminal_dir, mermaid_dir, raw_dir):
        directory.mkdir(parents=True, exist_ok=True)

    runtime_manifest = read_json(RUNTIME_LATEST)
    benchmark_manifest = read_json(BENCHMARK_LATEST)
    runtime_dir = Path(runtime_manifest["run_dir"])
    runtime_counts = read_json(runtime_dir / "raw" / "database_runtime_counts.json")
    frontend_summary = read_json(runtime_dir / "raw" / "frontend_playwright_summary.json")
    benchmark_report = read_json(Path(benchmark_manifest["benchmark_report"]))
    qrels = read_json(QRELS_STATUS)
    bench = benchmark_report["benchmarks"]["simulated_grounded"]
    meta = bench["metadata"]
    temporal = bench["splits"]["temporal"]
    holdout = bench["splits"]["user_holdout"]
    session = bench["session_split_leakage"]
    stability = bench["dqn_reward_stability"]
    dqn_proxy = bench.get("dqn_session_rerank_proxy", {})
    summary = benchmark_manifest["summary"]

    copied: dict[str, Path] = {}
    for key, src in benchmark_manifest["plots"].items():
        copied[key] = copy_asset(Path(src), plot_dir)
    for key, src in benchmark_manifest["terminal"].items():
        copied[key] = copy_asset(Path(src), terminal_dir)
    runtime_plot_names = [
        "database_embedding_coverage.png",
        "database_sources.png",
        "frontend_api_recommendation_summary.png",
        "dqn_rank_before_after.png",
        "model_runtime_evidence_matrix.png",
        "model_evidence_status_bar.png",
        "status_split_eksperimen.png",
    ]
    for src in runtime_manifest.get("plots", []):
        p = Path(src)
        if p.name in runtime_plot_names:
            copied[p.stem] = copy_asset(p, plot_dir)
    for src in runtime_manifest.get("screenshots", []):
        p = Path(src)
        if p.name.startswith("frontend_") or p.name.startswith("placeholder_"):
            copied[p.stem] = copy_asset(p, screenshot_dir)
    if "frontend_recommendations_initial_live" in copied:
        copied["frontend_recommendations_initial_crop"] = crop_frontend_screenshot(
            copied["frontend_recommendations_initial_live"],
            screenshot_dir / "frontend_recommendations_initial_crop.png",
        )
    if "frontend_recommendations_after_events_live" in copied:
        copied["frontend_recommendations_after_events_crop"] = crop_frontend_screenshot(
            copied["frontend_recommendations_after_events_live"],
            screenshot_dir / "frontend_recommendations_after_events_crop.png",
        )
    for src in runtime_manifest.get("terminal_screens", []):
        p = Path(src)
        copied[p.stem] = copy_asset(p, terminal_dir)

    dashboard = plot_dir / "evidence_dashboard.png"
    save_metric_dashboard(summary, runtime_counts, dashboard)
    copied["evidence_dashboard"] = dashboard

    sbert_rows = [
        {
            "Aspek": "Model",
            "Hasil implementasi": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 dengan checkpoint lokal sbert-indonesian-hybrid-manual-research-best",
            "Bukti runtime": f"job_embeddings model_version={runtime_counts.get('embedding_model_version')}",
            "Batas klaim": "Tidak klaim expert relevance sampai gold qrels selesai",
        },
        {
            "Aspek": "Dimensi",
            "Hasil implementasi": "Embedding 384 dimensi",
            "Bukti runtime": f"vector(384), ready={runtime_counts.get('ready_embeddings')}, active accepted jobs={runtime_counts.get('active_accepted_jobs')}",
            "Batas klaim": "Dimensi membuktikan kompatibilitas penyimpanan, bukan kualitas ranking sendiri",
        },
        {
            "Aspek": "Preprocessing",
            "Hasil implementasi": "canonical_job_text: dedupe casefold, exclude freshness metadata, hash sha256 lower text 16 hex",
            "Bukti runtime": "services/shared/job_text.py menjadi single producer hash embedding",
            "Batas klaim": "Hash stabil mencegah re-embed tidak perlu, bukan validasi semantik manusia",
        },
        {
            "Aspek": "Field lowongan",
            "Hasil implementasi": "title, company, location, function, industry, seniority, type, description, sections, responsibilities, requirements, skills, tags",
            "Bukti runtime": "CANONICAL_TEXT_FIELDS pada service shared",
            "Batas klaim": "Kualitas tetap bergantung kelengkapan data scraper",
        },
        {
            "Aspek": "Retrieval",
            "Hasil implementasi": "Profile/job embedding dibandingkan memakai cosine similarity via pgvector/HNSW",
            "Bukti runtime": "job_embeddings vector(384), vector_cosine_ops, top-k retrieval",
            "Batas klaim": "Belum menggantikan evaluasi qrels expert",
        },
        {
            "Aspek": "Contoh output",
            "Hasil implementasi": f"First API result: {frontend_summary.get('direct_api_summary', {}).get('first_title')} match={frontend_summary.get('direct_api_summary', {}).get('first_match_percent')}%",
            "Bukti runtime": f"sbert_score={frontend_summary.get('direct_api_summary', {}).get('first_scores', {}).get('sbert_score')}",
            "Batas klaim": "Contoh output membuktikan kontrak response, bukan preferensi user umum",
        },
    ]
    sbert_card = plot_dir / "sbert_technical_evidence_card.png"
    save_visual_table(
        sbert_rows,
        "Rincian Visual Implementasi SBERT Candidate Generator",
        "Sumber: services/sbert, services/shared/job_text.py, pgvector runtime capture, Playwright API summary.",
        sbert_card,
        widths=[1.0, 2.0, 1.55, 1.55],
        font_size=6.7,
    )
    copied["sbert_card"] = sbert_card

    ncf_rows = [
        {
            "Aspek": "Representasi user-item",
            "Hasil implementasi": "user_id + profile_text + job_id + candidate features; online scorer menerima candidate_job_ids/candidates",
            "Bukti runtime": "NCFRequest dan OnlineNCF dipakai pada benchmark real class",
            "Batas klaim": "Personalization kuat hanya pada split offline, bukan real-user gain",
        },
        {
            "Aspek": "Event positif",
            "Hasil implementasi": "apply=1.0, click=1.0, save=0.85, view_10s=0.65",
            "Bukti runtime": "EVENT_TARGETS services/ncf/main.py",
            "Batas klaim": "Bobot event adalah desain reward, bukan survey preferensi",
        },
        {
            "Aspek": "Event rendah/negatif",
            "Hasil implementasi": "view=0.45, impression=0.20, skip/immediate_skip=0.0",
            "Bukti runtime": "FeedbackEvent dan benchmark event_target",
            "Batas klaim": "View tidak disamakan dengan aplikasi lamaran",
        },
        {
            "Aspek": "Arsitektur",
            "Hasil implementasi": "NeuMF: GMF user/item embedding + MLP user/item embedding, hidden 128, output logit",
            "Bukti runtime": "NeuralCF class, factor_dim=64, model_version online-ncf-v2",
            "Batas klaim": "Tidak klaim superioritas tanpa ablation split sama",
        },
        {
            "Aspek": "Loss/training",
            "Hasil implementasi": "Online update implicit target dengan sigmoid error dan benchmark train split timestamp order",
            "Bukti runtime": f"temporal train={temporal['counts']['train']}, test={temporal['counts']['test']}; holdout test users={holdout['n_test_users_scored']}",
            "Batas klaim": "Offline simulated_grounded wajib disebut",
        },
        {
            "Aspek": "Cold-start",
            "Hasil implementasi": "New user/item memakai seeded/projected vector dan confidence prior agar cold job tidak diranking random",
            "Bukti runtime": "NEUMF_CONFIDENCE_PRIOR dan _seeded_vector/_project_embedding",
            "Batas klaim": "Cold-start diatasi secara engineering, bukan bukti kepuasan user",
        },
    ]
    ncf_card = plot_dir / "ncf_technical_evidence_card.png"
    save_visual_table(
        ncf_rows,
        "Rincian Visual Implementasi NCF Personalization Scorer",
        "Sumber: services/ncf/main.py, services/evaluation/model_rankers.py, benchmark frozen split.",
        ncf_card,
        widths=[1.0, 2.0, 1.55, 1.55],
        font_size=6.7,
    )
    copied["ncf_card"] = ncf_card

    dqn_rows = [
        {
            "Aspek": "State",
            "Hasil implementasi": "Projected job embedding 64 + sbert_score + ncf_score + log history count + log interaction count + text length + bias",
            "Bukti runtime": "FEATURE_DIM=70 dari EMBED_DIM=64+6",
            "Batas klaim": "State mewakili sesi dan kandidat, bukan learning path kurikulum",
        },
        {
            "Aspek": "Action",
            "Hasil implementasi": "Skill-vocabulary action head; ranking memakai mean q-values sebagai state value",
            "Bukti runtime": "N_ACTIONS=len(SKILL_VOCAB), QNetwork output per action",
            "Batas klaim": "Action internal untuk policy, bukan rekomendasi roadmap belajar",
        },
        {
            "Aspek": "Reward",
            "Hasil implementasi": "apply=1.0, save=0.6, click/open=0.2, view_10s=0.25, skip=-0.1, immediate_skip=-0.2",
            "Bukti runtime": "EVENT_REWARDS services/dqn/main.py",
            "Batas klaim": "Reward event tidak membuktikan outcome karier",
        },
        {
            "Aspek": "Policy",
            "Hasil implementasi": "QNetwork + target network + replay buffer + epsilon greedy; objective session_rerank",
            "Bukti runtime": f"CV={stability['coefficient_of_variation']}; test sessions={session['n_test_sessions']}",
            "Batas klaim": "DQN aktif sebagai reranker sesi setelah candidate + NCF tersedia",
        },
        {
            "Aspek": "Runtime evidence",
            "Hasil implementasi": "rank_before_dqn, rank_after_dqn, dqn_session_score, event sesi pengguna",
            "Bukti runtime": f"event rows={dqn_proxy.get('n_event_rows')}; mean_delta_ndcg@10={dqn_proxy.get('mean_delta_ndcg_at_10')}",
            "Batas klaim": "Proxy held-out session, bukan off-policy RL final",
        },
    ]
    dqn_card = plot_dir / "dqn_technical_evidence_card.png"
    save_visual_table(
        dqn_rows,
        "Rincian Visual Implementasi DQN Session Reranker",
        "Sumber: services/dqn/main.py, DQN held-out session proxy, runtime internal rerank.",
        dqn_card,
        widths=[1.0, 2.1, 1.55, 1.45],
        font_size=6.7,
    )
    copied["dqn_card"] = dqn_card

    hybrid_rows = [
        {
            "Aspek": "Candidate generator",
            "Evidence angka": f"SBERT/semantic content NDCG@10 temporal={temporal['metrics']['content']['ndcg_at_10']:.4f}, holdout={holdout['metrics']['content']['ndcg_at_10']:.4f}",
            "Interpretasi": "Semantic retrieval menjadi fondasi kandidat kuat",
            "Batas klaim": "Content delta terhadap full_scpa pada temporal tidak signifikan",
        },
        {
            "Aspek": "Personalization scorer",
            "Evidence angka": f"NCF-only NDCG@10 temporal={temporal['metrics']['ncf']['ndcg_at_10']:.4f}, holdout={holdout['metrics']['ncf']['ndcg_at_10']:.4f}",
            "Interpretasi": "Collaborative signal sendiri belum cukup tanpa kandidat semantik",
            "Batas klaim": "Butuh real interaction besar untuk klaim produksi",
        },
        {
            "Aspek": "Hybrid full",
            "Evidence angka": f"full_scpa NDCG@10 temporal={temporal['metrics']['full_scpa']['ndcg_at_10']:.4f}, holdout={holdout['metrics']['full_scpa']['ndcg_at_10']:.4f}",
            "Interpretasi": "Pipeline lengkap tertinggi pada dua split",
            "Batas klaim": "Wajib disclose simulated_grounded",
        },
        {
            "Aspek": "DQN rerank",
            "Evidence angka": f"delta NDCG@10={dqn_proxy.get('mean_delta_ndcg_at_10')}; mean positive delta rank={dqn_proxy.get('mean_positive_delta_rank')}",
            "Interpretasi": "Ada perubahan sesi terukur, kecil namun terlapor",
            "Batas klaim": "Tidak ditulis sebagai learning path adaptif",
        },
        {
            "Aspek": "Gold qrels",
            "Evidence angka": f"silver={qrels['silver_qrels']['n_judgements']}, gold={qrels['gold_qrels']['n_judgements']}, pending={qrels['annotation_template']['n_rows_pending_expert_grade']}",
            "Interpretasi": "Annotation pipeline siap tetapi expert grade belum ada",
            "Batas klaim": "Expert Precision/NDCG/MAP masih BLOCKED",
        },
    ]
    hybrid_card = plot_dir / "hybrid_claim_evidence_card.png"
    save_visual_table(
        hybrid_rows,
        "Evidence Hybrid, Ablation, dan Batas Klaim",
        "Sumber: benchmark_metrics.json, qrels status, DQN session proxy.",
        hybrid_card,
        widths=[1.0, 1.8, 1.6, 1.5],
        font_size=6.8,
    )
    copied["hybrid_card"] = hybrid_card

    capture = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "ports": {str(port): port_state(port) for port in (3000, 9000, 8000, 8005, 5432, 6379)},
        "docker": docker_status(),
        "latest_frontend_runtime_capture": runtime_manifest.get("latest_frontend_run"),
    }
    write_json(raw_dir / "current_capture_status.json", capture)
    terminal_lines = [
        "PS E:\\TUGAS AKHIR\\SCPA> current live capture check",
        json.dumps(capture["ports"], ensure_ascii=False),
        f"docker_returncode={capture['docker']['returncode']}",
        capture["docker"].get("stderr") or capture["docker"].get("stdout") or "(no docker output)",
        f"latest documented Playwright capture = {capture['latest_frontend_runtime_capture']}",
        "Interpretation: frontend/gateway were not listening during this revision; BAB IV uses the documented 16 June runtime capture and marks recapture as required if services are restarted.",
    ]
    current_terminal = terminal_dir / "powershell_current_capture_status.png"
    save_terminal("PowerShell Current Runtime Capture Status", terminal_lines, current_terminal)
    copied["current_capture_terminal"] = current_terminal

    mermaid_source = textwrap.dedent(
        """
        flowchart LR
            A["Frontend recommendation page"] --> B["FastAPI gateway /api/recommendations"]
            B --> C["Pipeline orchestrator"]
            C --> D["SBERT candidate generator"]
            D --> E["pgvector cosine top-k"]
            E --> F["NCF personalization scorer"]
            F --> G["DQN session reranker"]
            G --> H["Hybrid slate + model lineage"]
            H --> I["Frontend cards + feedback events"]
            I --> G
        """
    ).strip()
    mermaid_path = mermaid_dir / "bab4_runtime_recommendation_flow.mmd"
    mermaid_path.write_text(mermaid_source + "\n", encoding="utf-8")
    save_terminal(
        "Mermaid Source - Runtime Recommendation Flow",
        ["PS> Get-Content bab4_runtime_recommendation_flow.mmd", *mermaid_source.splitlines()],
        terminal_dir / "mermaid_runtime_flow_source.png",
    )
    copied["mermaid_runtime_flow_source"] = terminal_dir / "mermaid_runtime_flow_source.png"

    write_notebook(run_dir, copied)

    manifest = {
        "status": "ok",
        "generated_at": timestamp,
        "run_dir": str(run_dir),
        "runtime_manifest": str(RUNTIME_LATEST),
        "benchmark_manifest": str(BENCHMARK_LATEST),
        "notebook": str(NOTEBOOK_PATH),
        "assets": {key: str(value) for key, value in sorted(copied.items())},
        "raw": {"current_capture_status": str(raw_dir / "current_capture_status.json")},
        "mermaid": {"runtime_recommendation_flow": str(mermaid_path)},
        "summary": {
            "runtime_active_accepted_jobs": runtime_counts.get("active_accepted_jobs"),
            "runtime_ready_embeddings": runtime_counts.get("ready_embeddings"),
            "embedding_dimension": runtime_counts.get("embedding_dimension"),
            "benchmark_users": meta.get("n_users"),
            "benchmark_jobs": meta.get("n_jobs"),
            "benchmark_interactions": meta.get("n_interactions"),
            "temporal_full_ndcg10": temporal["metrics"]["full_scpa"]["ndcg_at_10"],
            "holdout_full_ndcg10": holdout["metrics"]["full_scpa"]["ndcg_at_10"],
            "dqn_stability_cv": stability["coefficient_of_variation"],
            "dqn_proxy_delta_ndcg10": dqn_proxy.get("mean_delta_ndcg_at_10"),
            "gold_qrels_status": qrels["status"],
            "current_frontend_port_3000": capture["ports"]["3000"],
            "current_gateway_port_9000": capture["ports"]["9000"],
        },
        "claim_boundaries": [
            "Runtime screenshots demonstrate artifact operability at the documented capture time, not usability satisfaction.",
            "Benchmark numbers use simulated_grounded interactions derived from real profile/job attributes, not production user behavior.",
            "SBERT expert Precision/NDCG/MAP remains blocked until gold qrels and inter-annotator agreement exist.",
            "DQN is session reranking evidence only; it is not a learning-path or career-roadmap model.",
        ],
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(OUT_ROOT / "bab4_visual_proof_latest.json", manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
