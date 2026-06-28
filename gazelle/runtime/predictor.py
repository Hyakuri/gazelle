import math
from numbers import Real
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import torch
from PIL import Image

from gazelle.runtime.config import validate_device_name
from gazelle.runtime.contracts import BBox, GazePrediction, HeadObservation
from gazelle.runtime.model_registry import get_model_spec
from gazelle.runtime.resources import (
    ensure_cache_dirs,
    load_checkpoint_state_dict,
    load_strict_gazelle_checkpoint,
    resolve_cache_paths,
)


def _resolve_device(device: str) -> torch.device:
    validated = validate_device_name(device)
    if validated == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(validated)


def _is_valid_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_and_clip_bbox(bbox: BBox, index: Optional[int] = None) -> BBox:
    if len(bbox) != 4:
        raise ValueError("Head bbox must contain exactly four values")
    if not all(_is_valid_number(value) for value in bbox):
        raise ValueError("Head bbox values must be finite real numbers")

    xmin, ymin, xmax, ymax = (float(value) for value in bbox)
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("Head bbox must satisfy xmin < xmax and ymin < ymax")

    clipped = (
        min(max(xmin, 0.0), 1.0),
        min(max(ymin, 0.0), 1.0),
        min(max(xmax, 0.0), 1.0),
        min(max(ymax, 0.0), 1.0),
    )
    if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
        label = " at index {}".format(index) if index is not None else ""
        raise ValueError("Head bbox{} is outside the frame after clipping".format(label))
    return clipped


def prepare_head_bboxes(heads: Sequence[HeadObservation]) -> Tuple[List[HeadObservation], List[Optional[BBox]]]:
    prepared_heads = []
    model_bboxes = []
    multiple_heads = len(heads) > 1

    for index, head in enumerate(heads):
        if head.bbox is None:
            if multiple_heads:
                raise ValueError("Multi-person inference requires a valid bbox for every head")
            prepared_heads.append(head)
            model_bboxes.append(None)
            continue

        clipped_bbox = validate_and_clip_bbox(head.bbox, index=index)
        prepared_heads.append(
            HeadObservation(
                person_id=head.person_id,
                bbox=clipped_bbox,
                confidence=head.confidence,
            )
        )
        model_bboxes.append(clipped_bbox)

    return prepared_heads, model_bboxes


def _frame_to_pil_rgb(frame) -> Image.Image:
    if isinstance(frame, Image.Image):
        return frame.convert("RGB")
    if torch.is_tensor(frame):
        tensor = frame.detach().cpu()
        if tensor.ndim != 3:
            raise ValueError("RGB frame tensor must have shape [H, W, 3] or [3, H, W]")
        if tensor.shape[0] == 3 and tensor.shape[-1] != 3:
            tensor = tensor.permute(1, 2, 0)
        if tensor.shape[-1] != 3:
            raise ValueError("RGB frame tensor must have exactly three channels")
        if torch.is_floating_point(tensor):
            tensor = tensor.clamp(0, 1).mul(255).round().to(torch.uint8)
        else:
            tensor = tensor.clamp(0, 255).to(torch.uint8)
        return Image.fromarray(tensor.numpy()).convert("RGB")

    try:
        import numpy as np
    except ImportError as exc:
        raise TypeError("Unsupported RGB frame type: {}".format(type(frame).__name__)) from exc

    if isinstance(frame, np.ndarray):
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("RGB frame array must have shape [H, W, 3]")
        if np.issubdtype(frame.dtype, np.floating):
            frame = np.clip(frame, 0, 1) * 255
        else:
            frame = np.clip(frame, 0, 255)
        return Image.fromarray(frame.astype("uint8")).convert("RGB")

    raise TypeError("Unsupported RGB frame type: {}".format(type(frame).__name__))


def _heatmap_peak(heatmap: torch.Tensor) -> Tuple[Tuple[float, float], float]:
    if heatmap.ndim != 2:
        raise ValueError("Gazelle heatmap must be a 2D tensor")
    height, width = heatmap.shape
    if height == 0 or width == 0:
        raise ValueError("Gazelle heatmap must not be empty")
    flat_index = int(heatmap.flatten().argmax().item())
    y_index = flat_index // width
    x_index = flat_index % width
    return (x_index / float(width), y_index / float(height)), float(heatmap[y_index, x_index].item())


class GazellePredictor:
    """Programmatic single-frame Gazelle runtime wrapper."""

    def __init__(self, model_name: str, model, transform, device: str = "auto"):
        get_model_spec(model_name)
        self.model_name = model_name
        self.model = model
        self.transform = transform
        self.device = _resolve_device(device)
        self.model.to(self.device)
        self.model.eval()

    @classmethod
    def from_checkpoint(
        cls,
        model_name: str,
        checkpoint_path,
        device: str = "auto",
        cache_dir: Optional[str] = None,
    ) -> "GazellePredictor":
        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            raise FileNotFoundError("Checkpoint does not exist: {}".format(checkpoint_path))

        cache_paths = resolve_cache_paths(cache_dir)
        ensure_cache_dirs(cache_paths)
        torch.hub.set_dir(str(cache_paths.torch_hub_dir))

        from gazelle.model import get_gazelle_model

        model, transform = get_gazelle_model(model_name)
        state_dict, _ = load_checkpoint_state_dict(checkpoint_path)
        load_strict_gazelle_checkpoint(model, state_dict)
        return cls(model_name=model_name, model=model, transform=transform, device=device)

    def predict_frame(self, frame, heads: Iterable[HeadObservation]) -> List[GazePrediction]:
        heads = tuple(heads)
        if not heads:
            return []

        prepared_heads, model_bboxes = prepare_head_bboxes(heads)
        pil_frame = _frame_to_pil_rgb(frame)
        image_tensor = self.transform(pil_frame)
        if not torch.is_tensor(image_tensor):
            raise TypeError("Gazelle transform must return a torch.Tensor")
        if image_tensor.ndim != 3:
            raise ValueError("Gazelle transform must return a [C, H, W] tensor")

        model_input = {
            "images": image_tensor.unsqueeze(dim=0).to(self.device),
            "bboxes": [model_bboxes],
        }
        with torch.no_grad():
            output = self.model(model_input)

        heatmaps = output["heatmap"][0]
        if len(heatmaps) != len(prepared_heads):
            raise RuntimeError(
                "Gazelle returned {} heatmaps for {} heads".format(
                    len(heatmaps),
                    len(prepared_heads),
                )
            )

        inout_values = None
        if output.get("inout") is not None:
            inout_values = output["inout"][0]
            if len(inout_values) != len(prepared_heads):
                raise RuntimeError(
                    "Gazelle returned {} inout scores for {} heads".format(
                        len(inout_values),
                        len(prepared_heads),
                    )
                )

        predictions = []
        for index, head in enumerate(prepared_heads):
            heatmap = heatmaps[index].detach().cpu()
            gaze_peak, peak_value = _heatmap_peak(heatmap)
            inout_score = None
            if inout_values is not None:
                inout_score = float(inout_values[index].detach().cpu().item())
            predictions.append(
                GazePrediction(
                    person_id=head.person_id,
                    bbox=head.bbox,
                    heatmap=heatmap,
                    gaze_peak=gaze_peak,
                    heatmap_peak_value=peak_value,
                    inout_score=inout_score,
                )
            )
        return predictions
