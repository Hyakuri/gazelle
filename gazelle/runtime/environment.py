from contextlib import contextmanager
import os


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
