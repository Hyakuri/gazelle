from dataclasses import dataclass
import math
from numbers import Real
from pathlib import Path
from typing import Optional, Tuple

from gazelle.runtime.contracts import BBox

from gazelle.runtime.model_registry import get_model_spec


SUPPORTED_RENDERED_SUFFIXES = (".png", ".jpg", ".jpeg")


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


def validate_rendered_name(rendered_name: str) -> str:
    name = str(rendered_name).strip()
    if not name:
        raise ValueError("rendered_name must not be empty")
    if "/" in name or "\\" in name or Path(name).name != name:
        raise ValueError("rendered_name must be a file name, not a path")
    if Path(name).suffix.lower() not in SUPPORTED_RENDERED_SUFFIXES:
        raise ValueError(
            "rendered_name must end with one of: {}".format(
                ", ".join(SUPPORTED_RENDERED_SUFFIXES)
            )
        )
    return name


def validate_heatmap_alpha(heatmap_alpha) -> float:
    if (
        not isinstance(heatmap_alpha, Real)
        or isinstance(heatmap_alpha, bool)
        or not math.isfinite(float(heatmap_alpha))
    ):
        raise ValueError("heatmap_alpha must be a finite real number")
    alpha = float(heatmap_alpha)
    if alpha < 0.0 or alpha > 1.0:
        raise ValueError("heatmap_alpha must be between 0.0 and 1.0")
    return alpha


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
    save_rendered: bool = False
    rendered_name: str = "rendered.png"
    heatmap_alpha: float = 0.45
    draw_head_box: bool = True
    draw_gaze_peak: bool = True
    draw_labels: bool = True
    device: str = "auto"
    cache_dir: Optional[str] = None
    checkpoint: Optional[str] = None
    force_download: bool = False

    def validate(self) -> "RuntimeConfig":
        get_model_spec(self.model)
        object.__setattr__(self, "device", validate_device_name(self.device))
        object.__setattr__(self, "rendered_name", validate_rendered_name(self.rendered_name))
        object.__setattr__(self, "heatmap_alpha", validate_heatmap_alpha(self.heatmap_alpha))
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
            save_rendered=args.save_rendered,
            rendered_name=args.rendered_name,
            heatmap_alpha=args.heatmap_alpha,
            draw_head_box=not args.no_head_box,
            draw_gaze_peak=not args.no_gaze_peak,
            draw_labels=not args.no_labels,
            device=args.device,
            cache_dir=args.cache_dir,
            checkpoint=args.checkpoint,
            force_download=args.force_download,
        ).validate()
