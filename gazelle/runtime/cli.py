import argparse
import sys
from typing import Optional, Sequence, TextIO

from gazelle.runtime.config import RuntimeConfig
from gazelle.runtime.model_registry import format_model_table, supported_model_names


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
        "--model",
        default="gazelle_dinov2_vitb14_inout",
        choices=supported_model_names(),
        help="Gazelle model to use. This does not load DINOv2 unless runtime preparation is requested.",
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

    parser = build_parser()
    parser.error("no runtime action selected yet; use --list-models in this milestone")
    return 2
