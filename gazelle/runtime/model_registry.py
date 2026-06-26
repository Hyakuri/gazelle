from dataclasses import dataclass
from typing import Iterable, Optional, Tuple


RELEASE_BASE_URL = "https://github.com/fkryan/gazelle/releases/download/v1.0.0"


@dataclass(frozen=True)
class CheckpointCandidate:
    """A checkpoint URL observed in current public docs or hubconf."""

    source: str
    filename: str
    url: str


@dataclass(frozen=True)
class ModelSpec:
    """Static model metadata that can be listed without constructing DINOv2."""

    name: str
    backbone_name: str
    supports_inout: bool
    input_size: Tuple[int, int]
    checkpoint_candidates: Tuple[CheckpointCandidate, ...]

    @property
    def has_ambiguous_checkpoint(self) -> bool:
        return len(self.checkpoint_candidates) != 1


def _candidate(source: str, filename: str) -> CheckpointCandidate:
    return CheckpointCandidate(
        source=source,
        filename=filename,
        url="{}/{}".format(RELEASE_BASE_URL, filename),
    )


MODEL_SPECS = (
    ModelSpec(
        name="gazelle_dinov2_vitb14",
        backbone_name="dinov2_vitb14",
        supports_inout=False,
        input_size=(448, 448),
        checkpoint_candidates=(
            _candidate("README", "gazelle_dinov2_vitb14.pt"),
        ),
    ),
    ModelSpec(
        name="gazelle_dinov2_vitl14",
        backbone_name="dinov2_vitl14",
        supports_inout=False,
        input_size=(448, 448),
        checkpoint_candidates=(
            _candidate("README/hubconf.py", "gazelle_dinov2_vitl14.pt"),
        ),
    ),
    ModelSpec(
        name="gazelle_dinov2_vitb14_inout",
        backbone_name="dinov2_vitb14",
        supports_inout=True,
        input_size=(448, 448),
        checkpoint_candidates=(
            _candidate("README/hubconf.py", "gazelle_dinov2_vitb14_inout.pt"),
        ),
    ),
    ModelSpec(
        name="gazelle_dinov2_vitl14_inout",
        backbone_name="dinov2_vitl14",
        supports_inout=True,
        input_size=(448, 448),
        checkpoint_candidates=(
            _candidate("README/hubconf.py", "gazelle_dinov2_vitl14_inout.pt"),
        ),
    ),
)

_MODEL_SPECS_BY_NAME = {spec.name: spec for spec in MODEL_SPECS}


def iter_model_specs() -> Iterable[ModelSpec]:
    return iter(MODEL_SPECS)


def supported_model_names() -> Tuple[str, ...]:
    return tuple(spec.name for spec in MODEL_SPECS)


def get_model_spec(model_name: str) -> ModelSpec:
    try:
        return _MODEL_SPECS_BY_NAME[model_name]
    except KeyError:
        supported = ", ".join(supported_model_names())
        raise ValueError("Unknown Gazelle model '{}'. Supported models: {}".format(model_name, supported))


def describe_checkpoint(spec: ModelSpec) -> str:
    if len(spec.checkpoint_candidates) == 1:
        return spec.checkpoint_candidates[0].filename
    return "AMBIGUOUS: {}".format(
        ", ".join(candidate.filename for candidate in spec.checkpoint_candidates)
    )


def format_model_table(specs: Optional[Iterable[ModelSpec]] = None) -> str:
    specs = list(specs if specs is not None else iter_model_specs())
    lines = [
        "Available Gazelle models:",
        "",
        "{:<32} {:<16} {:<7} {}".format("name", "backbone", "inout", "checkpoint"),
        "{:<32} {:<16} {:<7} {}".format("-" * 32, "-" * 16, "-" * 7, "-" * 10),
    ]
    for spec in specs:
        lines.append(
            "{:<32} {:<16} {:<7} {}".format(
                spec.name,
                spec.backbone_name,
                "yes" if spec.supports_inout else "no",
                describe_checkpoint(spec),
            )
        )
    return "\n".join(lines) + "\n"
