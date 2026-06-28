from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from gazelle.runtime.media import is_supported_image_path, load_image_rgb


class MediaTest(unittest.TestCase):
    def test_load_image_rgb_reads_image(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            Image.new("RGB", (8, 6), color=(10, 20, 30)).save(image_path)

            image, width, height = load_image_rgb(image_path)

        self.assertEqual(image.mode, "RGB")
        self.assertEqual((width, height), (8, 6))

    def test_load_image_rgb_converts_to_rgb(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "frame.png"
            Image.new("L", (5, 4), color=128).save(image_path)

            image, width, height = load_image_rgb(image_path)

        self.assertEqual(image.mode, "RGB")
        self.assertEqual((width, height), (5, 4))

    def test_load_image_rgb_rejects_missing_file(self):
        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                load_image_rgb(Path(tmpdir) / "missing.png")

    def test_load_image_rgb_rejects_unsupported_extension(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "frame.txt"
            path.write_text("not an image", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "video pipeline is not implemented"):
                load_image_rgb(path)

    def test_load_image_rgb_reports_invalid_image(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "frame.png"
            path.write_text("not an image", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Failed to open image"):
                load_image_rgb(path)

    def test_supported_image_suffixes_are_case_insensitive(self):
        self.assertTrue(is_supported_image_path("FRAME.JPG"))
        self.assertTrue(is_supported_image_path("frame.webp"))
        self.assertFalse(is_supported_image_path("frame.mov"))


if __name__ == "__main__":
    unittest.main()
