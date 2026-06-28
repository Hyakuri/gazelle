from dataclasses import dataclass
from typing import Optional, Tuple

from gazelle.runtime.contracts import BBox

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
    output_dir: str = "outputs"
    overwrite: bool = False
    head_source: str = "none"
    bboxes: Tuple[BBox, ...] = ()
    bbox_format: str = "normalized"
    person_ids: Optional[Tuple[int, ...]] = None
    head_data: Optional[str] = None
    save_heatmaps: bool = False
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
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            head_source=args.head_source,
            bboxes=tuple(tuple(bbox) for bbox in (args.bbox or ())),
            bbox_format=args.bbox_format,
            person_ids=None if args.person_id is None else tuple(args.person_id),
            head_data=args.head_data,
            save_heatmaps=args.save_heatmaps,
            device=args.device,
            cache_dir=args.cache_dir,
            checkpoint=args.checkpoint,
            force_download=args.force_download,
        ).validate()
