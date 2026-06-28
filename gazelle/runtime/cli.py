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
        help="Single image input path for local Gazelle inference.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Output root directory for image inference. A per-image subdirectory is created inside it.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow reuse of an existing per-image output directory.",
    )
    parser.add_argument(
        "--head-source",
        choices=("none", "static", "json"),
        default="none",
        help="Head input source for single-image inference.",
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
        help="Save raw per-person heatmap tensors alongside predictions.json.",
    )
    parser.add_argument(
        "--save-rendered",
        action="store_true",
        help="Save a rendered visual overlay image for single-image inference.",
    )
    parser.add_argument(
        "--rendered-name",
        default="rendered.png",
        help="Rendered image file name written inside the per-image output directory.",
    )
    parser.add_argument(
        "--heatmap-alpha",
        type=float,
        default=0.45,
        help="Rendered heatmap overlay alpha in [0, 1].",
    )
    parser.add_argument(
        "--no-head-box",
        action="store_true",
        help="Do not draw head bounding boxes in rendered image output.",
    )
    parser.add_argument(
        "--no-gaze-peak",
        action="store_true",
        help="Do not draw gaze peak markers in rendered image output.",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Do not draw person labels in rendered image output.",
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
        from gazelle.runtime.pipeline import run_image_pipeline

        result = run_image_pipeline(config)
        stdout.write("Wrote Gazelle image inference outputs to {}\n".format(result.output_dir))
        stdout.write("predictions: {}\n".format(result.predictions_path))
        stdout.write("run_config: {}\n".format(result.run_config_path))
        if result.rendered_path is not None:
            stdout.write("rendered: {}\n".format(result.rendered_path))
        return 0

    parser = build_parser()
    parser.error("no runtime action selected; use --list-models, --prepare-only, or --input")
    return 2
