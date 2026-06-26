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
        help="Image or video input path. Full inference pipeline will be added in a later milestone.",
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
        help="Delete the registered cached checkpoint and download it again.",
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
        stdout.write("Prepared Gazelle resources for {}\n".format(prepared.model_name))
        stdout.write("checkpoint: {}\n".format(prepared.checkpoint_path))
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

    parser = build_parser()
    parser.error("no runtime action selected yet; use --list-models in this milestone")
    return 2
