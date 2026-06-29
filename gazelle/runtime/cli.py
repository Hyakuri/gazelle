import argparse
import sys
from typing import Optional, Sequence, TextIO

from gazelle.runtime.config import RuntimeConfig
from gazelle.runtime.model_registry import format_model_table


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Unified local Gazelle inference runtime.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List locally registered Gazelle model names and exit without loading models.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help=(
            "Prepare the Gazelle checkpoint and DINOv2 Torch Hub cache, then exit without "
            "running image or video inference."
        ),
    )
    parser.add_argument(
        "--model",
        default="gazelle_dinov2_vitb14_inout",
        help=(
            "Gazelle model to use. Run --list-models to see supported names. "
            "This does not load DINOv2 unless runtime preparation is requested."
        ),
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Image or video input path for local Gazelle inference.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Output root directory. A per-input subdirectory is created inside it.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow reuse of an existing per-input output directory.",
    )
    parser.add_argument(
        "--head-source",
        choices=("none", "static", "json"),
        default="none",
        help="Head input source for image or video inference.",
    )
    parser.add_argument(
        "--bbox",
        action="append",
        nargs=4,
        type=float,
        metavar=("XMIN", "YMIN", "XMAX", "YMAX"),
        help="Static head bbox. Can be repeated. Interpreted using --bbox-format.",
    )
    parser.add_argument(
        "--bbox-format",
        choices=("normalized", "pixel"),
        default="normalized",
        help="Coordinate format for --bbox values.",
    )
    parser.add_argument(
        "--person-id",
        action="append",
        type=int,
        help="Optional person id for each --bbox. Can be repeated and must match --bbox count.",
    )
    parser.add_argument(
        "--head-data",
        default=None,
        help="JSON or JSONL head data file for --head-source json.",
    )
    parser.add_argument(
        "--save-heatmaps",
        action="store_true",
        help="Save raw per-person heatmap tensors for image inference. Not supported for video.",
    )
    parser.add_argument(
        "--save-rendered",
        action="store_true",
        help="Save a rendered visual overlay image or video.",
    )
    parser.add_argument(
        "--rendered-name",
        default="rendered.png",
        help="Rendered image file name written inside the per-image output directory.",
    )
    parser.add_argument(
        "--output-video-name",
        default="rendered.mp4",
        help="Rendered video file name written inside the per-video output directory.",
    )
    parser.add_argument(
        "--output-fps",
        type=float,
        default=None,
        help="Fallback output FPS for video rendering when the source FPS is invalid.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional maximum number of video frames to process and write.",
    )
    parser.add_argument(
        "--frame-step",
        type=int,
        default=1,
        help="Run video inference every N frames; skipped frames are still written to JSONL.",
    )
    parser.add_argument(
        "--heatmap-alpha",
        type=float,
        default=0.45,
        help="Rendered heatmap overlay alpha in [0, 1].",
    )
    parser.add_argument(
        "--no-heatmap",
        action="store_true",
        help="Do not draw heatmap overlays in rendered output.",
    )
    parser.add_argument(
        "--head-box",
        action="store_true",
        help="Draw head bounding boxes in rendered output when bboxes are available.",
    )
    parser.add_argument(
        "--no-gaze-peak",
        action="store_true",
        help="Do not draw gaze peak markers in rendered output.",
    )
    parser.add_argument(
        "--no-gaze-arrow",
        action="store_true",
        help="Do not draw head-center to gaze-peak arrows in rendered output.",
    )
    parser.add_argument(
        "--draw-heatmap-contour",
        action="store_true",
        help="Draw a contour around high-response heatmap regions in rendered output.",
    )
    parser.add_argument(
        "--heatmap-contour-quantile",
        type=float,
        default=0.90,
        help="Heatmap quantile threshold for --draw-heatmap-contour in [0, 1].",
    )
    parser.add_argument(
        "--heatmap-contour-width",
        type=int,
        default=None,
        help="Heatmap contour line width in rendered output.",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Do not draw person labels in rendered output.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Runtime device: auto, cpu, cuda, or cuda:<index>.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Runtime cache root. Defaults to GAZELLE_CACHE_DIR, then models/.",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Use a local checkpoint path instead of downloading the registered checkpoint.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Refresh the registered cached checkpoint after a successful temporary download.",
    )
    return parser


def parse_runtime_config(argv: Optional[Sequence[str]] = None) -> RuntimeConfig:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return RuntimeConfig.from_args(args)
    except ValueError as exc:
        parser.error(str(exc))


def main(argv: Optional[Sequence[str]] = None, stdout: Optional[TextIO] = None) -> int:
    stdout = stdout if stdout is not None else sys.stdout
    config = parse_runtime_config(argv)
    if config.list_models:
        stdout.write(format_model_table())
        return 0
    if config.prepare_only:
        from gazelle.runtime.resources import prepare_runtime_resources

        prepared = prepare_runtime_resources(config)
        checkpoint_source = (
            "local" if prepared.checkpoint_candidate is None else prepared.checkpoint_candidate.source
        )
        stdout.write("Prepared Gazelle resources for {}\n".format(prepared.model_name))
        stdout.write("checkpoint: {}\n".format(prepared.checkpoint_path))
        stdout.write("checkpoint_source: {}\n".format(checkpoint_source))
        stdout.write("cache_dir: {}\n".format(prepared.cache_paths.root_dir))
        stdout.write("torch_hub_dir: {}\n".format(prepared.cache_paths.torch_hub_dir))
        for result in prepared.candidate_results:
            stdout.write(
                "candidate: {} strict_load={} size={} sha256={}{}\n".format(
                    result.candidate.filename,
                    "yes" if result.strict_load_success else "no",
                    result.size_bytes if result.size_bytes is not None else "unknown",
                    result.sha256 if result.sha256 is not None else "unknown",
                    "" if result.error is None else " error={}".format(result.error),
                )
            )
        return 0

    if config.input_path:
        from gazelle.runtime.media import detect_media_type
        from gazelle.runtime.pipeline import run_image_pipeline, run_video_pipeline

        media_type = detect_media_type(config.input_path)
        if media_type == "image":
            result = run_image_pipeline(config)
            stdout.write("Wrote Gazelle image inference outputs to {}\n".format(result.output_dir))
            stdout.write("predictions: {}\n".format(result.predictions_path))
            stdout.write("run_config: {}\n".format(result.run_config_path))
            if result.rendered_path is not None:
                stdout.write("rendered: {}\n".format(result.rendered_path))
        elif media_type == "video":
            result = run_video_pipeline(config)
            stdout.write("Wrote Gazelle video inference outputs to {}\n".format(result.output_dir))
            stdout.write("predictions_jsonl: {}\n".format(result.predictions_jsonl_path))
            stdout.write("run_config: {}\n".format(result.run_config_path))
            if result.rendered_video_path is not None:
                stdout.write("rendered_video: {}\n".format(result.rendered_video_path))
            stdout.write("frames_read: {}\n".format(result.frames_read))
            stdout.write("frames_written: {}\n".format(result.frames_written))
        else:
            raise ValueError("Unsupported media type: {}".format(media_type))
        return 0

    parser = build_parser()
    parser.error("no runtime action selected; use --list-models, --prepare-only, or --input")
    return 2
