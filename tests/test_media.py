from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np
from PIL import Image

from gazelle.runtime.media import (
    VideoFrameReader,
    VideoFrameWriter,
    detect_media_type,
    is_supported_image_path,
    load_image_rgb,
    resolve_video_fps,
)


def write_tiny_video(path, width=32, height=24, fps=5.0, frame_count=3):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Failed to create test video: {}".format(path))
    try:
        for index in range(frame_count):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :, 0] = 20 + index
            frame[:, :, 1] = 40 + index
            frame[:, :, 2] = 60 + index
            writer.write(frame)
    finally:
        writer.release()


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

            with self.assertRaisesRegex(ValueError, "Unsupported input path"):
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

    def test_detect_media_type_image(self):
        self.assertEqual(detect_media_type("frame.png"), "image")

    def test_detect_media_type_video(self):
        self.assertEqual(detect_media_type("clip.mp4"), "video")

    def test_detect_media_type_unsupported(self):
        with self.assertRaisesRegex(ValueError, "Unsupported input path"):
            detect_media_type("frame.txt")

    def test_video_frame_reader_reads_frames(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, frame_count=3)

            with VideoFrameReader(video_path) as reader:
                frames = list(reader)

        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0].index, 0)
        self.assertEqual(frames[0].image.mode, "RGB")
        self.assertEqual(frames[0].image.size, (32, 24))

    def test_video_frame_reader_metadata(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "clip.mp4"
            write_tiny_video(video_path, width=40, height=30, fps=7.0, frame_count=2)

            with VideoFrameReader(video_path) as reader:
                metadata = reader.metadata

        self.assertEqual(metadata.width, 40)
        self.assertEqual(metadata.height, 30)
        self.assertGreater(metadata.fps, 0.0)
        self.assertIn(metadata.frame_count, (None, 2))

    def test_video_frame_reader_rejects_missing_file(self):
        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                VideoFrameReader(Path(tmpdir) / "missing.mp4")

    def test_video_frame_reader_rejects_invalid_video(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "broken.mp4"
            video_path.write_text("not a video", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Failed to open video"):
                VideoFrameReader(video_path)

    def test_resolve_video_fps_uses_source_when_valid(self):
        self.assertEqual(resolve_video_fps(25.0, output_fps=12.0), 25.0)

    def test_resolve_video_fps_uses_output_when_source_invalid(self):
        self.assertEqual(resolve_video_fps(0.0, output_fps=12.0), 12.0)

    def test_resolve_video_fps_falls_back_to_30(self):
        self.assertEqual(resolve_video_fps(0.0, output_fps=None), 30.0)

    def test_video_frame_writer_writes_frames(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "rendered.mp4"
            with VideoFrameWriter(video_path, width=32, height=24, fps=5.0) as writer:
                writer.write(Image.new("RGB", (32, 24), color=(10, 20, 30)))
                writer.write(Image.new("RGB", (32, 24), color=(20, 30, 40)))

            with VideoFrameReader(video_path) as reader:
                frames = list(reader)

        self.assertEqual(len(frames), 2)

    def test_video_frame_writer_rejects_bad_fps(self):
        with TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "FPS"):
                VideoFrameWriter(Path(tmpdir) / "rendered.mp4", width=32, height=24, fps=0.0)

    def test_video_frame_writer_rejects_mismatched_frame_size(self):
        with TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "rendered.mp4"
            with VideoFrameWriter(video_path, width=32, height=24, fps=5.0) as writer:
                with self.assertRaisesRegex(ValueError, "does not match"):
                    writer.write(Image.new("RGB", (16, 12), color=(10, 20, 30)))


if __name__ == "__main__":
    unittest.main()
