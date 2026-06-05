"""Bootstrap local ML weight directories for SCPA services.

Model artifacts are intentionally not committed. This script creates local
weight directories and writes initial checkpoints so Docker volume mounts have
the expected files. SBERT can optionally be pulled from HuggingFace when
sentence-transformers is installed locally.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SBERT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def ensure_weight_dirs(root: Path = REPO_ROOT) -> dict[str, Path]:
    """Create service weight directories and return their paths."""
    dirs = {
        "sbert": root / "services" / "sbert" / "weights" / "fine_tuned",
        "ncf": root / "services" / "ncf" / "weights",
        "dqn": root / "services" / "dqn" / "weights",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def bootstrap_ncf(weights_dir: Path) -> dict[str, Any]:
    """Save an initialized NCF state_dict checkpoint."""
    import torch

    from services.ncf.main import NeuralCF

    model = NeuralCF(num_users=10_000, num_items=50_000, embedding_dim=64)
    output_path = weights_dir / "ncf_model.pt"
    torch.save(model.state_dict(), output_path)
    return {"status": "created", "path": str(output_path)}


def bootstrap_dqn(weights_dir: Path) -> dict[str, Any]:
    """Save an initialized DQN Q-network state_dict checkpoint."""
    import torch

    from services.dqn.main import N_ACTIONS, QNetwork, ROLE_VOCAB, SKILL_VOCAB

    state_dim = len(SKILL_VOCAB) + 32 + len(ROLE_VOCAB)
    model = QNetwork(state_dim=state_dim, n_actions=N_ACTIONS)
    output_path = weights_dir / "dqn_model.pt"
    torch.save(model.state_dict(), output_path)
    return {"status": "created", "path": str(output_path)}


def bootstrap_sbert(
    weights_dir: Path,
    model_name: str = DEFAULT_SBERT_MODEL,
    skip_if_missing: bool = False,
) -> dict[str, Any]:
    """Pull and save an SBERT model locally."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        if skip_if_missing:
            return {"status": "skipped", "reason": str(exc)}
        raise

    model = SentenceTransformer(model_name)
    model.save_pretrained(str(weights_dir))
    return {"status": "created", "path": str(weights_dir), "model": model_name}


def bootstrap_all(
    root: Path = REPO_ROOT,
    sbert_model: str = DEFAULT_SBERT_MODEL,
    skip_sbert: bool = False,
) -> dict[str, Any]:
    """Bootstrap all local service weight directories."""
    dirs = ensure_weight_dirs(root)
    result = {
        "ncf": bootstrap_ncf(dirs["ncf"]),
        "dqn": bootstrap_dqn(dirs["dqn"]),
        "sbert": (
            {"status": "skipped", "reason": "--skip-sbert"}
            if skip_sbert
            else bootstrap_sbert(dirs["sbert"], sbert_model, skip_if_missing=True)
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--sbert-model", default=DEFAULT_SBERT_MODEL)
    parser.add_argument(
        "--skip-sbert",
        action="store_true",
        help="Create NCF/DQN checkpoints without pulling SBERT.",
    )
    args = parser.parse_args()

    result = bootstrap_all(
        root=args.root,
        sbert_model=args.sbert_model,
        skip_sbert=args.skip_sbert,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
