"""CLI wrapper for retraining the SCPA local ML artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.retrain_models import run_retraining
from scripts.sample_dataset import DEFAULT_SAMPLE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrain SCPA SBERT, NCF, and DQN smoke artifacts.")
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "reports" / "retraining_artifacts")
    parser.add_argument("--steps", type=int, default=4)
    args = parser.parse_args()

    result = run_retraining(args.sample_dir, args.output_dir, steps=args.steps)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"ok", "check"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
