import math

from gazelle.runtime.outputs import JsonlWriter


def _finite_float(value, field_name):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("{} must be finite".format(field_name)) from error
    if not math.isfinite(number):
        raise ValueError("{} must be finite".format(field_name))
    return number


def _finite_int(value, field_name):
    _finite_float(value, field_name)
    return int(value)


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
        "person_id": _finite_int(perception.person_id, "person_id"),
        "head_bbox_normalized": _optional_float_list(
            perception.head_bbox,
            "head_bbox_normalized",
        ),
        "confidence": _optional_float(perception.confidence, "confidence"),
        "state": perception.state.value,
        "view_state": perception.view_state.value,
        "observed": bool(perception.observed),
        "tracking": {
            "track_age_frames": _finite_int(perception.track_age_frames, "track_age_frames"),
            "missed_frames": _finite_int(perception.missed_frames, "missed_frames"),
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
        "person_id": _finite_int(head.person_id, "person_id"),
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
    perceptions = tuple(result.perceptions)
    people = (
        [
            _perception_to_json_dict(
                perception,
                save_face_landmarks=save_face_landmarks,
            )
            for perception in perceptions
        ]
        if perceptions
        else [_head_to_json_dict(head) for head in result.heads]
    )
    return {
        "frame_index": _finite_int(frame_index, "frame_index"),
        "timestamp_ms": _finite_float(timestamp_ms, "timestamp_ms"),
        "status": "ok" if result.heads else "no_head",
        "width": _finite_int(image_width, "width"),
        "height": _finite_int(image_height, "height"),
        "provider": str(provider),
        "timings_ms": {
            str(key): _finite_float(value, "timings_ms.{}".format(key))
            for key, value in result.timings_ms.items()
        },
        "people": people,
    }


def write_head_observations_json(writer: JsonlWriter, **kwargs):
    """Serialize and append one head-observation record through ``JsonlWriter``."""
    record = head_frame_to_json_dict(**kwargs)
    writer.write(record)
    return record
