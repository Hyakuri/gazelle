from dataclasses import dataclass
import math
from numbers import Real
from pathlib import Path
from typing import Optional, Tuple

from gazelle.runtime.contracts import BBox

from gazelle.runtime.model_registry import get_model_spec


SUPPORTED_RENDERED_SUFFIXES = (".png", ".jpg", ".jpeg")
SUPPORTED_VIDEO_OUTPUT_SUFFIXES = (".mp4",)
SUPPORTED_VIDEO_CODECS = ("mp4v", "avc1")
SUPPORTED_POSE_MODELS = ("lite", "full", "heavy")
SUPPORTED_GAZELLE_HEAD_MODE_SELECTORS = (
    "eligible",
    "observed",
    "all",
    "face_pose",
    "face_only",
    "pose_only",
    "tracked_only",
    "frontal",
    "profile",
    "back_or_occluded",
    "unknown",
)
SUPPORTED_GAZE_RENDER_MODES = ("valid-only", "all-predictions")


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


def validate_heatmap_contour_quantile(heatmap_contour_quantile) -> float:
    if (
        not isinstance(heatmap_contour_quantile, Real)
        or isinstance(heatmap_contour_quantile, bool)
        or not math.isfinite(float(heatmap_contour_quantile))
    ):
        raise ValueError("heatmap_contour_quantile must be a finite real number")
    quantile = float(heatmap_contour_quantile)
    if quantile < 0.0 or quantile > 1.0:
        raise ValueError("heatmap_contour_quantile must be between 0.0 and 1.0")
    return quantile


def validate_unit_interval(value, field_name: str) -> float:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise ValueError("{} must be a finite real number".format(field_name))
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError("{} must be between 0.0 and 1.0".format(field_name))
    return value


def validate_optional_positive_int(value, field_name: str):
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("{} must be a positive int".format(field_name))
    return value


def validate_optional_positive_float(value, field_name: str):
    if value is None:
        return None
    if not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError("{} must be a finite positive real number".format(field_name))
    value = float(value)
    if value <= 0.0:
        raise ValueError("{} must be greater than 0".format(field_name))
    return value


def validate_positive_int(value, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("{} must be an int greater than or equal to 1".format(field_name))
    return value


def validate_max_heads(max_heads) -> int:
    if not isinstance(max_heads, int) or isinstance(max_heads, bool) or not 1 <= max_heads <= 10:
        raise ValueError("max_heads must be an int between 1 and 10")
    return max_heads


def validate_pose_model(pose_model: str) -> str:
    if pose_model not in SUPPORTED_POSE_MODELS:
        raise ValueError("pose_model must be one of: {}".format(", ".join(SUPPORTED_POSE_MODELS)))
    return pose_model


def validate_positive_finite_float(value, field_name: str = "value") -> float:
    if not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError("{} must be a finite positive real number".format(field_name))
    value = float(value)
    if value <= 0.0:
        raise ValueError("{} must be greater than 0".format(field_name))
    return value


def validate_output_video_name(output_video_name: str) -> str:
    name = str(output_video_name).strip()
    if not name:
        raise ValueError("output_video_name must not be empty")
    if "/" in name or "\\" in name or Path(name).name != name:
        raise ValueError("output_video_name must be a file name, not a path")
    if Path(name).suffix.lower() not in SUPPORTED_VIDEO_OUTPUT_SUFFIXES:
        raise ValueError("output_video_name must end with .mp4")
    return name


def validate_video_codec(video_codec: str) -> str:
    codec = str(video_codec).strip().lower()
    if codec not in SUPPORTED_VIDEO_CODECS:
        raise ValueError(
            "video_codec must be one of: {}".format(
                ", ".join(SUPPORTED_VIDEO_CODECS)
            )
        )
    return codec


def validate_gazelle_head_mode(value) -> Tuple[str, ...]:
    if isinstance(value, bool):
        raise ValueError("gazelle_head_mode must contain one or more string selectors")
    if isinstance(value, str):
        selectors = (value,)
    else:
        try:
            selectors = tuple(value)
        except TypeError as exc:
            raise ValueError(
                "gazelle_head_mode must contain one or more string selectors"
            ) from exc
    if not selectors:
        raise ValueError("gazelle_head_mode must contain at least one selector")

    normalized = []
    for selector in selectors:
        if not isinstance(selector, str):
            raise ValueError("gazelle_head_mode selectors must be strings")
        selector = selector.strip()
        if selector not in SUPPORTED_GAZELLE_HEAD_MODE_SELECTORS:
            raise ValueError(
                "gazelle_head_mode selector must be one of: {}".format(
                    ", ".join(SUPPORTED_GAZELLE_HEAD_MODE_SELECTORS)
                )
            )
        if selector not in normalized:
            normalized.append(selector)

    if "all" in normalized:
        return ("all",)
    return tuple(normalized)


def validate_gaze_render_mode(value) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "gaze_render_mode must be one of: {}".format(
                ", ".join(SUPPORTED_GAZE_RENDER_MODES)
            )
        )
    mode = value.strip()
    if mode not in SUPPORTED_GAZE_RENDER_MODES:
        raise ValueError(
            "gaze_render_mode must be one of: {}".format(
                ", ".join(SUPPORTED_GAZE_RENDER_MODES)
            )
        )
    return mode


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
    max_heads: int = 1
    pose_model: str = "full"
    head_track_max_gap_ms: float = 500.0
    save_face_landmarks: bool = False
    bboxes: Tuple[BBox, ...] = ()
    bbox_format: str = "normalized"
    person_ids: Optional[Tuple[int, ...]] = None
    head_data: Optional[str] = None
    save_heatmaps: bool = False
    save_rendered: bool = False
    rendered_name: str = "rendered.png"
    heatmap_alpha: float = 0.45
    draw_heatmap: bool = True
    draw_head_box: bool = False
    draw_gaze_peak: bool = True
    draw_gaze_arrow: bool = True
    draw_heatmap_contour: bool = False
    draw_labels: bool = True
    draw_face_box: bool = False
    draw_face_keypoints: bool = False
    draw_pose_head_points: bool = False
    draw_face_mesh: bool = False
    draw_track_state: bool = True
    draw_face_pose_ray: bool = False
    draw_pose_head_ray: bool = False
    reference_ray_length: float = 2.5
    gaze_inout_threshold: float = 0.5
    gazelle_head_mode: Tuple[str, ...] = ("eligible",)
    gaze_render_mode: str = "valid-only"
    heatmap_contour_quantile: float = 0.90
    heatmap_contour_width: Optional[int] = None
    output_fps: Optional[float] = None
    max_frames: Optional[int] = None
    frame_step: int = 1
    output_video_name: str = "rendered.mp4"
    video_codec: str = "mp4v"
    device: str = "auto"
    cache_dir: Optional[str] = None
    checkpoint: Optional[str] = None
    force_download: bool = False

    def validate(self) -> "RuntimeConfig":
        get_model_spec(self.model)
        object.__setattr__(self, "device", validate_device_name(self.device))
        object.__setattr__(self, "max_heads", validate_max_heads(self.max_heads))
        object.__setattr__(self, "pose_model", validate_pose_model(self.pose_model))
        object.__setattr__(
            self,
            "head_track_max_gap_ms",
            validate_positive_finite_float(self.head_track_max_gap_ms, "head_track_max_gap_ms"),
        )
        object.__setattr__(
            self,
            "reference_ray_length",
            validate_positive_finite_float(
                self.reference_ray_length,
                "reference_ray_length",
            ),
        )
        object.__setattr__(
            self,
            "gaze_inout_threshold",
            validate_unit_interval(
                self.gaze_inout_threshold,
                "gaze_inout_threshold",
            ),
        )
        object.__setattr__(
            self,
            "gazelle_head_mode",
            validate_gazelle_head_mode(self.gazelle_head_mode),
        )
        object.__setattr__(
            self,
            "gaze_render_mode",
            validate_gaze_render_mode(self.gaze_render_mode),
        )
        object.__setattr__(self, "rendered_name", validate_rendered_name(self.rendered_name))
        object.__setattr__(self, "heatmap_alpha", validate_heatmap_alpha(self.heatmap_alpha))
        object.__setattr__(
            self,
            "heatmap_contour_quantile",
            validate_heatmap_contour_quantile(self.heatmap_contour_quantile),
        )
        object.__setattr__(
            self,
            "heatmap_contour_width",
            validate_optional_positive_int(self.heatmap_contour_width, "heatmap_contour_width"),
        )
        object.__setattr__(
            self,
            "output_fps",
            validate_optional_positive_float(self.output_fps, "output_fps"),
        )
        object.__setattr__(
            self,
            "max_frames",
            validate_optional_positive_int(self.max_frames, "max_frames"),
        )
        object.__setattr__(self, "frame_step", validate_positive_int(self.frame_step, "frame_step"))
        object.__setattr__(
            self,
            "output_video_name",
            validate_output_video_name(self.output_video_name),
        )
        object.__setattr__(
            self,
            "video_codec",
            validate_video_codec(self.video_codec),
        )
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
            max_heads=args.max_heads,
            pose_model=args.pose_model,
            head_track_max_gap_ms=args.head_track_max_gap_ms,
            save_face_landmarks=args.save_face_landmarks,
            bboxes=tuple(tuple(bbox) for bbox in (args.bbox or ())),
            bbox_format=args.bbox_format,
            person_ids=None if args.person_id is None else tuple(args.person_id),
            head_data=args.head_data,
            save_heatmaps=args.save_heatmaps,
            save_rendered=args.save_rendered,
            rendered_name=args.rendered_name,
            heatmap_alpha=args.heatmap_alpha,
            draw_heatmap=not args.no_heatmap,
            draw_head_box=args.head_box,
            draw_gaze_peak=not args.no_gaze_peak,
            draw_gaze_arrow=not args.no_gaze_arrow,
            draw_heatmap_contour=args.draw_heatmap_contour,
            draw_labels=not args.no_labels,
            draw_face_box=args.face_box,
            draw_face_keypoints=args.face_keypoints,
            draw_pose_head_points=args.pose_head_points,
            draw_face_mesh=args.face_mesh,
            draw_track_state=not args.no_track_state,
            draw_face_pose_ray=args.face_pose_ray,
            draw_pose_head_ray=args.pose_head_ray,
            reference_ray_length=args.reference_ray_length,
            gaze_inout_threshold=args.gaze_inout_threshold,
            gazelle_head_mode=tuple(args.gazelle_head_mode),
            gaze_render_mode=args.gaze_render_mode,
            heatmap_contour_quantile=args.heatmap_contour_quantile,
            heatmap_contour_width=args.heatmap_contour_width,
            output_fps=args.output_fps,
            max_frames=args.max_frames,
            frame_step=args.frame_step,
            output_video_name=args.output_video_name,
            video_codec=args.video_codec,
            device=args.device,
            cache_dir=args.cache_dir,
            checkpoint=args.checkpoint,
            force_download=args.force_download,
        ).validate()
