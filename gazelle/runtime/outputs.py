import json
from pathlib import Path
from typing import List, Optional, Sequence

import torch


def _optional_float(value):
    return None if value is None else float(value)


def _optional_float_list(values):
    if values is None:
        return None
    return [float(value) for value in values]


def _json_safe(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def prediction_to_json_dict(prediction, *, heatmap_path=None) -> dict:
    record = {
        "person_id": prediction.person_id,
        "bbox_normalized": _optional_float_list(prediction.bbox),
        "gaze_peak_normalized": _optional_float_list(prediction.gaze_peak),
        "heatmap_peak_value": _optional_float(prediction.heatmap_peak_value),
        "inout_score": _optional_float(prediction.inout_score),
    }
    if heatmap_path is not None:
        record["heatmap_path"] = str(heatmap_path)
    return record


def write_predictions_json(
    output_path,
    *,
    input_path,
    image_width,
    image_height,
    model_name,
    heads,
    predictions,
    heatmap_paths: Optional[Sequence[str]] = None,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    heads = tuple(heads)
    predictions = tuple(predictions)
    if len(predictions) != len(heads):
        raise ValueError("predictions length must match heads length")
    if heatmap_paths is not None and len(heatmap_paths) != len(predictions):
        raise ValueError("heatmap_paths length must match predictions length")

    people = []
    for index, prediction in enumerate(predictions):
        heatmap_path = None if heatmap_paths is None else heatmap_paths[index]
        people.append(prediction_to_json_dict(prediction, heatmap_path=heatmap_path))

    payload = {
        "input": str(input_path),
        "width": int(image_width),
        "height": int(image_height),
        "model": model_name,
        "people": people,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_run_config_json(output_path, config_dict) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_json_safe(config_dict), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_prediction_heatmaps(heatmaps_dir, predictions) -> List[str]:
    heatmaps_dir = Path(heatmaps_dir)
    heatmaps_dir.mkdir(parents=True, exist_ok=True)
    relative_paths = []
    seen_person_ids = {}
    for index, prediction in enumerate(predictions):
        if prediction.heatmap is None:
            raise ValueError("Prediction at index {} does not contain a heatmap".format(index))
        person_id = prediction.person_id
        count = seen_person_ids.get(person_id, 0)
        seen_person_ids[person_id] = count + 1
        suffix = "" if count == 0 else "_{}".format(count)
        filename = "person_{}{}.pt".format(person_id, suffix)
        torch.save(prediction.heatmap, heatmaps_dir / filename)
        relative_paths.append((Path(heatmaps_dir.name) / filename).as_posix())
    return relative_paths
