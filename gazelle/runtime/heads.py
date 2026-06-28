import json
import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from numbers import Real
from pathlib import Path
from typing import Optional, Tuple

from gazelle.runtime.contracts import BBox, HeadObservation
from gazelle.runtime.geometry import pixel_bbox_to_normalized, sanitize_normalized_bbox


SUPPORTED_BBOX_FORMATS = ("normalized", "pixel")


class HeadProvider(ABC):
    @abstractmethod
    def get_heads(
        self,
        frame,
        frame_index: int,
        timestamp_ms: float,
        image_width: int,
        image_height: int,
    ) -> Tuple[HeadObservation, ...]:
        raise NotImplementedError


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_person_id(value, *, field_name: str = "person_id") -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("{} must be an int".format(field_name))
    return value


def validate_confidence(value):
    if not _is_finite_real(value):
        raise ValueError("confidence must be a finite real number")
    return float(value)


def parse_bbox_format(value) -> str:
    if value not in SUPPORTED_BBOX_FORMATS:
        raise ValueError("bbox_format must be one of: {}".format(", ".join(SUPPORTED_BBOX_FORMATS)))
    return value


def validate_frame_index(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("frame_index must be a non-negative int")
    return value


def validate_timestamp_ms(value):
    if not _is_finite_real(value):
        raise ValueError("timestamp_ms must be a finite real number")
    return float(value)


def _normalize_bboxes_input(bboxes) -> Tuple[BBox, ...]:
    try:
        items = tuple(bboxes)
    except TypeError as exc:
        raise ValueError("bboxes must be an iterable of one or more bboxes") from exc
    if not items:
        raise ValueError("bboxes must not be empty")

    if len(items) == 4 and not any(isinstance(value, (list, tuple, dict)) for value in items):
        return (items,)
    return items


def _validate_optional_sequence(values, expected_length: int, field_name: str):
    if values is None:
        return None
    values = tuple(values)
    if len(values) != expected_length:
        raise ValueError("{} length must match bboxes length".format(field_name))
    return values


def _bbox_to_normalized(bbox, bbox_format: str, image_width: int, image_height: int) -> BBox:
    if bbox_format == "normalized":
        return sanitize_normalized_bbox(bbox)
    if bbox_format == "pixel":
        return pixel_bbox_to_normalized(bbox, image_width=image_width, image_height=image_height)
    raise ValueError("bbox_format must be one of: {}".format(", ".join(SUPPORTED_BBOX_FORMATS)))


class NoneHeadProvider(HeadProvider):
    def __init__(self, person_id: int = 0):
        self.person_id = validate_person_id(person_id)

    def get_heads(
        self,
        frame,
        frame_index: int,
        timestamp_ms: float,
        image_width: int,
        image_height: int,
    ) -> Tuple[HeadObservation, ...]:
        return (HeadObservation(person_id=self.person_id, bbox=None, confidence=None),)


class StaticHeadProvider(HeadProvider):
    def __init__(
        self,
        bboxes,
        bbox_format: str = "normalized",
        person_ids=None,
        confidences=None,
    ):
        self.bboxes = _normalize_bboxes_input(bboxes)
        self.bbox_format = parse_bbox_format(bbox_format)
        self.person_ids = _validate_optional_sequence(person_ids, len(self.bboxes), "person_ids")
        self.confidences = _validate_optional_sequence(confidences, len(self.bboxes), "confidences")

        if self.person_ids is not None:
            self.person_ids = tuple(validate_person_id(value) for value in self.person_ids)
        if self.confidences is not None:
            self.confidences = tuple(validate_confidence(value) for value in self.confidences)

    def get_heads(
        self,
        frame,
        frame_index: int,
        timestamp_ms: float,
        image_width: int,
        image_height: int,
    ) -> Tuple[HeadObservation, ...]:
        heads = []
        for index, bbox in enumerate(self.bboxes):
            try:
                normalized_bbox = _bbox_to_normalized(bbox, self.bbox_format, image_width, image_height)
            except ValueError as exc:
                raise ValueError(
                    "Invalid bbox at index {} with bbox_format '{}': {}".format(
                        index,
                        self.bbox_format,
                        exc,
                    )
                ) from exc
            person_id = self.person_ids[index] if self.person_ids is not None else index
            confidence = self.confidences[index] if self.confidences is not None else None
            heads.append(
                HeadObservation(
                    person_id=person_id,
                    bbox=normalized_bbox,
                    confidence=confidence,
                )
            )
        return tuple(heads)


def _normalize_frame_records(frame_records):
    if isinstance(frame_records, Mapping):
        return ((frame_records, True),)
    if isinstance(frame_records, (list, tuple)):
        return tuple((record, False) for record in frame_records)
    raise ValueError("frame_records must be a frame record dict or a list of frame records")


def _validate_frame_record(raw_record, *, allow_default_frame_index: bool):
    if not isinstance(raw_record, Mapping):
        raise ValueError("frame record must be a JSON object")
    if "frame_index" in raw_record:
        frame_index = validate_frame_index(raw_record["frame_index"])
    elif allow_default_frame_index:
        frame_index = 0
    else:
        raise ValueError("frame_index is required for JSON list/video records")

    if "timestamp_ms" in raw_record:
        try:
            validate_timestamp_ms(raw_record["timestamp_ms"])
        except ValueError as exc:
            raise ValueError("frame_index {} invalid timestamp_ms: {}".format(frame_index, exc)) from exc
    try:
        bbox_format = parse_bbox_format(raw_record.get("bbox_format", "normalized"))
    except ValueError as exc:
        raise ValueError("frame_index {} invalid bbox_format: {}".format(frame_index, exc)) from exc

    if "heads" not in raw_record:
        raise ValueError("frame_index {} record must contain heads".format(frame_index))
    heads = raw_record["heads"]
    if not isinstance(heads, list):
        raise ValueError("frame_index {} heads must be a list".format(frame_index))

    return {
        "frame_index": frame_index,
        "bbox_format": bbox_format,
        "heads": heads,
    }


def build_head_observation(
    raw_head,
    *,
    default_person_id: int,
    bbox_format: str,
    image_width: int,
    image_height: int,
    frame_index: int,
    head_index: int,
) -> HeadObservation:
    if not isinstance(raw_head, Mapping):
        raise ValueError("frame_index {} head {} must be a JSON object".format(frame_index, head_index))

    try:
        person_id = validate_person_id(raw_head.get("person_id", default_person_id))
    except ValueError as exc:
        raise ValueError("frame_index {} head {} invalid person_id: {}".format(frame_index, head_index, exc)) from exc

    confidence = None
    if "confidence" in raw_head:
        try:
            confidence = validate_confidence(raw_head["confidence"])
        except ValueError as exc:
            raise ValueError(
                "frame_index {} head {} invalid confidence: {}".format(frame_index, head_index, exc)
            ) from exc

    try:
        head_bbox_format = parse_bbox_format(raw_head.get("bbox_format", bbox_format))
    except ValueError as exc:
        raise ValueError(
            "frame_index {} head {} invalid bbox_format: {}".format(frame_index, head_index, exc)
        ) from exc
    if "bbox" not in raw_head:
        raise ValueError("frame_index {} head {} must contain bbox".format(frame_index, head_index))
    raw_bbox = raw_head["bbox"]
    if raw_bbox is None:
        normalized_bbox = None
    else:
        try:
            normalized_bbox = _bbox_to_normalized(raw_bbox, head_bbox_format, image_width, image_height)
        except ValueError as exc:
            raise ValueError(
                "frame_index {} head {} invalid bbox with bbox_format '{}': {}".format(
                    frame_index,
                    head_index,
                    head_bbox_format,
                    exc,
                )
            ) from exc

    return HeadObservation(person_id=person_id, bbox=normalized_bbox, confidence=confidence)


class JsonHeadProvider(HeadProvider):
    def __init__(self, frame_records):
        self.records_by_frame_index = {}
        for raw_record, allow_default_frame_index in _normalize_frame_records(frame_records):
            record = _validate_frame_record(
                raw_record,
                allow_default_frame_index=allow_default_frame_index,
            )
            frame_index = record["frame_index"]
            if frame_index in self.records_by_frame_index:
                raise ValueError("duplicate frame_index {}".format(frame_index))
            self.records_by_frame_index[frame_index] = record

    def get_heads(
        self,
        frame,
        frame_index: int,
        timestamp_ms: float,
        image_width: int,
        image_height: int,
    ) -> Tuple[HeadObservation, ...]:
        frame_index = validate_frame_index(frame_index)
        record = self.records_by_frame_index.get(frame_index)
        if record is None:
            return ()

        heads = []
        for head_index, raw_head in enumerate(record["heads"]):
            heads.append(
                build_head_observation(
                    raw_head,
                    default_person_id=head_index,
                    bbox_format=record["bbox_format"],
                    image_width=image_width,
                    image_height=image_height,
                    frame_index=frame_index,
                    head_index=head_index,
                )
            )
        return tuple(heads)


def _load_jsonl_records(path: Path):
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("Malformed JSONL at line {}: {}".format(line_number, exc.msg)) from exc
            if not isinstance(record, Mapping):
                raise ValueError("JSONL line {} must contain a JSON object".format(line_number))
            records.append(record)
    return records


def load_json_head_provider(path) -> JsonHeadProvider:
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        return JsonHeadProvider(_load_jsonl_records(path))

    with path.open("r", encoding="utf-8") as handle:
        try:
            frame_records = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed JSON file: {}".format(exc.msg)) from exc
    return JsonHeadProvider(frame_records)
