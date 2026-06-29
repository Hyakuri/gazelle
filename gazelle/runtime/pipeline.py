from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
from time import perf_counter
from typing import Callable, List, Optional, Tuple

from gazelle.runtime.contracts import GazePrediction, HeadObservation
from gazelle.runtime.heads import (
    NoneHeadProvider,
    StaticHeadProvider,
    load_json_head_provider,
)
from gazelle.runtime.media import (
    VideoFrameReader,
    VideoFrameWriter,
    load_image_rgb,
    resolve_video_fps,
)
from gazelle.runtime.outputs import (
    JsonlWriter,
    prediction_frame_to_json_dict,
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


@dataclass(frozen=True)
class VideoPipelineResult:
    output_dir: Path
    predictions_jsonl_path: Path
    run_config_path: Path
    rendered_video_path: Optional[Path]
    frames_read: int
    frames_written: int


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
    from gazelle.runtime.environment import temporarily_disable_xformers_for_cpu_device
    from gazelle.runtime.predictor import GazellePredictor, resolve_torch_device
    from gazelle.runtime.resources import prepare_runtime_resources

    resolved_device = resolve_torch_device(config.device)
    with temporarily_disable_xformers_for_cpu_device(resolved_device):
        if config.checkpoint:
            checkpoint_path = config.checkpoint
        else:
            prepared = prepare_runtime_resources(config)
            checkpoint_path = prepared.checkpoint_path

        # TODO: avoid double model construction by sharing prepared model in a future optimization.
        return GazellePredictor.from_checkpoint(
            config.model,
            checkpoint_path,
            device=str(resolved_device),
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


def _render_options_from_config(config) -> RenderOptions:
    return RenderOptions(
        heatmap_alpha=config.heatmap_alpha,
        draw_heatmap=config.draw_heatmap,
        draw_head_box=config.draw_head_box,
        draw_gaze_peak=config.draw_gaze_peak,
        draw_gaze_arrow=config.draw_gaze_arrow,
        draw_heatmap_contour=config.draw_heatmap_contour,
        draw_labels=config.draw_labels,
        heatmap_contour_quantile=config.heatmap_contour_quantile,
        heatmap_contour_width=config.heatmap_contour_width,
    )


def _video_run_config_payload(
    config,
    *,
    input_path,
    width: int,
    height: int,
    source_fps: float,
    output_fps: Optional[float],
    frames_read: int,
    frames_written: int,
):
    payload = asdict(config)
    payload.update(
        {
            "input_path": str(input_path),
            "width": int(width),
            "height": int(height),
            "source_fps": float(source_fps),
            "output_fps": None if output_fps is None else float(output_fps),
            "frames_read": int(frames_read),
            "frames_written": int(frames_written),
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
        renderer = PredictionRenderer(_render_options_from_config(config))
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


def run_video_pipeline(config, predictor_factory: Optional[Callable[[object], object]] = None) -> VideoPipelineResult:
    if config.save_heatmaps:
        raise ValueError("video heatmap export is not implemented yet")

    with VideoFrameReader(config.input_path) as reader:
        metadata = reader.metadata
        output_dir = create_output_dir(
            config.input_path,
            config.output_dir,
            overwrite=config.overwrite,
        )
        head_provider = build_head_provider_from_config(config)
        predictor = predictor_factory(config) if predictor_factory is not None else _build_real_predictor(config)

        predictions_jsonl_path = output_dir / "predictions.jsonl"
        run_config_path = output_dir / "run_config.json"
        rendered_video_path = None
        writer = None
        renderer = None
        if config.save_rendered:
            video_fps = resolve_video_fps(metadata.fps, config.output_fps)
            rendered_video_path = output_dir / config.output_video_name
            writer = VideoFrameWriter(
                rendered_video_path,
                width=metadata.width,
                height=metadata.height,
                fps=video_fps,
            )
            renderer = PredictionRenderer(
                _render_options_from_config(config)
            )

        frames_read = 0
        frames_written = 0
        try:
            with JsonlWriter(predictions_jsonl_path) as jsonl_writer:
                frame_iterator = iter(reader)
                while config.max_frames is None or frames_written < config.max_frames:
                    try:
                        frame = next(frame_iterator)
                    except StopIteration:
                        break
                    frames_read += 1

                    if frame.index % config.frame_step != 0:
                        predictions: Tuple[GazePrediction, ...] = ()
                        record = prediction_frame_to_json_dict(
                            frame_index=frame.index,
                            timestamp_ms=frame.timestamp_ms,
                            status="skipped",
                            image_width=metadata.width,
                            image_height=metadata.height,
                            predictions=predictions,
                        )
                        jsonl_writer.write(record)
                        if writer is not None:
                            writer.write(frame.image)
                        frames_written += 1
                        continue

                    heads = tuple(
                        head_provider.get_heads(
                            frame=frame.image,
                            frame_index=frame.index,
                            timestamp_ms=frame.timestamp_ms,
                            image_width=metadata.width,
                            image_height=metadata.height,
                        )
                    )
                    if not heads:
                        predictions = ()
                        record = prediction_frame_to_json_dict(
                            frame_index=frame.index,
                            timestamp_ms=frame.timestamp_ms,
                            status="no_head",
                            image_width=metadata.width,
                            image_height=metadata.height,
                            predictions=predictions,
                        )
                        jsonl_writer.write(record)
                        if writer is not None:
                            writer.write(frame.image)
                        frames_written += 1
                        continue

                    start_time = perf_counter()
                    predictions = tuple(predictor.predict_frame(frame.image, heads))
                    inference_ms = (perf_counter() - start_time) * 1000.0
                    record = prediction_frame_to_json_dict(
                        frame_index=frame.index,
                        timestamp_ms=frame.timestamp_ms,
                        status="ok",
                        image_width=metadata.width,
                        image_height=metadata.height,
                        predictions=predictions,
                        inference_ms=inference_ms,
                    )
                    jsonl_writer.write(record)
                    if writer is not None:
                        rendered = renderer.render(frame.image, predictions)
                        writer.write(rendered)
                    frames_written += 1
        finally:
            if writer is not None:
                writer.close()

        write_run_config_json(
            run_config_path,
            _video_run_config_payload(
                config,
                input_path=config.input_path,
                width=metadata.width,
                height=metadata.height,
                source_fps=metadata.fps,
                output_fps=resolve_video_fps(metadata.fps, config.output_fps),
                frames_read=frames_read,
                frames_written=frames_written,
            ),
        )

    return VideoPipelineResult(
        output_dir=output_dir,
        predictions_jsonl_path=predictions_jsonl_path,
        run_config_path=run_config_path,
        rendered_video_path=rendered_video_path,
        frames_read=frames_read,
        frames_written=frames_written,
    )
