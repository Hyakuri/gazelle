import unittest
import math
import numpy as np

from gazelle.runtime.perception.contracts import (
    HeadPoseAngles,
    NormalizedLandmark,
    PoseHeadKeypoints,
    ReferenceRayProjectionStatus,
    ReferenceRaySource,
)
from gazelle.runtime.perception.reference_rays import (
    estimate_face_pose_reference_ray,
    estimate_pose_head_reference_ray,
)
from gazelle.runtime.perception.mediapipe_backend import _matrix_to_head_pose


def point(x, y, *, visibility=0.9, presence=0.9):
    return NormalizedLandmark(
        x=x,
        y=y,
        visibility=visibility,
        presence=presence,
    )


class ReferenceRayTest(unittest.TestCase):
    def face_ray(self,angles):
        return estimate_face_pose_reference_ray(head_bbox=(.2,.1,.8,.9),
            face_keypoints=(point(.45,.4),point(.55,.4),point(.5,.5)),head_pose=angles,confidence=.9)

    def test_matrix_projection_matches_display_direction_for_compound_rotations(self):
        for yaw,pitch,roll in ((20,30,15),(-35,25,-40),(15,-20,45),(89,12,-17),(90,30,15),(-90,20,-10)):
            with self.subTest(yaw=yaw,pitch=pitch,roll=roll):
                y,p,r=map(math.radians,(yaw,pitch,roll))
                rx=np.array([[1,0,0],[0,math.cos(p),-math.sin(p)],[0,math.sin(p),math.cos(p)]])
                ry=np.array([[math.cos(y),0,math.sin(y)],[0,1,0],[-math.sin(y),0,math.cos(y)]])
                rz=np.array([[math.cos(r),-math.sin(r),0],[math.sin(r),math.cos(r),0],[0,0,1]])
                matrix=rz@ry@rx
                angles=_matrix_to_head_pose(matrix)
                ray=self.face_ray(angles)
                expected=np.array([matrix[0,2],-matrix[1,2]])
                expected/=np.linalg.norm(expected)
                np.testing.assert_allclose(ray.direction,expected,atol=1e-6,rtol=0)
                if abs(yaw)<90:
                    self.assertAlmostEqual(angles.roll_deg,-roll)

    def test_display_pitch_yaw_and_clockwise_roll_signs(self):
        self.assertGreater(self.face_ray(HeadPoseAngles(0,30,0)).direction[1],0)
        self.assertLess(self.face_ray(HeadPoseAngles(0,-30,0)).direction[1],0)
        self.assertGreater(self.face_ray(HeadPoseAngles(30,0,0)).direction[0],0)
        np.testing.assert_allclose(self.face_ray(HeadPoseAngles(30,0,90)).direction,(0,1),atol=1e-6)

    def test_face_and_pose_downward_reference_signs_agree(self):
        face=self.face_ray(HeadPoseAngles(0,30,0))
        pose=estimate_pose_head_reference_ray(head_bbox=(.2,.1,.8,.9),confidence=.9,
            keypoints=PoseHeadKeypoints(nose=point(.5,.55),left_eye=point(.45,.4),right_eye=point(.55,.4)))
        self.assertGreater(face.direction[1],0)
        self.assertGreater(pose.direction[1],0)

    def test_face_ray_uses_head_pose_and_face_keypoint_origin(self):
        ray = estimate_face_pose_reference_ray(
            head_bbox=(0.3, 0.2, 0.7, 0.8),
            face_keypoints=(
                point(0.44, 0.40),
                point(0.56, 0.40),
                point(0.53, 0.50),
            ),
            head_pose=HeadPoseAngles(yaw_deg=30.0, pitch_deg=0.0, roll_deg=0.0),
            confidence=0.9,
            length_multiplier=2.0,
        )

        self.assertEqual(ray.source, ReferenceRaySource.FACE_POSE)
        self.assertEqual(ray.projection_status, ReferenceRayProjectionStatus.AVAILABLE)
        self.assertAlmostEqual(ray.origin[0], 0.5)
        self.assertAlmostEqual(ray.origin[1], 0.4)
        self.assertGreater(ray.direction[0], 0.99)
        self.assertAlmostEqual(ray.direction[1], 0.0)
        self.assertGreater(ray.endpoint[0], ray.origin[0])

    def test_face_ray_marks_near_frontal_projection_as_axial(self):
        ray = estimate_face_pose_reference_ray(
            head_bbox=(0.3, 0.2, 0.7, 0.8),
            face_keypoints=(
                point(0.44, 0.40),
                point(0.56, 0.40),
                point(0.50, 0.50),
            ),
            head_pose=HeadPoseAngles(yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0),
            confidence=0.9,
        )

        self.assertEqual(ray.projection_status, ReferenceRayProjectionStatus.AXIAL)
        self.assertIsNone(ray.direction)
        self.assertIsNone(ray.endpoint)

    def test_face_ray_requires_current_face_keypoints(self):
        self.assertIsNone(
            estimate_face_pose_reference_ray(
                head_bbox=(0.3, 0.2, 0.7, 0.8),
                face_keypoints=(),
                head_pose=HeadPoseAngles(yaw_deg=20.0, pitch_deg=0.0, roll_deg=0.0),
                confidence=0.9,
            )
        )

    def test_face_ray_uses_face_bbox_center_when_eye_pair_is_unavailable(self):
        invalid_eye = point(float("nan"), 0.40)
        ray = estimate_face_pose_reference_ray(
            head_bbox=(0.2, 0.1, 0.8, 0.9),
            face_bbox=(0.4, 0.3, 0.6, 0.7),
            face_keypoints=(
                invalid_eye,
                invalid_eye,
                point(0.50, 0.48),
                point(0.50, 0.58),
                point(0.42, 0.50),
                point(0.58, 0.50),
            ),
            head_pose=HeadPoseAngles(yaw_deg=25.0, pitch_deg=0.0, roll_deg=0.0),
            confidence=0.9,
        )

        self.assertIsNotNone(ray)
        self.assertEqual(ray.origin, (0.5, 0.5))

    def test_pose_ray_is_computed_independently_from_pose_keypoints(self):
        ray = estimate_pose_head_reference_ray(
            head_bbox=(0.3, 0.2, 0.7, 0.8),
            keypoints=PoseHeadKeypoints(
                nose=point(0.56, 0.47),
                left_eye=point(0.46, 0.40),
                right_eye=point(0.54, 0.40),
            ),
            confidence=0.85,
            length_multiplier=2.0,
        )

        self.assertEqual(ray.source, ReferenceRaySource.POSE_HEAD)
        self.assertEqual(ray.projection_status, ReferenceRayProjectionStatus.AVAILABLE)
        self.assertGreater(ray.direction[0], 0.0)
        self.assertIsNotNone(ray.endpoint)

    def test_pose_ray_requires_nose_and_bilateral_anchor(self):
        ray = estimate_pose_head_reference_ray(
            head_bbox=(0.3, 0.2, 0.7, 0.8),
            keypoints=PoseHeadKeypoints(
                nose=point(0.50, 0.47),
                left_eye=point(0.46, 0.40),
            ),
            confidence=0.85,
        )

        self.assertIsNone(ray)

    def test_ray_endpoint_is_clipped_to_image_boundary(self):
        ray = estimate_face_pose_reference_ray(
            head_bbox=(0.85, 0.3, 0.99, 0.7),
            face_keypoints=(
                point(0.90, 0.40),
                point(0.96, 0.40),
                point(0.97, 0.48),
            ),
            head_pose=HeadPoseAngles(yaw_deg=60.0, pitch_deg=0.0, roll_deg=0.0),
            confidence=0.9,
            length_multiplier=20.0,
        )

        self.assertAlmostEqual(ray.endpoint[0], 1.0)
        self.assertGreaterEqual(ray.endpoint[1], 0.0)
        self.assertLessEqual(ray.endpoint[1], 1.0)

    def test_reference_ray_length_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "length_multiplier"):
            estimate_face_pose_reference_ray(
                head_bbox=(0.3, 0.2, 0.7, 0.8),
                face_keypoints=(
                    point(0.44, 0.40),
                    point(0.56, 0.40),
                    point(0.53, 0.50),
                ),
                head_pose=HeadPoseAngles(yaw_deg=30.0, pitch_deg=0.0, roll_deg=0.0),
                confidence=0.9,
                length_multiplier=0.0,
            )


if __name__ == "__main__":
    unittest.main()
