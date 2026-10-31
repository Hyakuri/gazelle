from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from gazelle.runtime.media import (
    VideoFrameReader,
    VideoFrame,
    VideoFrameWriter,
    detect_media_type,
    is_supported_image_path,
    load_image_rgb,
    resolve_video_fps,
)


class FakeCapture:
    def __init__(self, timestamps=None, fps=30.0, frame_count=0, readable_count=None):
        self.timestamps = timestamps
        self.fps = fps
        self.frame_count = frame_count
        self.readable_count = len(timestamps) if timestamps is not None else readable_count
        self.index = -1
        self.release_calls = 0

    def isOpened(self):
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_POS_MSEC:
            return self.timestamps[self.index] if self.timestamps is not None else self.index * 1000 / self.fps
        return {
            cv2.CAP_PROP_FRAME_WIDTH: 2,
            cv2.CAP_PROP_FRAME_HEIGHT: 2,
            cv2.CAP_PROP_FPS: self.fps,
            cv2.CAP_PROP_FRAME_COUNT: self.frame_count or 0,
        }[prop]

    def read(self):
        self.index += 1
        return (True, np.zeros((2, 2, 3), dtype=np.uint8)) if self.index < self.readable_count else (False, None)

    def release(self):
        self.release_calls += 1


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
    def test_reader_repairs_timestamps_without_displacing_valid_container_time(self):
        nan = float("nan")
        cases = (
            ([0, 0, 30, 98, 130], 20, [0, 1, 30, 98, 130], "crccc"),
            ([500, 480, 520], 30, [500, 501, 520], "crc"),
            ([10.2, 10.4], 30, [10.2, 11], "cr"),
            ([0, 0, 0, 0, 0], 30, [0, 1, 34.333333333, 67.666666667, 101], "crfff"),
            ([0, 33.3, nan, 100], 30, [0, 33.3, 66.633333333, 100], "ccfc"),
            ([-5, 33.3, 66.7], 30, [0, 33.3, 66.7], "fcc"),
            ([0, 0, 0, 33.3, 66.7], 30, [0, 1, 34.333333333, 35, 66.7], "crfrc"),
            ([0, nan], 30, [0, 33.333333333], "cf"),
            ([0, nan], 1000, [0, 1], "cf"),
            ([0, nan], 2000, [0, 1], "cf"),
            ([0, nan, nan], 1000000, [0, 1, 2], "cff"),
            ([0, 0, 0, 0], 1500, [0, 1, 2, 3], "crff"),
            ([float("inf"), -1, None], 0, [0, 33.333333333, 66.666666667], "fff"),
        )
        names = {"c": "container", "r": "repaired", "f": "fps_fallback"}
        for raw, fps, expected, sources in cases:
            with self.subTest(raw=raw, fps=fps), TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "fake.mp4"
                path.touch()
                capture = FakeCapture(raw, fps=fps, frame_count=len(raw))
                with patch("cv2.VideoCapture", return_value=capture), VideoFrameReader(path) as reader:
                    frames = list(reader)
                self.assertEqual(len(frames), len(expected))
                for frame, timestamp, source in zip(frames, expected, sources):
                    self.assertIsInstance(frame.timestamp_ms,float)
                    self.assertAlmostEqual(frame.timestamp_ms, timestamp, places=6)
                    self.assertEqual(frame.timestamp_source, names[source])
                rounded = [int(round(frame.timestamp_ms)) for frame in frames]
                self.assertTrue(all(b > a for a, b in zip(rounded, rounded[1:])))
                self.assertEqual(capture.release_calls, 1)

    def test_missing_timestamps_have_no_accumulated_rounding_drift(self):
        for fps in (29.97, 30, 60):
            with self.subTest(fps=fps), TemporaryDirectory() as tmp:
                count = round(600 * fps)
                path = Path(tmp) / 'fake.mp4'
                path.touch()
                capture = FakeCapture([float('nan')] * count, fps=fps, frame_count=count)
                previous = -1
                with patch('cv2.VideoCapture', return_value=capture), VideoFrameReader(path) as reader:
                    for frame in reader:
                        self.assertGreater(round(frame.timestamp_ms), previous)
                        self.assertEqual(frame.timestamp_source, 'fps_fallback')
                        previous = round(frame.timestamp_ms)
                        frame.image.close()
                self.assertLess(abs(frame.timestamp_ms - (count - 1) * 1000 / fps), 1e-6)

    def test_video_frame_keeps_legacy_constructor(self):
        frame = VideoFrame(0, 0.0, Image.new("RGB", (2, 2)))
        self.assertEqual(frame.timestamp_source, "container")

    def test_reader_rejects_unrepresentable_fallback_instead_of_emitting_infinity(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fake.mp4"
            path.touch()
            capture = FakeCapture([0, float("nan")], fps=1e-310, frame_count=2)
            with patch("cv2.VideoCapture", return_value=capture), VideoFrameReader(path) as reader:
                with self.assertRaisesRegex(ValueError, "represent.*timestamp"):
                    list(reader)

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
