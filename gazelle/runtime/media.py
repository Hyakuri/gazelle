from pathlib import Path
from typing import Tuple

from PIL import Image, UnidentifiedImageError


SUPPORTED_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def is_supported_image_path(path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_IMAGE_SUFFIXES


def load_image_rgb(path) -> Tuple[Image.Image, int, int]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("Input image does not exist: {}".format(path))
    if not is_supported_image_path(path):
        raise ValueError(
            "Unsupported input path for image pipeline; video pipeline is not implemented: {}".format(
                path
            )
        )

    try:
        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            rgb_image.load()
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Failed to open image '{}': {}".format(path, exc)) from exc

    return rgb_image, rgb_image.width, rgb_image.height
