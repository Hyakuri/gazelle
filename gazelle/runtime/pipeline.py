from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
from time import perf_counter
from typing import Callable, List, Optional, Tuple

from gazelle.runtime.contracts import GazePrediction, HeadObservation
from gazelle.runtime.ffmpeg import (
    TemporaryVideoPath,
    detect_ffmpeg_capabilities,
    transcode_h264,
)
from gazelle.runtime.heads import (
    NoneHeadProvider,
    StaticHeadProvider,
    load_json_head_provider,
)
from gazelle.runtime.perception.contracts import HeadFrameResult
from gazelle.runtime.perception.gaze_policy import (
    apply_prediction_gaze_status,
    select_gazelle_heads,
)
from gazelle.runtime.perception.outputs import (
    head_frame_to_json_dict,
    write_head_observations_json,
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
    head_observations_path: Path
    run_config_path: Path
    rendered_path: Optional[Path]
    heatmap_paths: Tuple[str, ...]
    heads: Tuple[HeadObservation, ...]
    head_result: HeadFrameResult
    predictions: Tuple[GazePrediction, ...]


@dataclass(frozen=True)
class VideoPipelineResult:
    output_dir: Path
    predictions_jsonl_path: Path
    head_observations_jsonl_path: Path
    run_config_path: Path
    rendered_video_path: Optional[Path]
    frames_read: int
    frames_written: int


def build_head_provider_from_config(
    config,
    media_type: str = "image",
    source_fps: float = 30.0,
    backend_factory=None,
    tracker_factory=None,
):
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
    if config.head_source == "mediapipe":
        from gazelle.runtime.perception.provider import MediaPipeHeadProvider

        return MediaPipeHeadProvider.create(
            config,
            media_type=media_type,
            source_fps=source_fps,
            backend_factory=backend_factory,
            tracker_factory=tracker_factory,
        )
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
    from gazelle.runtime.predictor import GazellePredictor, resolve_torch_device
    from gazelle.runtime.resources import resolve_runtime_checkpoint

    resolved_device = resolve_torch_device(config.device)
    checkpoint = resolve_runtime_checkpoint(config)
    return GazellePredictor.from_checkpoint(
        config.model,
        checkpoint.checkpoint_path,
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
        draw_face_box=config.draw_face_box,
        draw_face_keypoints=config.draw_face_keypoints,
        draw_pose_head_points=config.draw_pose_head_points,
        draw_face_mesh=config.draw_face_mesh,
        draw_track_state=config.draw_track_state,
        draw_face_pose_ray=config.draw_face_pose_ray,
        draw_pose_head_ray=config.draw_pose_head_ray,
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


def _attach_cleanup_context(primary_error, resource_name: str, cleanup_error) -> None:
    add_note = getattr(primary_error, "add_note", None)
    if callable(add_note):
        add_note("{} cleanup also failed: {!r}".format(resource_name, cleanup_error))


def _close_video_resources(resources, primary_error) -> None:
    first_cleanup_error = None
    for resource_name, resource in resources:
        if resource is None:
            continue
        close = getattr(resource, "close", None)
        if not callable(close):
            continue
        try:
            close()
        except BaseException as cleanup_error:
            if primary_error is not None:
                _attach_cleanup_context(primary_error, resource_name, cleanup_error)
            elif first_cleanup_error is None:
                first_cleanup_error = cleanup_error
            else:
                _attach_cleanup_context(first_cleanup_error, resource_name, cleanup_error)
    if primary_error is None and first_cleanup_error is not None:
        raise first_cleanup_error


def run_image_pipeline(config, predictor_factory: Optional[Callable[[object], object]] = None) -> ImagePipelineResult:
    image, width, height = load_image_rgb(config.input_path)
    output_dir = create_output_dir(config.input_path, config.output_dir, overwrite=config.overwrite)

    with build_head_provider_from_config(config, media_type="image") as head_provider:
        head_result = head_provider.get_frame_result(
            image,
            0,
            0.0,
            width,
            height,
        )
        head_observations_path = output_dir / "head_observations.json"
        write_head_observations_json(
            head_observations_path,
            frame_index=0,
            timestamp_ms=0.0,
            image_width=width,
            image_height=height,
            provider=config.head_source,
            result=head_result,
            save_face_landmarks=config.save_face_landmarks,
        )
        gazelle_heads = select_gazelle_heads(head_result)
        if gazelle_heads:
            predictor = (
                predictor_factory(config)
                if predictor_factory is not None
                else _build_real_predictor(config)
            )
            predictions = apply_prediction_gaze_status(
                predictor.predict_frame(image, gazelle_heads),
                inout_threshold=config.gaze_inout_threshold,
            )
        else:
            predictions = ()

    heatmap_paths: List[str] = []
    if config.save_heatmaps:
        heatmap_paths = save_prediction_heatmaps(output_dir / "heatmaps", predictions)

    rendered_path = None
    if config.save_rendered:
        renderer = PredictionRenderer(_render_options_from_config(config))
        rendered = renderer.render(
            image,
            predictions,
            head_result.perceptions,
        )
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
        heads=gazelle_heads,
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
        head_observations_path=head_observations_path,
        run_config_path=run_config_path,
        rendered_path=rendered_path,
        heatmap_paths=tuple(heatmap_paths),
        heads=head_result.heads,
        head_result=head_result,
        predictions=predictions,
    )


def run_video_pipeline(config, predictor_factory: Optional[Callable[[object], object]] = None) -> VideoPipelineResult:
    if config.save_heatmaps:
        raise ValueError("video heatmap export is not implemented yet")

    ffmpeg_capabilities = None
    if config.save_rendered and config.video_codec == "avc1":
        ffmpeg_capabilities = detect_ffmpeg_capabilities()

    reader = None
    head_provider = None
    writer = None
    rendered_source = None
    head_jsonl_writer = None
    gaze_jsonl_writer = None
    primary_error = None
    try:
        reader = VideoFrameReader(config.input_path)
        metadata = reader.metadata
        output_dir = create_output_dir(
            config.input_path,
            config.output_dir,
            overwrite=config.overwrite,
        )
        video_fps = resolve_video_fps(metadata.fps, config.output_fps)
        head_provider = build_head_provider_from_config(
            config,
            media_type="video",
            source_fps=video_fps,
        )
        predictor = None

        predictions_jsonl_path = output_dir / "predictions.jsonl"
        head_observations_jsonl_path = output_dir / "head_observations.jsonl"
        run_config_path = output_dir / "run_config.json"
        rendered_video_path = None
        renderer = None
        if config.save_rendered:
            rendered_video_path = output_dir / config.output_video_name
            if config.video_codec == "avc1":
                rendered_source = TemporaryVideoPath.beside(
                    rendered_video_path,
                    "source",
                )
                writer_path = rendered_source.path
            else:
                writer_path = rendered_video_path
            writer = VideoFrameWriter(
                writer_path,
                width=metadata.width,
                height=metadata.height,
                fps=video_fps,
            )
            renderer = PredictionRenderer(_render_options_from_config(config))

        head_jsonl_writer = JsonlWriter(head_observations_jsonl_path)
        gaze_jsonl_writer = JsonlWriter(predictions_jsonl_path)
        frames_read = 0
        frames_written = 0
        frame_iterator = iter(reader)
        while config.max_frames is None or frames_written < config.max_frames:
            try:
                frame = next(frame_iterator)
            except StopIteration:
                break
            frames_read += 1

            head_result = head_provider.get_frame_result(
                frame.image,
                frame.index,
                frame.timestamp_ms,
                metadata.width,
                metadata.height,
            )
            head_jsonl_writer.write(
                head_frame_to_json_dict(
                    frame_index=frame.index,
                    timestamp_ms=frame.timestamp_ms,
                    image_width=metadata.width,
                    image_height=metadata.height,
                    provider=config.head_source,
                    result=head_result,
                    save_face_landmarks=config.save_face_landmarks,
                )
            )

            inference_ms = None
            gazelle_heads = select_gazelle_heads(head_result)
            if frame.index % config.frame_step != 0:
                status = "skipped"
                predictions: Tuple[GazePrediction, ...] = ()
            elif not head_result.heads:
                status = "no_head"
                predictions = ()
            elif not gazelle_heads:
                status = "no_gaze"
                predictions = ()
            else:
                if predictor is None:
                    predictor = (
                        predictor_factory(config)
                        if predictor_factory is not None
                        else _build_real_predictor(config)
                    )
                start_time = perf_counter()
                predictions = apply_prediction_gaze_status(
                    predictor.predict_frame(frame.image, gazelle_heads),
                    inout_threshold=config.gaze_inout_threshold,
                )
                inference_ms = (perf_counter() - start_time) * 1000.0
                status = "ok"

            gaze_jsonl_writer.write(
                prediction_frame_to_json_dict(
                    frame_index=frame.index,
                    timestamp_ms=frame.timestamp_ms,
                    status=status,
                    image_width=metadata.width,
                    image_height=metadata.height,
                    predictions=predictions,
                    inference_ms=inference_ms,
                )
            )
            if writer is not None:
                output_frame = renderer.render(
                    frame.image,
                    predictions,
                    head_result.perceptions,
                )
                writer.write(output_frame)
            frames_written += 1

        write_run_config_json(
            run_config_path,
            _video_run_config_payload(
                config,
                input_path=config.input_path,
                width=metadata.width,
                height=metadata.height,
                source_fps=metadata.fps,
                output_fps=video_fps,
                frames_read=frames_read,
                frames_written=frames_written,
            ),
        )
        if writer is not None:
            writer.close()
            writer = None
        if rendered_source is not None:
            transcode_h264(
                rendered_source.path,
                rendered_video_path,
                ffmpeg_capabilities,
            )
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        _close_video_resources(
            (
                ("gaze JSONL writer", gaze_jsonl_writer),
                ("head observation JSONL writer", head_jsonl_writer),
                ("video writer", writer),
                ("rendered video source", rendered_source),
                ("provider", head_provider),
                ("reader", reader),
            ),
            primary_error,
        )

    return VideoPipelineResult(
        output_dir=output_dir,
        predictions_jsonl_path=predictions_jsonl_path,
        head_observations_jsonl_path=head_observations_jsonl_path,
        run_config_path=run_config_path,
        rendered_video_path=rendered_video_path,
        frames_read=frames_read,
        frames_written=frames_written,
    )
