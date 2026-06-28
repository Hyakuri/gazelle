import hashlib
import math
from numbers import Real
from pathlib import Path
from typing import Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from gazelle.runtime.geometry import normalized_bbox_to_pixel


SUPPORTED_RENDERED_SUFFIXES = (".png", ".jpg", ".jpeg")


def _validate_alpha(alpha: float) -> float:
    if not isinstance(alpha, Real) or isinstance(alpha, bool) or not math.isfinite(float(alpha)):
        raise ValueError("alpha must be a finite real number")
    alpha = float(alpha)
    if alpha < 0.0 or alpha > 1.0:
        raise ValueError("alpha must be between 0.0 and 1.0")
    return alpha


def _image_to_rgb_pil(image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if torch.is_tensor(image):
        tensor = image.detach().cpu()
        if tensor.ndim != 3:
            raise ValueError("image tensor must have shape [H, W, 3] or [3, H, W]")
        if tensor.shape[0] == 3 and tensor.shape[-1] != 3:
            tensor = tensor.permute(1, 2, 0)
        if tensor.shape[-1] != 3:
            raise ValueError("image tensor must have exactly three channels")
        array = tensor.numpy()
    else:
        array = np.asarray(image)

    if array.ndim != 3 or array.shape[-1] != 3:
        raise ValueError("image array must have shape [H, W, 3]")
    if np.issubdtype(array.dtype, np.floating):
        array = np.clip(array, 0.0, 1.0) * 255.0
    else:
        array = np.clip(array, 0, 255)
    return Image.fromarray(array.astype("uint8")).convert("RGB")


def _heatmap_to_array(heatmap) -> np.ndarray:
    if torch.is_tensor(heatmap):
        array = heatmap.detach().cpu().numpy()
    else:
        array = np.asarray(heatmap)
    if array.ndim != 2:
        raise ValueError("heatmap must be a 2D tensor or array")
    if array.size == 0:
        raise ValueError("heatmap must not be empty")
    return array.astype("float32", copy=True)


def _normalize_heatmap(array: np.ndarray) -> np.ndarray:
    finite_mask = np.isfinite(array)
    if not finite_mask.any():
        return np.zeros_like(array, dtype="float32")
    finite_values = array[finite_mask]
    min_value = float(finite_values.min())
    max_value = float(finite_values.max())
    if max_value == min_value:
        return np.zeros_like(array, dtype="float32")
    normalized = (array - min_value) / (max_value - min_value)
    return np.nan_to_num(normalized, nan=0.0, posinf=1.0, neginf=0.0).clip(0.0, 1.0)


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def stable_color_for_person(person_id) -> Tuple[int, int, int]:
    digest = hashlib.sha256(str(person_id).encode("utf-8")).digest()
    return tuple(64 + digest[index] % 192 for index in range(3))


def heatmap_to_overlay(
    heatmap,
    image_width: int,
    image_height: int,
    color: Tuple[int, int, int],
    alpha: float,
) -> Image.Image:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_width and image_height must be greater than 0")
    alpha = _validate_alpha(alpha)
    array = _normalize_heatmap(_heatmap_to_array(heatmap))
    alpha_image = Image.fromarray((array * alpha * 255.0).astype("uint8"), mode="L")
    alpha_image = alpha_image.resize((int(image_width), int(image_height)), resample=Image.BILINEAR)
    overlay = Image.new("RGBA", (int(image_width), int(image_height)), tuple(color) + (0,))
    overlay.putalpha(alpha_image)
    return overlay


def draw_prediction(
    draw_context,
    prediction,
    image_width: int,
    image_height: int,
    color,
    draw_head_box: bool,
    draw_gaze_peak: bool,
    draw_labels: bool,
) -> None:
    x_anchor = 4
    y_anchor = 4
    line_width = max(1, min(image_width, image_height) // 160)

    if draw_head_box and prediction.bbox is not None:
        xmin, ymin, xmax, ymax = normalized_bbox_to_pixel(
            prediction.bbox,
            image_width=image_width,
            image_height=image_height,
        )
        xmin = _clamp(xmin, 0.0, float(image_width - 1))
        ymin = _clamp(ymin, 0.0, float(image_height - 1))
        xmax = _clamp(xmax, 0.0, float(image_width - 1))
        ymax = _clamp(ymax, 0.0, float(image_height - 1))
        draw_context.rectangle((xmin, ymin, xmax, ymax), outline=color, width=line_width)
        x_anchor = int(xmin)
        y_anchor = max(0, int(ymin) - 12)

    if draw_gaze_peak and prediction.gaze_peak is not None:
        x_value, y_value = prediction.gaze_peak
        x = _clamp(float(x_value) * float(image_width - 1), 0.0, float(image_width - 1))
        y = _clamp(float(y_value) * float(image_height - 1), 0.0, float(image_height - 1))
        radius = max(2, min(image_width, image_height) // 80)
        draw_context.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=line_width)
        draw_context.line((x - radius, y, x + radius, y), fill=color, width=line_width)
        draw_context.line((x, y - radius, x, y + radius), fill=color, width=line_width)

    if draw_labels:
        label = "id={}".format(prediction.person_id)
        if prediction.inout_score is not None:
            label = "{} inout={:.2f}".format(label, float(prediction.inout_score))
        font = ImageFont.load_default()
        try:
            left, top, right, bottom = draw_context.textbbox((x_anchor, y_anchor), label, font=font)
        except AttributeError:
            width, height = draw_context.textsize(label, font=font)
            left, top, right, bottom = x_anchor, y_anchor, x_anchor + width, y_anchor + height
        draw_context.rectangle((left, top, right + 2, bottom + 2), fill=(0, 0, 0))
        draw_context.text((x_anchor + 1, y_anchor + 1), label, fill=color, font=font)


def render_predictions(
    image,
    predictions,
    *,
    heatmap_alpha: float = 0.45,
    draw_head_box: bool = True,
    draw_gaze_peak: bool = True,
    draw_labels: bool = True,
) -> Image.Image:
    rendered = _image_to_rgb_pil(image).copy()
    image_width, image_height = rendered.size
    predictions = tuple(predictions)

    for prediction in predictions:
        color = stable_color_for_person(prediction.person_id)
        if prediction.heatmap is not None:
            overlay = heatmap_to_overlay(
                prediction.heatmap,
                image_width=image_width,
                image_height=image_height,
                color=color,
                alpha=heatmap_alpha,
            )
            rendered = Image.alpha_composite(rendered.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(rendered)
        draw_prediction(
            draw,
            prediction,
            image_width=image_width,
            image_height=image_height,
            color=color,
            draw_head_box=draw_head_box,
            draw_gaze_peak=draw_gaze_peak,
            draw_labels=draw_labels,
        )
    return rendered


def save_rendered_image(path, image) -> None:
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_RENDERED_SUFFIXES:
        raise ValueError(
            "Rendered image path must end with one of: {}".format(
                ", ".join(SUPPORTED_RENDERED_SUFFIXES)
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    image = _image_to_rgb_pil(image)
    image.save(path)
