from dataclasses import dataclass
from typing import Optional

from gazelle.runtime.model_registry import get_model_spec


@dataclass(frozen=True)
class RuntimeConfig:
    """Validated CLI configuration for the Gazelle runtime."""

    model: str = "gazelle_dinov2_vitb14_inout"
    list_models: bool = False
    input_path: Optional[str] = None
    device: str = "auto"

    def validate(self) -> "RuntimeConfig":
        get_model_spec(self.model)
        if self.device not in ("auto", "cpu", "cuda") and not self.device.startswith("cuda:"):
            raise ValueError("Invalid device '{}'. Use auto, cpu, cuda, or cuda:<index>.".format(self.device))
        return self

    @classmethod
    def from_args(cls, args) -> "RuntimeConfig":
        return cls(
            model=args.model,
            list_models=args.list_models,
            input_path=args.input,
            device=args.device,
        ).validate()
