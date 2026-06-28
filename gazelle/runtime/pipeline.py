from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from gazelle.runtime.contracts import GazePrediction, HeadObservation
from gazelle.runtime.heads import (
    NoneHeadProvider,
    StaticHeadProvider,
    load_json_head_provider,
)
from gazelle.runtime.media import load_image_rgb
from gazelle.runtime.outputs import (
    save_prediction_heatmaps,
    write_predictions_json,
    write_run_config_json,
)


@dataclass(frozen=True)
class ImagePipelineResult:
    output_dir: Path
    predictions_path: Path
    run_config_path: Path
    heatmap_paths: Tuple[str, ...]
    heads: Tuple[HeadObservation, ...]
    predictions: Tuple[GazePrediction, ...]


def build_head_provider_from_config(config):
    if config.head_source == "none":
        return NoneHeadProvider()
    if config.head_source == "static":
        if not config.bboxes:
            raise ValueError("--head-source static requires at least one --bbox")
        return StaticHeadProvider(
            bboxes=config.bboxes,
            bbox_format=config.bbox_format,
            person_ids=config.person_ids,
        )
    if config.head_source == "json":
        if not config.head_data:
            raise ValueError("--head-source json requires --head-data")
        return load_json_head_provider(config.head_data)
    raise ValueError("Unknown head source: {}".format(config.head_source))


def create_output_dir(input_path, output_dir, overwrite: bool = False) -> Path:
    input_path = Path(input_path)
    output_root = Path(output_dir)
    output_path = output_root / "{}_gazelle".format(input_path.stem)
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            "Output directory already exists: {}. Use --overwrite to reuse it.".format(output_path)
        )
    output_path.mkdir(parents=True, exist_ok=overwrite)
    return output_path


def _build_real_predictor(config):
    from gazelle.runtime.predictor import GazellePredictor
    from gazelle.runtime.resources import prepare_runtime_resources

    if config.checkpoint:
        checkpoint_path = config.checkpoint
    else:
        prepared = prepare_runtime_resources(config)
        checkpoint_path = prepared.checkpoint_path

    # TODO: avoid double model construction by sharing prepared model in a future optimization.
    return GazellePredictor.from_checkpoint(
        config.model,
        checkpoint_path,
        device=config.device,
        cache_dir=config.cache_dir,
    )


def _run_config_payload(config, *, input_path, image_width: int, image_height: int):
    payload = asdict(config)
    payload.update(
        {
            "input_path": str(input_path),
            "image_width": int(image_width),
            "image_height": int(image_height),
        }
    )
    return payload


def run_image_pipeline(config, predictor_factory: Optional[Callable[[object], object]] = None) -> ImagePipelineResult:
    image, width, height = load_image_rgb(config.input_path)
    output_dir = create_output_dir(config.input_path, config.output_dir, overwrite=config.overwrite)

    head_provider = build_head_provider_from_config(config)
    heads = tuple(
        head_provider.get_heads(
            frame=image,
            frame_index=0,
            timestamp_ms=0.0,
            image_width=width,
            image_height=height,
        )
    )

    predictor = predictor_factory(config) if predictor_factory is not None else _build_real_predictor(config)
    predictions = tuple(predictor.predict_frame(image, heads))

    heatmap_paths: List[str] = []
    if config.save_heatmaps:
        heatmap_paths = save_prediction_heatmaps(output_dir / "heatmaps", predictions)

    predictions_path = output_dir / "predictions.json"
    run_config_path = output_dir / "run_config.json"
    write_predictions_json(
        predictions_path,
        input_path=config.input_path,
        image_width=width,
        image_height=height,
        model_name=config.model,
        heads=heads,
        predictions=predictions,
        heatmap_paths=heatmap_paths if config.save_heatmaps else None,
    )
    write_run_config_json(
        run_config_path,
        _run_config_payload(
            config,
            input_path=config.input_path,
            image_width=width,
            image_height=height,
        ),
    )

    return ImagePipelineResult(
        output_dir=output_dir,
        predictions_path=predictions_path,
        run_config_path=run_config_path,
        heatmap_paths=tuple(heatmap_paths),
        heads=heads,
        predictions=predictions,
    )
