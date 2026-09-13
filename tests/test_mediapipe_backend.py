import builtins
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from gazelle.runtime.perception.mediapipe_backend import (
    MediaPipeBackend,
    MediaPipeTaskBundle,
)
from gazelle.runtime.perception.resources import (
    MediaPipeResourcePaths,
    PreparedMediaPipeResources,
)


def _landmark(x, y, z=0.0, visibility=None, presence=None):
    return SimpleNamespace(
        x=x,
        y=y,
        z=z,
        visibility=visibility,
        presence=presence,
    )


def _detection(x, y, width, height, score, keypoints=()):
    return SimpleNamespace(
        bounding_box=SimpleNamespace(
            origin_x=x,
            origin_y=y,
            width=width,
            height=height,
        ),
        categories=[SimpleNamespace(score=score)],
        keypoints=list(keypoints),
    )


def _face_result(landmarks=(), matrix=None):
    return SimpleNamespace(
        face_landmarks=[] if not landmarks else [list(landmarks)],
        facial_transformation_matrixes=[] if matrix is None else [matrix],
    )


def _pose_result(landmarks=(), world_landmarks=()):
    return SimpleNamespace(
        pose_landmarks=[list(item) for item in landmarks],
        pose_world_landmarks=[list(item) for item in world_landmarks],
    )


def _identity_matrix():
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def _rotation_matrix(axis, degrees):
    angle = math.radians(degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    if axis == "yaw":
        rotation = (
            (cosine, 0.0, sine),
            (0.0, 1.0, 0.0),
            (-sine, 0.0, cosine),
        )
    elif axis == "pitch":
        rotation = (
            (1.0, 0.0, 0.0),
            (0.0, cosine, -sine),
            (0.0, sine, cosine),
        )
    elif axis == "roll":
        rotation = (
            (cosine, -sine, 0.0),
            (sine, cosine, 0.0),
            (0.0, 0.0, 1.0),
        )
    else:
        raise ValueError(axis)
    return tuple(
        tuple(rotation[row][column] if column < 3 else 0.0 for column in range(4))
        for row in range(3)
    ) + ((0.0, 0.0, 0.0, 1.0),)


class CountingFrame:
    def __init__(self, image):
        self.image = image
        self.convert_calls = []

    def convert(self, mode):
        self.convert_calls.append(mode)
        return self.image.convert(mode)


class FakeImageFactory:
    def __init__(self):
        self.arrays = []

    def __call__(self, array):
        copied = array.copy()
        self.arrays.append(copied)
        return SimpleNamespace(array=copied)


class FakeTask:
    def __init__(self, *, image_results=(), video_results=(), error=None):
        self.image_results = list(image_results)
        self.video_results = list(video_results)
        self.error = error
        self.image_calls = []
        self.video_calls = []
        self.close_count = 0

    def detect(self, image):
        self.image_calls.append(image)
        if self.error is not None:
            raise self.error
        return self.image_results.pop(0)

    def detect_for_video(self, image, timestamp_ms):
        self.video_calls.append((image, timestamp_ms))
        if self.error is not None:
            raise self.error
        return self.video_results.pop(0)

    def close(self):
        self.close_count += 1


class RecordingTaskFactory:
    def __init__(self, bundle):
        self.bundle = bundle
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.bundle


class MediaPipeBackendTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "models"
        cache_paths = MediaPipeResourcePaths(
            root_dir=root,
            mediapipe_dir=root / "mediapipe",
            downloads_dir=root / "mediapipe" / ".downloads",
        )
        self.resources = PreparedMediaPipeResources(
            face_detector_path=root / "mediapipe" / "face_detector.tflite",
            face_landmarker_path=root / "mediapipe" / "face_landmarker.task",
            pose_landmarker_path=root / "mediapipe" / "pose_landmarker.task",
            pose_model="full",
            cache_paths=cache_paths,
        )

    def _backend(
        self,
        *,
        media_type="image",
        max_heads=1,
        detections=(),
        face_results=(),
        pose_result=None,
        face_error=None,
    ):
        detector_result = SimpleNamespace(detections=list(detections))
        detector = FakeTask(
            image_results=[detector_result],
            video_results=[detector_result, detector_result],
        )
        face_landmarker = FakeTask(
            image_results=list(face_results),
            error=face_error,
        )
        if pose_result is None:
            pose_result = _pose_result()
        pose_landmarker = FakeTask(
            image_results=[pose_result],
            video_results=[pose_result, pose_result],
        )
        image_factory = FakeImageFactory()
        bundle = MediaPipeTaskBundle(
            face_detector=detector,
            face_landmarker=face_landmarker,
            pose_landmarker=pose_landmarker,
            image_factory=image_factory,
        )
        factory = RecordingTaskFactory(bundle)
        backend = MediaPipeBackend.create(
            self.resources,
            media_type=media_type,
            max_heads=max_heads,
            task_factory=factory,
        )
        return backend, bundle, factory

    def test_injected_factory_uses_expected_paths_and_running_modes(self):
        backend, _, factory = self._backend(media_type="video", max_heads=3)

        self.assertEqual(
            factory.calls,
            [
                {
                    "face_detector_path": self.resources.face_detector_path.resolve(),
                    "face_landmarker_path": self.resources.face_landmarker_path.resolve(),
                    "pose_landmarker_path": self.resources.pose_landmarker_path.resolve(),
                    "running_mode": "VIDEO",
                    "max_heads": 3,
                    "face_landmarker_running_mode": "IMAGE",
                }
            ],
        )
        backend.close()

    def test_image_mode_converts_once_and_uses_image_calls(self):
        detection = _detection(20, 20, 20, 20, 0.9)
        backend, bundle, _ = self._backend(
            detections=(detection,),
            face_results=(_face_result([_landmark(0.5, 0.5)]),),
        )
        frame = CountingFrame(Image.new("RGBA", (100, 100), (10, 20, 30, 40)))

        backend.observe(
            frame,
            frame_index=0,
            timestamp_ms=0.0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(frame.convert_calls, ["RGB"])
        self.assertEqual(len(bundle.image_factory.arrays), 2)
        self.assertEqual(bundle.image_factory.arrays[0].shape, (100, 100, 3))
        self.assertEqual(len(bundle.face_detector.image_calls), 1)
        self.assertEqual(len(bundle.pose_landmarker.image_calls), 1)
        self.assertIs(
            bundle.face_detector.image_calls[0],
            bundle.pose_landmarker.image_calls[0],
        )
        self.assertEqual(len(bundle.face_detector.video_calls), 0)
        self.assertEqual(len(bundle.pose_landmarker.video_calls), 0)
        self.assertEqual(len(bundle.face_landmarker.image_calls), 1)
        self.assertEqual(len(bundle.face_landmarker.video_calls), 0)
        backend.close()

    def test_video_mode_rounds_timestamps_and_requires_strict_increase(self):
        backend, bundle, _ = self._backend(media_type="video")
        frame = Image.new("RGB", (8, 8))

        backend.observe(
            frame,
            frame_index=0,
            timestamp_ms=10.6,
            image_width=8,
            image_height=8,
        )
        backend.observe(
            frame,
            frame_index=1,
            timestamp_ms=11.6,
            image_width=8,
            image_height=8,
        )

        self.assertEqual(
            [call[1] for call in bundle.face_detector.video_calls],
            [11, 12],
        )
        self.assertEqual(
            [call[1] for call in bundle.pose_landmarker.video_calls],
            [11, 12],
        )
        with self.assertRaisesRegex(ValueError, "strictly increase"):
            backend.observe(
                frame,
                frame_index=2,
                timestamp_ms=12.4,
                image_width=8,
                image_height=8,
            )
        backend.close()

    def test_face_crops_expand_and_landmarks_remap_to_full_frame(self):
        keypoint = _landmark(0.25, 0.35, z=0.1)
        detection = _detection(20, 20, 20, 20, 0.8, keypoints=(keypoint,))
        crop_landmark = _landmark(0.5, 0.5, z=0.25, visibility=0.8, presence=0.9)
        backend, bundle, _ = self._backend(
            detections=(detection,),
            face_results=(_face_result([crop_landmark], _identity_matrix()),),
        )

        result = backend.observe(
            Image.new("RGB", (100, 100)),
            frame_index=0,
            timestamp_ms=0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(bundle.image_factory.arrays[1].shape, (31, 28, 3))
        face = result.faces[0]
        self.assertEqual(face.bbox, (0.2, 0.2, 0.4, 0.4))
        self.assertEqual(face.keypoints[0].x, 0.25)
        self.assertEqual(face.keypoints[0].y, 0.35)
        self.assertAlmostEqual(face.landmarks[0].x, 0.30)
        self.assertAlmostEqual(face.landmarks[0].y, 0.275)
        self.assertAlmostEqual(face.landmarks[0].z, 0.07)
        self.assertEqual(face.landmarks[0].visibility, 0.8)
        self.assertEqual(face.landmarks[0].presence, 0.9)
        backend.close()

    def test_faces_are_sorted_by_confidence_before_max_heads_limit(self):
        detections = (
            _detection(10, 10, 10, 10, 0.2),
            _detection(30, 10, 10, 10, 0.9),
            _detection(50, 10, 10, 10, 0.7),
        )
        backend, bundle, _ = self._backend(
            max_heads=2,
            detections=detections,
            face_results=(_face_result(), _face_result()),
        )

        result = backend.observe(
            Image.new("RGB", (100, 100)),
            frame_index=0,
            timestamp_ms=0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual([face.confidence for face in result.faces], [0.9, 0.7])
        self.assertEqual([face.bbox[0] for face in result.faces], [0.3, 0.5])
        self.assertEqual(len(bundle.face_landmarker.image_calls), 2)
        backend.close()

    def test_crops_smaller_than_two_pixels_skip_face_landmarker(self):
        detection = _detection(0, 0, 0.1, 0.1, 0.9)
        backend, bundle, _ = self._backend(detections=(detection,))

        result = backend.observe(
            Image.new("RGB", (100, 100)),
            frame_index=0,
            timestamp_ms=0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(result.faces, ())
        self.assertEqual(bundle.face_landmarker.image_calls, [])
        backend.close()

    def test_all_478_face_landmarks_are_retained(self):
        landmarks = [_landmark(index / 1000.0, 0.5) for index in range(478)]
        backend, _, _ = self._backend(
            detections=(_detection(10, 10, 80, 80, 0.9),),
            face_results=(_face_result(landmarks),),
        )

        result = backend.observe(
            Image.new("RGB", (100, 100)),
            frame_index=0,
            timestamp_ms=0,
            image_width=100,
            image_height=100,
        )

        self.assertEqual(len(result.faces[0].landmarks), 478)
        backend.close()

    def test_pose_landmarks_and_world_landmarks_preserve_order_and_scores(self):
        poses = (
            (_landmark(0.1, 0.2, 0.3, 0.4, 0.5),),
            (_landmark(0.6, 0.7, 0.8, 0.9, 1.0),),
        )
        world = (
            (_landmark(1.1, 1.2, 1.3, 0.4, 0.5),),
            (_landmark(1.6, 1.7, 1.8, 0.9, 1.0),),
        )
        backend, _, _ = self._backend(pose_result=_pose_result(poses, world))

        result = backend.observe(
            Image.new("RGB", (10, 10)),
            frame_index=0,
            timestamp_ms=0,
            image_width=10,
            image_height=10,
        )

        self.assertEqual([pose.pose_index for pose in result.poses], [0, 1])
        self.assertEqual(result.poses[0].landmarks[0].visibility, 0.4)
        self.assertEqual(result.poses[1].world_landmarks[0].x, 1.6)
        backend.close()

    def test_transformation_matrices_use_display_oriented_euler_signs(self):
        for axis in ("yaw", "pitch", "roll"):
            with self.subTest(axis=axis):
                backend, _, _ = self._backend(
                    detections=(_detection(10, 10, 80, 80, 0.9),),
                    face_results=(
                        _face_result([_landmark(0.5, 0.5)], _rotation_matrix(axis, 20.0)),
                    ),
                )

                result = backend.observe(
                    Image.new("RGB", (100, 100)),
                    frame_index=0,
                    timestamp_ms=0,
                    image_width=100,
                    image_height=100,
                )

                angles = result.faces[0].head_pose
                self.assertIsNotNone(angles)
                expected = {"yaw": (20.0, 0.0, 0.0), "pitch": (0.0, 20.0, 0.0), "roll": (0.0, 0.0, 20.0)}[axis]
                self.assertAlmostEqual(angles.yaw_deg, expected[0], delta=1e-5)
                self.assertAlmostEqual(angles.pitch_deg, expected[1], delta=1e-5)
                self.assertAlmostEqual(angles.roll_deg, expected[2], delta=1e-5)
                self.assertEqual(result.faces[0].transformation_matrix, _rotation_matrix(axis, 20.0))
                backend.close()

    def test_timings_include_each_task_and_total(self):
        backend, _, _ = self._backend()

        result = backend.observe(
            Image.new("RGB", (8, 8)),
            frame_index=0,
            timestamp_ms=0,
            image_width=8,
            image_height=8,
        )

        self.assertEqual(
            set(result.timings_ms),
            {"face_detector", "face_landmarker", "pose_landmarker", "total"},
        )
        for timing in result.timings_ms.values():
            self.assertGreaterEqual(timing, 0.0)
        self.assertGreaterEqual(
            result.timings_ms["total"],
            result.timings_ms["face_detector"] + result.timings_ms["face_landmarker"],
        )
        backend.close()

    def test_close_is_idempotent_after_success(self):
        backend, bundle, _ = self._backend()
        backend.observe(
            Image.new("RGB", (8, 8)),
            frame_index=0,
            timestamp_ms=0,
            image_width=8,
            image_height=8,
        )

        backend.close()
        backend.close()

        self.assertEqual(bundle.face_detector.close_count, 1)
        self.assertEqual(bundle.face_landmarker.close_count, 1)
        self.assertEqual(bundle.pose_landmarker.close_count, 1)

    def test_partial_observe_failure_closes_every_task_exactly_once(self):
        backend, bundle, _ = self._backend(
            detections=(_detection(1, 1, 6, 6, 0.9),),
            face_error=ValueError("face landmarker failed"),
        )

        with self.assertRaisesRegex(ValueError, "face landmarker failed"):
            backend.observe(
                Image.new("RGB", (8, 8)),
                frame_index=0,
                timestamp_ms=0,
                image_width=8,
                image_height=8,
            )
        backend.close()

        self.assertEqual(bundle.face_detector.close_count, 1)
        self.assertEqual(bundle.face_landmarker.close_count, 1)
        self.assertEqual(bundle.pose_landmarker.close_count, 1)

    def test_partial_native_construction_closes_created_tasks(self):
        detector = FakeTask()
        face_landmarker = FakeTask()

        class Creator:
            def __init__(self, result=None, error=None):
                self.result = result
                self.error = error

            def create_from_options(self, options):
                if self.error is not None:
                    raise self.error
                return self.result

        class Options:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        fake_mp = SimpleNamespace(
            tasks=SimpleNamespace(
                BaseOptions=Options,
                vision=SimpleNamespace(
                    RunningMode=SimpleNamespace(IMAGE="IMAGE", VIDEO="VIDEO"),
                    FaceDetectorOptions=Options,
                    FaceLandmarkerOptions=Options,
                    PoseLandmarkerOptions=Options,
                    FaceDetector=Creator(result=detector),
                    FaceLandmarker=Creator(result=face_landmarker),
                    PoseLandmarker=Creator(error=RuntimeError("pose construction failed")),
                ),
            ),
            Image=lambda **kwargs: kwargs,
            ImageFormat=SimpleNamespace(SRGB="SRGB"),
        )

        with patch(
            "gazelle.runtime.perception.mediapipe_backend.import_mediapipe",
            return_value=fake_mp,
        ):
            with self.assertRaisesRegex(RuntimeError, "pose construction failed"):
                MediaPipeBackend.create(
                    self.resources,
                    media_type="image",
                    max_heads=1,
                )

        self.assertEqual(detector.close_count, 1)
        self.assertEqual(face_landmarker.close_count, 1)

    def test_missing_mediapipe_fails_only_for_real_construction(self):
        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "mediapipe":
                raise ModuleNotFoundError("No module named 'mediapipe'", name="mediapipe")
            return real_import(name, *args, **kwargs)

        injected_backend, _, _ = self._backend()
        injected_backend.close()
        with patch("builtins.__import__", side_effect=blocked_import):
            with self.assertRaisesRegex(
                RuntimeError,
                "MediaPipe head detection requires the 'mediapipe' package",
            ):
                MediaPipeBackend.create(
                    self.resources,
                    media_type="image",
                    max_heads=1,
                )


if __name__ == "__main__":
    unittest.main()
