import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Tuple

import torch

from gazelle.runtime.environment import temporarily_disable_xformers
from gazelle.runtime.model_registry import CheckpointCandidate, ModelSpec, get_model_spec


@dataclass(frozen=True)
class RuntimeCachePaths:
    root_dir: Path
    checkpoints_dir: Path
    torch_hub_dir: Path


@dataclass(frozen=True)
class CandidateValidationResult:
    candidate: CheckpointCandidate
    checkpoint_path: Path
    size_bytes: Optional[int]
    sha256: Optional[str]
    top_level_type: Optional[str]
    strict_load_success: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class PreparedResources:
    model_name: str
    checkpoint_path: Path
    cache_paths: RuntimeCachePaths
    checkpoint_candidate: Optional[CheckpointCandidate]
    candidate_results: Tuple[CandidateValidationResult, ...]


def resolve_cache_paths(cache_dir: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> RuntimeCachePaths:
    env = os.environ if env is None else env
    root = Path(cache_dir or env.get("GAZELLE_CACHE_DIR") or "models")
    return RuntimeCachePaths(
        root_dir=root,
        checkpoints_dir=root / "checkpoints",
        torch_hub_dir=root / "torch_hub",
    )


def ensure_cache_dirs(paths: RuntimeCachePaths) -> None:
    paths.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    paths.torch_hub_dir.mkdir(parents=True, exist_ok=True)


def ensure_checkpoint(
    candidate: CheckpointCandidate,
    paths: RuntimeCachePaths,
    force_download: bool = False,
    downloader: Optional[Callable[..., object]] = None,
) -> Path:
    ensure_cache_dirs(paths)
    checkpoint_path = paths.checkpoints_dir / candidate.filename
    if checkpoint_path.exists() and not force_download:
        return checkpoint_path

    downloader = torch.hub.load_state_dict_from_url if downloader is None else downloader
    temp_dir = paths.checkpoints_dir / ".downloads" / candidate.filename
    temp_checkpoint_path = temp_dir / candidate.filename
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            downloader(
                candidate.url,
                model_dir=str(temp_dir),
                file_name=candidate.filename,
                progress=True,
                weights_only=True,
            )
        except Exception as exc:
            if checkpoint_path.exists():
                raise RuntimeError(
                    "Failed to download checkpoint from {} to {}; existing cached checkpoint "
                    "was preserved at {}: {}".format(
                        candidate.url,
                        checkpoint_path,
                        checkpoint_path,
                        exc,
                    )
                )
            raise RuntimeError(
                "Failed to download checkpoint from {} to {}: {}".format(
                    candidate.url,
                    checkpoint_path,
                    exc,
                )
            )
        if not temp_checkpoint_path.exists():
            raise RuntimeError(
                "Checkpoint download completed but file was not found: {}".format(
                    temp_checkpoint_path
                )
            )
        temp_checkpoint_path.replace(checkpoint_path)
        if not checkpoint_path.exists():
            raise RuntimeError(
                "Checkpoint download completed but file was not found: {}".format(
                    checkpoint_path
                )
            )
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    return checkpoint_path


def _unwrap_state_dict(checkpoint_obj: object) -> Dict[str, torch.Tensor]:
    if isinstance(checkpoint_obj, dict) and "state_dict" in checkpoint_obj:
        checkpoint_obj = checkpoint_obj["state_dict"]
    if not isinstance(checkpoint_obj, dict):
        raise ValueError(
            "Checkpoint must be a state dict or contain a 'state_dict' mapping; got {}".format(
                type(checkpoint_obj).__name__
            )
        )
    if not checkpoint_obj:
        raise ValueError("Checkpoint state dict is empty")
    return dict(checkpoint_obj)


def load_checkpoint_state_dict(
    checkpoint_path: Path,
    torch_load: Optional[Callable[..., object]] = None,
) -> Tuple[Dict[str, torch.Tensor], str]:
    torch_load = torch.load if torch_load is None else torch_load
    try:
        checkpoint_obj = torch_load(str(checkpoint_path), map_location="cpu", weights_only=True)
    except TypeError:
        checkpoint_obj = torch_load(str(checkpoint_path), map_location="cpu")
    top_level_type = type(checkpoint_obj).__name__
    return _unwrap_state_dict(checkpoint_obj), top_level_type


def expected_gazelle_state_dict(model, include_backbone: bool = False) -> Dict[str, torch.Tensor]:
    if hasattr(model, "get_gazelle_state_dict"):
        return dict(model.get_gazelle_state_dict(include_backbone=include_backbone))
    state_dict = model.state_dict()
    if include_backbone:
        return dict(state_dict)
    return {key: value for key, value in state_dict.items() if not key.startswith("backbone")}


def validate_gazelle_state_dict(
    model,
    checkpoint_state_dict: Mapping[str, object],
    include_backbone: bool = False,
) -> Dict[str, torch.Tensor]:
    state_dict = _unwrap_state_dict(dict(checkpoint_state_dict))
    expected = expected_gazelle_state_dict(model, include_backbone=include_backbone)
    if not expected:
        raise ValueError("Expected Gazelle model state dict is empty")

    non_tensor_keys = [key for key, value in state_dict.items() if not torch.is_tensor(value)]
    if non_tensor_keys:
        raise ValueError("Checkpoint contains non-tensor values for keys: {}".format(sorted(non_tensor_keys)))

    expected_keys = set(expected.keys())
    actual_keys = set(state_dict.keys())
    missing = sorted(expected_keys - actual_keys)
    unexpected = sorted(actual_keys - expected_keys)
    if missing:
        raise ValueError("Checkpoint missing keys: {}".format(missing))
    if unexpected:
        raise ValueError("Checkpoint has unexpected keys: {}".format(unexpected))

    shape_mismatches = []
    for key in sorted(expected_keys):
        if tuple(state_dict[key].shape) != tuple(expected[key].shape):
            shape_mismatches.append(
                "{} expected {} got {}".format(
                    key,
                    tuple(expected[key].shape),
                    tuple(state_dict[key].shape),
                )
            )
    if shape_mismatches:
        raise ValueError("Checkpoint tensor shape mismatch: {}".format(shape_mismatches))
    return dict(state_dict)


def load_strict_gazelle_checkpoint(model, checkpoint_state_dict: Mapping[str, object]) -> None:
    validated = validate_gazelle_state_dict(model, checkpoint_state_dict, include_backbone=False)
    current = dict(model.state_dict())
    current.update(validated)
    model.load_state_dict(current, strict=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_candidate(
    candidate: CheckpointCandidate,
    model,
    paths: RuntimeCachePaths,
    force_download: bool,
) -> Tuple[CandidateValidationResult, Optional[Dict[str, torch.Tensor]]]:
    checkpoint_path = paths.checkpoints_dir / candidate.filename
    try:
        checkpoint_path = ensure_checkpoint(candidate, paths, force_download=force_download)
        state_dict, top_level_type = load_checkpoint_state_dict(checkpoint_path)
        validated = validate_gazelle_state_dict(model, state_dict)
        return (
            CandidateValidationResult(
                candidate=candidate,
                checkpoint_path=checkpoint_path,
                size_bytes=checkpoint_path.stat().st_size,
                sha256=file_sha256(checkpoint_path),
                top_level_type=top_level_type,
                strict_load_success=True,
            ),
            validated,
        )
    except Exception as exc:
        return (
            CandidateValidationResult(
                candidate=candidate,
                checkpoint_path=checkpoint_path,
                size_bytes=checkpoint_path.stat().st_size if checkpoint_path.exists() else None,
                sha256=file_sha256(checkpoint_path) if checkpoint_path.exists() else None,
                top_level_type=None,
                strict_load_success=False,
                error=str(exc),
            ),
            None,
        )


def _state_dicts_equivalent(first: Mapping[str, torch.Tensor], second: Mapping[str, torch.Tensor]) -> bool:
    if set(first.keys()) != set(second.keys()):
        return False
    for key in first:
        if tuple(first[key].shape) != tuple(second[key].shape):
            return False
        if not torch.equal(first[key].cpu(), second[key].cpu()):
            return False
    return True


def resolve_checkpoint_candidate(
    spec: ModelSpec,
    model,
    paths: RuntimeCachePaths,
    force_download: bool = False,
) -> Tuple[CheckpointCandidate, Path, Tuple[CandidateValidationResult, ...]]:
    if not spec.checkpoint_candidates:
        raise ValueError("No checkpoint candidates registered for {}".format(spec.name))

    results = []
    valid_state_dicts = []
    for candidate in spec.checkpoint_candidates:
        result, validated_state_dict = _validate_candidate(candidate, model, paths, force_download=force_download)
        results.append(result)
        if validated_state_dict is not None:
            valid_state_dicts.append((candidate, result.checkpoint_path, validated_state_dict))

    if len(valid_state_dicts) == 1:
        candidate, checkpoint_path, _ = valid_state_dicts[0]
        return candidate, checkpoint_path, tuple(results)
    if not valid_state_dicts:
        errors = ["{}: {}".format(result.candidate.filename, result.error) for result in results]
        raise RuntimeError(
            "No checkpoint candidate can be strictly loaded for {}. {}".format(spec.name, "; ".join(errors))
        )

    first_candidate, first_path, first_state_dict = valid_state_dicts[0]
    all_equivalent = all(
        _state_dicts_equivalent(first_state_dict, state_dict)
        for _, _, state_dict in valid_state_dicts[1:]
    )
    if all_equivalent:
        for candidate, checkpoint_path, _ in valid_state_dicts:
            if candidate.source == "README":
                return candidate, checkpoint_path, tuple(results)
        return first_candidate, first_path, tuple(results)

    raise RuntimeError(
        "Multiple checkpoint candidates strictly load for {}, but their tensor contents differ. "
        "Pass --checkpoint to select one explicitly.".format(spec.name)
    )


def prepare_runtime_resources(config) -> PreparedResources:
    spec = get_model_spec(config.model)
    paths = resolve_cache_paths(config.cache_dir)

    if config.checkpoint:
        checkpoint_path = Path(config.checkpoint)
        if not checkpoint_path.exists():
            raise FileNotFoundError("Checkpoint does not exist: {}".format(checkpoint_path))
    else:
        checkpoint_path = None

    ensure_cache_dirs(paths)
    torch.hub.set_dir(str(paths.torch_hub_dir))

    with temporarily_disable_xformers():
        from gazelle.model import get_gazelle_model

        model, _ = get_gazelle_model(spec.name)

    if checkpoint_path is not None:
        state_dict, _ = load_checkpoint_state_dict(checkpoint_path)
        load_strict_gazelle_checkpoint(model, state_dict)
        return PreparedResources(
            model_name=spec.name,
            checkpoint_path=checkpoint_path,
            cache_paths=paths,
            checkpoint_candidate=None,
            candidate_results=(),
        )

    candidate, checkpoint_path, candidate_results = resolve_checkpoint_candidate(
        spec,
        model,
        paths,
        force_download=config.force_download,
    )
    state_dict, _ = load_checkpoint_state_dict(checkpoint_path)
    load_strict_gazelle_checkpoint(model, state_dict)
    return PreparedResources(
        model_name=spec.name,
        checkpoint_path=checkpoint_path,
        cache_paths=paths,
        checkpoint_candidate=candidate,
        candidate_results=candidate_results,
    )
