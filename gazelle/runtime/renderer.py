import hashlib
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from gazelle.runtime.geometry import normalized_bbox_to_pixel


SUPPORTED_RENDERED_SUFFIXES = (".png", ".jpg", ".jpeg")
PEAK_MARKER_COLOR = (255, 0, 0)


@dataclass(frozen=True)
class RenderOptions:
    heatmap_alpha: float = 0.45
    draw_heatmap: bool = True
    draw_head_box: bool = False
    draw_gaze_peak: bool = True
    draw_gaze_arrow: bool = True
    draw_heatmap_contour: bool = False
    draw_labels: bool = True
    heatmap_contour_quantile: float = 0.90
    heatmap_contour_width: Optional[int] = None
    arrow_width: Optional[int] = None
    peak_marker_size: Optional[int] = None


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


def _validate_quantile(quantile: float) -> float:
    if not isinstance(quantile, Real) or isinstance(quantile, bool) or not math.isfinite(float(quantile)):
        raise ValueError("quantile must be a finite real number")
    quantile = float(quantile)
    if quantile < 0.0 or quantile > 1.0:
        raise ValueError("quantile must be between 0.0 and 1.0")
    return quantile


def _validate_positive_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("{} must be an int greater than or equal to 1".format(field_name))
    return value


def _auto_line_width(image_width: int, image_height: int) -> int:
    return max(1, min(int(image_width), int(image_height)) // 160)


def _auto_peak_marker_size(image_width: int, image_height: int) -> int:
    return max(4, min(int(image_width), int(image_height)) // 40)


def normalized_point_to_pixel(point, image_width: int, image_height: int) -> Tuple[float, float]:
    x_value, y_value = point
    x = _clamp(float(x_value) * float(image_width - 1), 0.0, float(image_width - 1))
    y = _clamp(float(y_value) * float(image_height - 1), 0.0, float(image_height - 1))
    return x, y


def bbox_center_normalized(bbox) -> Optional[Tuple[float, float]]:
    if bbox is None:
        return None
    xmin, ymin, xmax, ymax = bbox
    return (float(xmin) + float(xmax)) / 2.0, (float(ymin) + float(ymax)) / 2.0


def bbox_center_pixel(bbox, image_width: int, image_height: int) -> Optional[Tuple[float, float]]:
    center = bbox_center_normalized(bbox)
    if center is None:
        return None
    return normalized_point_to_pixel(center, image_width, image_height)


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


def heatmap_to_topk_mask(heatmap, *, quantile: float) -> np.ndarray:
    quantile = _validate_quantile(quantile)
    array = _heatmap_to_array(heatmap)
    finite_mask = np.isfinite(array)
    if not finite_mask.any():
        return np.zeros(array.shape, dtype=bool)
    finite_values = array[finite_mask]
    if float(finite_values.max()) == float(finite_values.min()):
        return np.zeros(array.shape, dtype=bool)
    threshold = float(np.quantile(finite_values, quantile))
    return np.logical_and(finite_mask, array >= threshold)


def _mask_boundary(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    center = padded[1:-1, 1:-1]
    up = padded[:-2, 1:-1]
    down = padded[2:, 1:-1]
    left = padded[1:-1, :-2]
    right = padded[1:-1, 2:]
    eroded = center & up & down & left & right
    return center & ~eroded


def heatmap_mask_to_contour_overlay(
    mask,
    image_width: int,
    image_height: int,
    color,
    width: int,
) -> Image.Image:
    width = _validate_positive_int(width, "width")
    mask_array = np.asarray(mask, dtype=bool)
    if mask_array.ndim != 2:
        raise ValueError("mask must be a 2D array")
    if mask_array.size == 0:
        raise ValueError("mask must not be empty")
    mask_image = Image.fromarray(mask_array.astype("uint8") * 255, mode="L")
    mask_image = mask_image.resize((int(image_width), int(image_height)), resample=Image.NEAREST)
    resized = np.asarray(mask_image, dtype=np.uint8) > 0
    boundary = _mask_boundary(resized)

    overlay = Image.new("RGBA", (int(image_width), int(image_height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    ys, xs = np.nonzero(boundary)
    radius = max(0, int(width - 1) // 2)
    for x, y in zip(xs, ys):
        if radius:
            draw.rectangle((x - radius, y - radius, x + radius, y + radius), fill=tuple(color) + (255,))
        else:
            draw.point((int(x), int(y)), fill=tuple(color) + (255,))
    return overlay


def draw_gaze_arrow(
    draw_context,
    *,
    bbox,
    gaze_peak,
    image_width: int,
    image_height: int,
    color,
    width: int,
) -> None:
    start = bbox_center_pixel(bbox, image_width, image_height)
    if start is None or gaze_peak is None:
        return
    end = normalized_point_to_pixel(gaze_peak, image_width, image_height)
    start_x, start_y = start
    end_x, end_y = end
    dx = end_x - start_x
    dy = end_y - start_y
    length = math.hypot(dx, dy)
    if length < 1.0:
        return
    draw_context.line((start_x, start_y, end_x, end_y), fill=color, width=width)

    head_length = max(6.0, float(width) * 4.0)
    angle = math.atan2(dy, dx)
    spread = math.radians(28.0)
    for sign in (-1, 1):
        head_angle = angle + math.pi + sign * spread
        x = end_x + math.cos(head_angle) * head_length
        y = end_y + math.sin(head_angle) * head_length
        draw_context.line((end_x, end_y, x, y), fill=color, width=width)


def draw_gaze_peak_x(
    draw_context,
    *,
    gaze_peak,
    image_width: int,
    image_height: int,
    size: int,
    color=PEAK_MARKER_COLOR,
    width: int = 2,
) -> None:
    if gaze_peak is None:
        return
    x, y = normalized_point_to_pixel(gaze_peak, image_width, image_height)
    half = float(size) / 2.0
    draw_context.line((x - half, y - half, x + half, y + half), fill=color, width=width)
    draw_context.line((x - half, y + half, x + half, y - half), fill=color, width=width)


def build_prediction_label(prediction) -> str:
    label = "id={}".format(prediction.person_id)
    if prediction.inout_score is not None:
        label = "{} inout={:.2f}".format(label, float(prediction.inout_score))
    if prediction.heatmap_peak_value is not None:
        label = "{} peak={:.2f}".format(label, float(prediction.heatmap_peak_value))
    return label


def _label_anchor_for_prediction(prediction, image_width: int, image_height: int) -> Tuple[int, int]:
    if prediction.bbox is None:
        return 4, 4
    xmin, ymin, _, _ = normalized_bbox_to_pixel(
        prediction.bbox,
        image_width=image_width,
        image_height=image_height,
    )
    xmin = _clamp(xmin, 0.0, float(image_width - 1))
    ymin = _clamp(ymin, 0.0, float(image_height - 1))
    return int(xmin), max(0, int(ymin) - 12)


def draw_prediction(
    draw_context,
    prediction,
    image_width: int,
    image_height: int,
    color,
    options: RenderOptions,
    font=None,
) -> None:
    x_anchor, y_anchor = _label_anchor_for_prediction(prediction, image_width, image_height)
    line_width = _auto_line_width(image_width, image_height)
    arrow_width = options.arrow_width or line_width
    peak_marker_size = options.peak_marker_size or _auto_peak_marker_size(image_width, image_height)

    if options.draw_head_box and prediction.bbox is not None:
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

    if options.draw_gaze_arrow:
        draw_gaze_arrow(
            draw_context,
            bbox=prediction.bbox,
            gaze_peak=prediction.gaze_peak,
            image_width=image_width,
            image_height=image_height,
            color=color,
            width=arrow_width,
        )

    if options.draw_gaze_peak:
        draw_gaze_peak_x(
            draw_context,
            gaze_peak=prediction.gaze_peak,
            image_width=image_width,
            image_height=image_height,
            size=peak_marker_size,
            color=PEAK_MARKER_COLOR,
            width=line_width,
        )

    if options.draw_labels:
        label = build_prediction_label(prediction)
        font = font if font is not None else ImageFont.load_default()
        try:
            left, top, right, bottom = draw_context.textbbox((x_anchor, y_anchor), label, font=font)
        except AttributeError:
            width, height = draw_context.textsize(label, font=font)
            left, top, right, bottom = x_anchor, y_anchor, x_anchor + width, y_anchor + height
        draw_context.rectangle((left, top, right + 2, bottom + 2), fill=(0, 0, 0))
        draw_context.text((x_anchor + 1, y_anchor + 1), label, fill=color, font=font)


class PredictionRenderer:
    def __init__(self, options: RenderOptions = None):
        self.options = options or RenderOptions()
        self.font = ImageFont.load_default()

    def render(self, image, predictions) -> Image.Image:
        rendered = _image_to_rgb_pil(image).copy()
        image_width, image_height = rendered.size
        predictions = tuple(predictions)

        for prediction in predictions:
            color = stable_color_for_person(prediction.person_id)
            if self.options.draw_heatmap and prediction.heatmap is not None:
                overlay = heatmap_to_overlay(
                    prediction.heatmap,
                    image_width=image_width,
                    image_height=image_height,
                    color=color,
                    alpha=self.options.heatmap_alpha,
                )
                rendered = Image.alpha_composite(rendered.convert("RGBA"), overlay).convert("RGB")
            if self.options.draw_heatmap_contour and prediction.heatmap is not None:
                mask = heatmap_to_topk_mask(
                    prediction.heatmap,
                    quantile=self.options.heatmap_contour_quantile,
                )
                contour_overlay = heatmap_mask_to_contour_overlay(
                    mask,
                    image_width=image_width,
                    image_height=image_height,
                    color=color,
                    width=self.options.heatmap_contour_width
                    or max(2, _auto_line_width(image_width, image_height)),
                )
                rendered = Image.alpha_composite(rendered.convert("RGBA"), contour_overlay).convert("RGB")
            draw = ImageDraw.Draw(rendered)
            draw_prediction(
                draw,
                prediction,
                image_width=image_width,
                image_height=image_height,
                color=color,
                options=self.options,
                font=self.font,
            )
        return rendered


def render_predictions(
    image,
    predictions,
    *,
    heatmap_alpha: float = 0.45,
    draw_heatmap: bool = True,
    draw_head_box: bool = False,
    draw_gaze_peak: bool = True,
    draw_gaze_arrow: bool = True,
    draw_heatmap_contour: bool = False,
    draw_labels: bool = True,
    heatmap_contour_quantile: float = 0.90,
    heatmap_contour_width: Optional[int] = None,
) -> Image.Image:
    return PredictionRenderer(
        RenderOptions(
            heatmap_alpha=heatmap_alpha,
            draw_heatmap=draw_heatmap,
            draw_head_box=draw_head_box,
            draw_gaze_peak=draw_gaze_peak,
            draw_gaze_arrow=draw_gaze_arrow,
            draw_heatmap_contour=draw_heatmap_contour,
            draw_labels=draw_labels,
            heatmap_contour_quantile=heatmap_contour_quantile,
            heatmap_contour_width=heatmap_contour_width,
        )
    ).render(image, predictions)


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
