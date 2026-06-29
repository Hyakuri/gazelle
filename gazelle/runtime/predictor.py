from pathlib import Path
from collections.abc import Mapping
from typing import Iterable, List, Optional, Sequence, Tuple

import torch
from PIL import Image

from gazelle.runtime.config import validate_device_name
from gazelle.runtime.contracts import BBox, GazePrediction, HeadObservation
from gazelle.runtime.environment import temporarily_disable_xformers_for_cpu_device
from gazelle.runtime.geometry import sanitize_head_bbox_for_model
from gazelle.runtime.model_registry import get_model_spec
from gazelle.runtime.resources import (
    ensure_cache_dirs,
    load_checkpoint_state_dict,
    load_strict_gazelle_checkpoint,
    resolve_cache_paths,
)


def resolve_torch_device(device_name: str) -> torch.device:
    validated = validate_device_name(device_name)
    if validated == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if validated == "cpu":
        return torch.device("cpu")
    if validated == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("CUDA device requested but CUDA is not available")
        return torch.device("cuda")
    if validated.startswith("cuda:"):
        if not torch.cuda.is_available():
            raise ValueError("{} requested but CUDA is not available".format(validated))
        index = int(validated[len("cuda:") :])
        device_count = torch.cuda.device_count()
        if index >= device_count:
            raise ValueError(
                "{} requested but only {} CUDA device(s) are available".format(
                    validated,
                    device_count,
                )
            )
        return torch.device(validated)
    return torch.device(validated)


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

        try:
            clipped_bbox = sanitize_head_bbox_for_model(head.bbox)
        except ValueError as exc:
            raise ValueError("Invalid head bbox at index {}: {}".format(index, exc)) from exc
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


def _batch_len(value: object) -> int:
    try:
        return len(value)
    except TypeError:
        return -1


def _extract_gazelle_outputs(output, expected_people: int):
    if not isinstance(output, Mapping):
        raise RuntimeError("Gazelle output must be a mapping; got {}".format(type(output).__name__))
    if "heatmap" not in output:
        raise RuntimeError("Gazelle output is missing required 'heatmap' key")

    heatmap_batch = output["heatmap"]
    if not isinstance(heatmap_batch, (list, tuple)):
        raise RuntimeError("Gazelle heatmap output must be a list/tuple batch")
    if len(heatmap_batch) != 1:
        raise RuntimeError(
            "Gazelle heatmap batch length mismatch: expected 1, got {}".format(len(heatmap_batch))
        )
    heatmaps = heatmap_batch[0]
    actual_people = _batch_len(heatmaps)
    if actual_people != expected_people:
        raise RuntimeError(
            "Gazelle heatmap person count mismatch: expected {}, got {}".format(
                expected_people,
                actual_people,
            )
        )

    inout_values = None
    inout_batch = output.get("inout")
    if inout_batch is not None:
        if not isinstance(inout_batch, (list, tuple)):
            raise RuntimeError("Gazelle inout output must be a list/tuple batch or None")
        if len(inout_batch) != 1:
            raise RuntimeError(
                "Gazelle inout batch length mismatch: expected 1, got {}".format(len(inout_batch))
            )
        inout_values = inout_batch[0]
        actual_inout_people = _batch_len(inout_values)
        if actual_inout_people != expected_people:
            raise RuntimeError(
                "Gazelle inout person count mismatch: expected {}, got {}".format(
                    expected_people,
                    actual_inout_people,
                )
            )

    return heatmaps, inout_values


class GazellePredictor:
    """Programmatic single-frame Gazelle runtime wrapper."""

    def __init__(self, model_name: str, model, transform, device: str = "auto"):
        get_model_spec(model_name)
        self.model_name = model_name
        self.model = model
        self.transform = transform
        self.device = resolve_torch_device(device)
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
        get_model_spec(model_name)
        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            raise FileNotFoundError("Checkpoint does not exist: {}".format(checkpoint_path))

        cache_paths = resolve_cache_paths(cache_dir)
        ensure_cache_dirs(cache_paths)
        torch.hub.set_dir(str(cache_paths.torch_hub_dir))
        resolved_device = resolve_torch_device(device)

        with temporarily_disable_xformers_for_cpu_device(resolved_device):
            from gazelle.model import get_gazelle_model

            model, transform = get_gazelle_model(model_name)
        state_dict, _ = load_checkpoint_state_dict(checkpoint_path)
        load_strict_gazelle_checkpoint(model, state_dict)
        return cls(model_name=model_name, model=model, transform=transform, device=str(resolved_device))

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
        with torch.inference_mode():
            output = self.model(model_input)

        heatmaps, inout_values = _extract_gazelle_outputs(output, expected_people=len(prepared_heads))

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
