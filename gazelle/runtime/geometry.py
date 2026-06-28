import math
from numbers import Real
from typing import Optional

from gazelle.runtime.contracts import BBox


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _coerce_bbox_values(bbox: BBox) -> BBox:
    try:
        values = tuple(bbox)
    except TypeError as exc:
        raise ValueError("bbox must be an iterable of four finite real values") from exc
    if len(values) != 4:
        raise ValueError("bbox must contain exactly four values")
    if not all(_is_finite_real(value) for value in values):
        raise ValueError("bbox values must be finite real numbers")
    return tuple(float(value) for value in values)


def sanitize_normalized_bbox(bbox: BBox, clip: bool = True, min_size: float = 1e-6) -> BBox:
    if min_size <= 0:
        raise ValueError("min_size must be greater than 0")

    xmin, ymin, xmax, ymax = _coerce_bbox_values(bbox)
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("bbox must satisfy xmin < xmax and ymin < ymax")

    if clip:
        xmin = min(max(xmin, 0.0), 1.0)
        ymin = min(max(ymin, 0.0), 1.0)
        xmax = min(max(xmax, 0.0), 1.0)
        ymax = min(max(ymax, 0.0), 1.0)

    if xmin >= xmax or ymin >= ymax:
        raise ValueError("bbox is empty after clipping")
    if xmax - xmin < min_size or ymax - ymin < min_size:
        raise ValueError("bbox is smaller than min_size after sanitization")
    return (xmin, ymin, xmax, ymax)


def pixel_bbox_to_normalized(
    bbox: BBox,
    image_width: int,
    image_height: int,
    clip: bool = True,
    min_size: float = 1e-6,
) -> BBox:
    if image_width <= 0:
        raise ValueError("image_width must be greater than 0")
    if image_height <= 0:
        raise ValueError("image_height must be greater than 0")

    xmin, ymin, xmax, ymax = _coerce_bbox_values(bbox)
    normalized = (
        xmin / float(image_width),
        ymin / float(image_height),
        xmax / float(image_width),
        ymax / float(image_height),
    )
    return sanitize_normalized_bbox(normalized, clip=clip, min_size=min_size)


def normalized_bbox_to_pixel(bbox: BBox, image_width: int, image_height: int) -> BBox:
    if image_width <= 0:
        raise ValueError("image_width must be greater than 0")
    if image_height <= 0:
        raise ValueError("image_height must be greater than 0")

    xmin, ymin, xmax, ymax = sanitize_normalized_bbox(bbox, clip=True)
    return (
        min(max(xmin * image_width, 0.0), float(image_width)),
        min(max(ymin * image_height, 0.0), float(image_height)),
        min(max(xmax * image_width, 0.0), float(image_width)),
        min(max(ymax * image_height, 0.0), float(image_height)),
    )


def sanitize_head_bbox_for_model(bbox: Optional[BBox]) -> Optional[BBox]:
    if bbox is None:
        return None
    return sanitize_normalized_bbox(bbox, clip=True)
