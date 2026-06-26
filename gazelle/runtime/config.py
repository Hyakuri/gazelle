from dataclasses import dataclass
from typing import Optional

from gazelle.runtime.model_registry import get_model_spec


def validate_device_name(device: str) -> str:
    normalized = str(device).strip()
    if not normalized:
        raise ValueError(
            "Invalid device '{}'. Use auto, cpu, cuda, or cuda:<non-negative-index>.".format(device)
        )
    if normalized in ("auto", "cpu", "cuda"):
        return normalized
    if normalized.startswith("cuda:"):
        index = normalized[len("cuda:") :]
        if index and index.isascii() and index.isdigit():
            return normalized
    raise ValueError(
        "Invalid device '{}'. Use auto, cpu, cuda, or cuda:<non-negative-index>.".format(device)
    )


@dataclass(frozen=True)
class RuntimeConfig:
    """Validated CLI configuration for the Gazelle runtime."""

    model: str = "gazelle_dinov2_vitb14_inout"
    list_models: bool = False
    prepare_only: bool = False
    input_path: Optional[str] = None
    device: str = "auto"
    cache_dir: Optional[str] = None
    checkpoint: Optional[str] = None
    force_download: bool = False

    def validate(self) -> "RuntimeConfig":
        get_model_spec(self.model)
        object.__setattr__(self, "device", validate_device_name(self.device))
        return self

    @classmethod
    def from_args(cls, args) -> "RuntimeConfig":
        return cls(
            model=args.model,
            list_models=args.list_models,
            prepare_only=args.prepare_only,
            input_path=args.input,
            device=args.device,
            cache_dir=args.cache_dir,
            checkpoint=args.checkpoint,
            force_download=args.force_download,
        ).validate()
