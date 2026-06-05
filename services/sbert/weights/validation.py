"""Validate local SentenceTransformer checkpoint artifacts.

The checks here are intentionally metadata-first so they can run in lightweight
test paths. Pass ``require_reload=True`` when a gate must prove the checkpoint
can be reloaded by ``sentence-transformers``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_SENTENCE_TRANSFORMERS = "config_sentence_transformers.json"
ARTIFACT_METADATA = "sbert_artifact_metadata.json"
MODULES_CONFIG = "modules.json"
TRANSFORMER_CONFIG = "config.json"
POOLING_CONFIG = Path("1_Pooling") / "config.json"


@dataclass(frozen=True)
class SBERTArtifactValidation:
    """Machine-readable result for SBERT checkpoint validation."""

    artifact_path: str
    artifact_name: str | None
    fine_tuned: bool
    base_model: str | None
    config_sentence_transformers: bool
    metadata_file: bool
    model_type: str | None
    similarity_fn_name: str | None
    embedding_dim: int | None
    dimension_sources: dict[str, int]
    reloadable: bool
    fallback_mode: bool
    fallback_reason: str | None
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors and not self.fallback_mode

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "artifact_name": self.artifact_name,
            "fine_tuned": self.fine_tuned,
            "base_model": self.base_model,
            "config_sentence_transformers": self.config_sentence_transformers,
            "metadata_file": self.metadata_file,
            "model_type": self.model_type,
            "similarity_fn_name": self.similarity_fn_name,
            "embedding_dim": self.embedding_dim,
            "dimension_sources": dict(self.dimension_sources),
            "reloadable": self.reloadable,
            "fallback_mode": self.fallback_mode,
            "fallback_reason": self.fallback_reason,
            "valid": self.valid,
            "errors": list(self.errors),
        }


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _dimension_from_json(path: Path, *keys: str) -> int | None:
    if not path.exists():
        return None
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return None
    for key in keys:
        dim = _positive_int(payload.get(key))
        if dim is not None:
            return dim
    return None


def collect_embedding_dimension_sources(model_dir: Path) -> dict[str, int]:
    """Collect deterministic embedding-dimension metadata from the artifact."""
    sources: dict[str, int] = {}
    metadata_dim = _dimension_from_json(
        model_dir / ARTIFACT_METADATA,
        "embedding_dim",
        "sentence_embedding_dimension",
    )
    if metadata_dim is not None:
        sources[ARTIFACT_METADATA] = metadata_dim

    pooling_dim = _dimension_from_json(
        model_dir / POOLING_CONFIG,
        "embedding_dimension",
        "word_embedding_dimension",
    )
    if pooling_dim is not None:
        sources[str(POOLING_CONFIG).replace("\\", "/")] = pooling_dim

    transformer_dim = _dimension_from_json(
        model_dir / TRANSFORMER_CONFIG,
        "hidden_size",
        "dim",
    )
    if transformer_dim is not None:
        sources[TRANSFORMER_CONFIG] = transformer_dim

    return sources


def _module_types(model_dir: Path) -> list[str]:
    modules_path = model_dir / MODULES_CONFIG
    if not modules_path.exists():
        return []
    payload = _read_json(modules_path)
    if not isinstance(payload, list):
        return []
    return [
        str(item.get("type", ""))
        for item in payload
        if isinstance(item, dict) and item.get("type")
    ]


def validate_sbert_artifact(
    model_dir: Path | str,
    *,
    expected_embedding_dim: int | None = None,
    require_metadata: bool = True,
    require_reload: bool = False,
) -> SBERTArtifactValidation:
    """Validate a local SentenceTransformer checkpoint directory."""
    path = Path(model_dir)
    errors: list[str] = []
    config_payload: dict[str, Any] = {}
    metadata_file = (path / ARTIFACT_METADATA).exists()
    metadata_payload = _read_json_object(path / ARTIFACT_METADATA)
    training_metadata = _read_json_object(path.parent / "artifacts" / "finetune_metadata.json")
    config_file = path / CONFIG_SENTENCE_TRANSFORMERS

    if not path.exists():
        errors.append("artifact directory does not exist")
    elif not path.is_dir():
        errors.append("artifact path is not a directory")

    if not config_file.exists():
        errors.append(f"missing {CONFIG_SENTENCE_TRANSFORMERS}")
    else:
        payload = _read_json(config_file)
        if isinstance(payload, dict):
            config_payload = payload
        else:
            errors.append(f"{CONFIG_SENTENCE_TRANSFORMERS} must contain a JSON object")

    if require_metadata and not metadata_file:
        errors.append(f"missing {ARTIFACT_METADATA}")

    model_type = config_payload.get("model_type")
    similarity_fn_name = config_payload.get("similarity_fn_name")
    if config_payload and model_type != "SentenceTransformer":
        errors.append("model_type must be SentenceTransformer")
    if config_payload and similarity_fn_name != "cosine":
        errors.append("similarity_fn_name must be cosine")

    module_types = _module_types(path)
    if module_types:
        if not any(module_type.endswith(".Transformer") for module_type in module_types):
            errors.append("modules.json does not include a Transformer module")
        if not any(".pooling.Pooling" in module_type for module_type in module_types):
            errors.append("modules.json does not include a Pooling module")
    elif path.exists() and path.is_dir():
        errors.append(f"missing or invalid {MODULES_CONFIG}")

    dimension_sources = collect_embedding_dimension_sources(path)
    unique_dims = set(dimension_sources.values())
    embedding_dim = next(iter(unique_dims)) if len(unique_dims) == 1 else None
    if not dimension_sources:
        errors.append("missing embedding dimension metadata")
    elif embedding_dim is None:
        errors.append(f"inconsistent embedding dimension metadata: {dimension_sources}")
    elif expected_embedding_dim is not None and embedding_dim != expected_embedding_dim:
        errors.append(
            f"embedding dimension {embedding_dim} != expected {expected_embedding_dim}"
        )

    reloadable = False
    if require_reload and not errors:
        try:
            from transformers import AutoModel, AutoTokenizer

            AutoTokenizer.from_pretrained(str(path))
            model = AutoModel.from_pretrained(str(path))
            loaded_dim = _positive_int(getattr(model.config, "hidden_size", None))
            if loaded_dim is None:
                errors.append("reloaded model did not expose embedding dimension")
            elif embedding_dim is not None and loaded_dim != embedding_dim:
                errors.append(
                    f"reloaded embedding dimension {loaded_dim} != metadata {embedding_dim}"
                )
            else:
                reloadable = True
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            errors.append(f"reload failed: {exc}")
    elif not require_reload and not errors:
        reloadable = True

    fallback_reason = "; ".join(errors) if errors else None
    return SBERTArtifactValidation(
        artifact_path=str(path),
        artifact_name=(
            str(metadata_payload.get("artifact_name"))
            if metadata_payload.get("artifact_name")
            else None
        ),
        fine_tuned=bool(
            metadata_payload.get("artifact_name")
            or training_metadata.get("best_model_dir")
            or training_metadata.get("final_model_dir")
        ),
        base_model=(
            str(training_metadata.get("base_model"))
            if training_metadata.get("base_model")
            else None
        ),
        config_sentence_transformers=config_file.exists(),
        metadata_file=metadata_file,
        model_type=str(model_type) if model_type is not None else None,
        similarity_fn_name=str(similarity_fn_name)
        if similarity_fn_name is not None
        else None,
        embedding_dim=embedding_dim,
        dimension_sources=dimension_sources,
        reloadable=reloadable,
        fallback_mode=bool(errors),
        fallback_reason=fallback_reason,
        errors=tuple(errors),
    )
