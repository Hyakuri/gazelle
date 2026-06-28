from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
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
from gazelle.runtime.renderer import PredictionRenderer, RenderOptions, save_rendered_image


@dataclass(frozen=True)
class ImagePipelineResult:
    output_dir: Path
    predictions_path: Path
    run_config_path: Path
    rendered_path: Optional[Path]
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


def _is_dangerous_output_path(output_path: Path) -> bool:
    return str(output_path) in ("", ".", output_path.anchor)


def _safe_clear_output_dir(output_path: Path, output_root: Path) -> None:
    if _is_dangerous_output_path(output_path):
        raise ValueError("Refusing to clean unsafe output directory: {}".format(output_path))
    if not output_path.name.endswith("_gazelle"):
        raise ValueError("Refusing to clean non-Gazelle output directory: {}".format(output_path))

    output_root_resolved = output_root.resolve(strict=False)
    output_path_resolved = output_path.resolve(strict=False)
    if output_path_resolved == output_root_resolved:
        raise ValueError("Refusing to clean output root directly: {}".format(output_path))
    try:
        output_path_resolved.relative_to(output_root_resolved)
    except ValueError as exc:
        raise ValueError(
            "Refusing to clean output directory outside output root: {}".format(output_path)
        ) from exc

    if output_path.exists() and not output_path.is_dir():
        raise ValueError("Refusing to overwrite non-directory output path: {}".format(output_path))
    if output_path.exists():
        shutil.rmtree(output_path)


def create_output_dir(
    input_path,
    output_dir,
    overwrite: bool = False,
    clean_on_overwrite: bool = True,
) -> Path:
    input_path = Path(input_path)
    output_root = Path(output_dir)
    output_path = output_root / "{}_gazelle".format(input_path.stem)
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            "Output directory already exists: {}. Use --overwrite to reuse it.".format(output_path)
        )
    if output_path.exists() and overwrite and clean_on_overwrite:
        _safe_clear_output_dir(output_path, output_root)
    output_path.mkdir(parents=True, exist_ok=True)
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

    rendered_path = None
    if config.save_rendered:
        renderer = PredictionRenderer(
            RenderOptions(
                heatmap_alpha=config.heatmap_alpha,
                draw_head_box=config.draw_head_box,
                draw_gaze_peak=config.draw_gaze_peak,
                draw_labels=config.draw_labels,
            )
        )
        rendered = renderer.render(image, predictions)
        rendered_path = output_dir / config.rendered_name
        save_rendered_image(rendered_path, rendered)

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
        rendered_path=rendered_path,
        heatmap_paths=tuple(heatmap_paths),
        heads=heads,
        predictions=predictions,
    )
