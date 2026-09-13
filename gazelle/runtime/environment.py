from contextlib import contextmanager
import importlib.util
import os
import sys


_DINOV2_XFORMERS_MODULES = (
    "dinov2.layers.attention",
    "dinov2.layers.block",
    "dinov2.layers.swiglu_ffn",
)


@contextmanager
def temporarily_disable_xformers():
    previous = os.environ.get("XFORMERS_DISABLED")
    os.environ["XFORMERS_DISABLED"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("XFORMERS_DISABLED", None)
        else:
            os.environ["XFORMERS_DISABLED"] = previous


@contextmanager
def temporarily_disable_xformers_for_cpu_device(device):
    if getattr(device, "type", None) != "cpu":
        yield
        return

    with temporarily_disable_xformers():
        yield


@contextmanager
def temporarily_disable_missing_triton_for_cuda_device(device):
    if getattr(device, "type", None) != "cuda":
        yield
        return
    if os.environ.get("XFORMERS_FORCE_DISABLE_TRITON") is not None:
        yield
        return
    if os.environ.get("XFORMERS_ENABLE_TRITON") == "1":
        yield
        return

    try:
        triton_available = importlib.util.find_spec("triton") is not None
    except (AttributeError, ImportError, ValueError):
        triton_available = False
    if triton_available:
        yield
        return

    os.environ["XFORMERS_FORCE_DISABLE_TRITON"] = "1"
    try:
        yield
    finally:
        os.environ.pop("XFORMERS_FORCE_DISABLE_TRITON", None)


def _loaded_dinov2_uses_xformers():
    states = []
    for module_name in _DINOV2_XFORMERS_MODULES:
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "XFORMERS_AVAILABLE"):
            states.append(bool(module.XFORMERS_AVAILABLE))
    if not states:
        return None
    return any(states)


@contextmanager
def configure_dinov2_model_construction(device=None, *, force_disable_xformers=False):
    wants_xformers = (
        not force_disable_xformers
        and getattr(device, "type", None) == "cuda"
        and os.environ.get("XFORMERS_DISABLED") is None
    )
    loaded_uses_xformers = _loaded_dinov2_uses_xformers()
    if loaded_uses_xformers is True and not wants_xformers:
        raise RuntimeError(
            "DINOv2 is already initialized with xFormers enabled; cannot construct "
            "an xFormers-disabled model in the same process. Start a fresh process "
            "for CPU or prepare-only model construction."
        )
    if loaded_uses_xformers is False and wants_xformers:
        raise RuntimeError(
            "DINOv2 is already initialized without xFormers; cannot enable xFormers "
            "in the same process. Start a fresh process for CUDA model construction."
        )

    if force_disable_xformers:
        with temporarily_disable_xformers():
            yield
        return

    with temporarily_disable_xformers_for_cpu_device(device):
        with temporarily_disable_missing_triton_for_cuda_device(device):
            yield
