from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Optional, Tuple
from uuid import uuid4


SUPPORTED_H264_ENCODERS = ("h264_nvenc", "libx264")


@dataclass(frozen=True)
class FFmpegCapabilities:
    executable: str
    encoders: Tuple[str, ...]

    @property
    def encoder_order(self) -> Tuple[str, ...]:
        return tuple(
            encoder
            for encoder in SUPPORTED_H264_ENCODERS
            if encoder in self.encoders
        )


@dataclass(frozen=True)
class TemporaryVideoPath:
    path: Path

    @classmethod
    def beside(
        cls,
        final_path,
        role: str,
        token: Optional[str] = None,
    ) -> "TemporaryVideoPath":
        final_path = Path(final_path)
        token = uuid4().hex if token is None else str(token)
        path = final_path.with_name(
            ".{}.{}.{}{}".format(
                final_path.stem,
                role,
                token,
                final_path.suffix,
            )
        )
        return cls(path=path)

    def close(self) -> None:
        self.path.unlink(missing_ok=True)


def _completed_output(completed) -> str:
    return "\n".join(
        value.strip()
        for value in (
            getattr(completed, "stdout", "") or "",
            getattr(completed, "stderr", "") or "",
        )
        if value.strip()
    )


def detect_ffmpeg_capabilities(
    *,
    executable_name: str = "ffmpeg",
    which=None,
    runner=None,
) -> FFmpegCapabilities:
    if which is None:
        which = shutil.which
    if runner is None:
        runner = subprocess.run

    executable = which(executable_name)
    if executable is None:
        raise RuntimeError(
            "FFmpeg is required for --video-codec avc1 but was not found on PATH."
        )

    command = [str(executable), "-hide_banner", "-encoders"]
    try:
        completed = runner(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(
            "FFmpeg encoder probe failed to start: {}".format(exc)
        ) from exc

    output = _completed_output(completed)
    if completed.returncode != 0:
        raise RuntimeError(
            "FFmpeg encoder probe failed with return code {}: {}".format(
                completed.returncode,
                output or "no diagnostic output",
            )
        )

    output_tokens = set(output.split())
    encoders = tuple(
        encoder
        for encoder in SUPPORTED_H264_ENCODERS
        if encoder in output_tokens
    )
    if not encoders:
        raise RuntimeError(
            "FFmpeg does not provide a supported H.264 encoder; "
            "expected h264_nvenc or libx264."
        )

    return FFmpegCapabilities(
        executable=str(executable),
        encoders=encoders,
    )


def _transcode_command(
    executable: str,
    source_path: Path,
    candidate_path: Path,
    encoder: str,
):
    return [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-an",
        "-c:v",
        encoder,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(candidate_path),
    ]


def transcode_h264(
    source_path,
    final_path,
    capabilities: FFmpegCapabilities,
    *,
    runner=None,
) -> str:
    if runner is None:
        runner = subprocess.run

    source_path = Path(source_path)
    final_path = Path(final_path)
    encoder_order = capabilities.encoder_order
    if not encoder_order:
        raise RuntimeError("No supported FFmpeg H.264 encoder is available.")

    candidate = TemporaryVideoPath.beside(final_path, "candidate")
    failures = []
    try:
        for encoder in encoder_order:
            candidate.close()
            command = _transcode_command(
                capabilities.executable,
                source_path,
                candidate.path,
                encoder,
            )
            try:
                completed = runner(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            except OSError as exc:
                failures.append("{} failed to start: {}".format(encoder, exc))
                continue

            if completed.returncode != 0:
                failures.append(
                    "{} return code {}: {}".format(
                        encoder,
                        completed.returncode,
                        _completed_output(completed) or "no diagnostic output",
                    )
                )
                continue

            if not candidate.path.exists():
                raise RuntimeError(
                    "FFmpeg encoding with {} completed but output file was not found: {}".format(
                        encoder,
                        candidate.path,
                    )
                )

            os.replace(candidate.path, final_path)
            return encoder

        raise RuntimeError(
            "FFmpeg H.264 encoding failed: {}".format("; ".join(failures))
        )
    finally:
        candidate.close()
