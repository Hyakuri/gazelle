import json
import math
from numbers import Real
from pathlib import Path

from gazelle.runtime.perception.contracts import HeadPerceptionState, HeadViewState


def _finite_float(value, field_name):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("{} must be finite".format(field_name)) from error
    if not math.isfinite(number):
        raise ValueError("{} must be finite".format(field_name))
    return number


def _exact_int(value, field_name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("{} must be an integer".format(field_name))
    try:
        integer = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("{} must be an integer".format(field_name)) from error
    try:
        is_exact = bool(value == integer)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("{} must be an integer".format(field_name)) from error
    if not is_exact:
        raise ValueError("{} must be an integer".format(field_name))
    return integer


def _exact_bool(value, field_name):
    if type(value) is not bool:
        raise ValueError("{} must be bool".format(field_name))
    return value


def _enum_value(value, enum_type, field_name):
    if type(value) is not enum_type:
        raise ValueError("{} must be a {} member".format(field_name, enum_type.__name__))
    return value.value


def _optional_float(value, field_name):
    if value is None:
        return None
    return _finite_float(value, field_name)


def _optional_float_list(values, field_name):
    if values is None:
        return None
    return [
        _finite_float(value, "{}[{}]".format(field_name, index))
        for index, value in enumerate(values)
    ]


def _landmark_to_json_dict(landmark, field_name):
    record = {
        "x": _finite_float(landmark.x, "{}.x".format(field_name)),
        "y": _finite_float(landmark.y, "{}.y".format(field_name)),
    }
    for attribute in ("z", "visibility", "presence"):
        value = getattr(landmark, attribute)
        if value is not None:
            record[attribute] = _finite_float(value, "{}.{}".format(field_name, attribute))
    return record


def _perception_to_json_dict(perception, *, save_face_landmarks):
    record = {
        "person_id": _exact_int(perception.person_id, "person_id"),
        "head_bbox_normalized": _optional_float_list(
            perception.head_bbox,
            "head_bbox_normalized",
        ),
        "confidence": _optional_float(perception.confidence, "confidence"),
        "state": _enum_value(perception.state, HeadPerceptionState, "state"),
        "view_state": _enum_value(perception.view_state, HeadViewState, "view_state"),
        "observed": _exact_bool(perception.observed, "observed"),
        "tracking": {
            "track_age_frames": _exact_int(perception.track_age_frames, "track_age_frames"),
            "missed_frames": _exact_int(perception.missed_frames, "missed_frames"),
            "missed_ms": _finite_float(perception.missed_ms, "missed_ms"),
        },
    }
    if perception.face_bbox is not None:
        record["face_bbox_normalized"] = _optional_float_list(
            perception.face_bbox,
            "face_bbox_normalized",
        )
    if perception.face_keypoints:
        record["face_keypoints"] = [
            _landmark_to_json_dict(keypoint, "face_keypoints[{}]".format(index))
            for index, keypoint in enumerate(perception.face_keypoints)
        ]
    if perception.pose_head_landmarks:
        record["pose_head_landmarks"] = [
            _landmark_to_json_dict(landmark, "pose_head_landmarks[{}]".format(index))
            for index, landmark in enumerate(perception.pose_head_landmarks)
        ]
    if perception.facial_transformation_matrix is not None:
        record["facial_transformation_matrix"] = [
            _optional_float_list(row, "facial_transformation_matrix[{}]".format(row_index))
            for row_index, row in enumerate(perception.facial_transformation_matrix)
        ]
    if perception.head_pose is not None:
        record["head_pose"] = {
            "yaw_deg": _finite_float(perception.head_pose.yaw_deg, "head_pose.yaw_deg"),
            "pitch_deg": _finite_float(perception.head_pose.pitch_deg, "head_pose.pitch_deg"),
            "roll_deg": _finite_float(perception.head_pose.roll_deg, "head_pose.roll_deg"),
        }
    if save_face_landmarks and perception.face_landmarks:
        record["face_landmarks"] = [
            _landmark_to_json_dict(landmark, "face_landmarks[{}]".format(index))
            for index, landmark in enumerate(perception.face_landmarks)
        ]
    return record


def _head_to_json_dict(head):
    return {
        "person_id": _exact_int(head.person_id, "person_id"),
        "head_bbox_normalized": _optional_float_list(head.bbox, "head_bbox_normalized"),
        "confidence": _optional_float(head.confidence, "confidence"),
    }


def head_frame_to_json_dict(
    *,
    frame_index,
    timestamp_ms,
    image_width,
    image_height,
    provider,
    result,
    save_face_landmarks=False,
):
    """Serialize one independent head-provider result into a JSON-safe record."""
    save_face_landmarks = _exact_bool(save_face_landmarks, "save_face_landmarks")
    heads = tuple(result.heads)
    perceptions = tuple(result.perceptions)
    if perceptions:
        if len(perceptions) != len(heads):
            raise ValueError("result.heads and result.perceptions must have the same length")
        people = []
        for index, (head, perception) in enumerate(zip(heads, perceptions)):
            head_record = _head_to_json_dict(head)
            perception_record = _perception_to_json_dict(
                perception,
                save_face_landmarks=save_face_landmarks,
            )
            for field_name in ("person_id", "head_bbox_normalized", "confidence"):
                if perception_record[field_name] != head_record[field_name]:
                    raise ValueError(
                        "result.perceptions at index {} must match result.heads for {}".format(
                            index,
                            field_name,
                        )
                    )
            people.append(perception_record)
    else:
        people = [_head_to_json_dict(head) for head in heads]
    return {
        "frame_index": _exact_int(frame_index, "frame_index"),
        "timestamp_ms": _finite_float(timestamp_ms, "timestamp_ms"),
        "status": "ok" if heads else "no_head",
        "width": _exact_int(image_width, "width"),
        "height": _exact_int(image_height, "height"),
        "provider": str(provider),
        "timings_ms": {
            str(key): _finite_float(value, "timings_ms.{}".format(key))
            for key, value in result.timings_ms.items()
        },
        "people": people,
    }


def write_head_observations_json(output_path, **kwargs):
    """Serialize one image head-observation record as an indented JSON document."""
    record = head_frame_to_json_dict(**kwargs)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return record
