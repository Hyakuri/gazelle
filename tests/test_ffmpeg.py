from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gazelle.runtime.ffmpeg import (
    FFmpegCapabilities,
    TemporaryVideoPath,
    detect_ffmpeg_capabilities,
    transcode_h264,
)


def completed_process(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class FFmpegCapabilityTest(unittest.TestCase):
    def test_missing_ffmpeg_reports_path_requirement(self):
        with self.assertRaisesRegex(RuntimeError, "FFmpeg.*PATH"):
            detect_ffmpeg_capabilities(which=lambda _: None)

    def test_encoder_probe_prefers_nvenc_then_libx264(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return completed_process(
                stdout=" V..... h264_nvenc\n V..... libx264\n"
            )

        capabilities = detect_ffmpeg_capabilities(
            which=lambda _: "C:/ffmpeg/bin/ffmpeg.exe",
            runner=runner,
        )

        self.assertEqual(
            capabilities.encoder_order,
            ("h264_nvenc", "libx264"),
        )
        self.assertEqual(
            calls[0][0],
            ["C:/ffmpeg/bin/ffmpeg.exe", "-hide_banner", "-encoders"],
        )
        self.assertEqual(calls[0][1]["stdout"], subprocess.PIPE)
        self.assertEqual(calls[0][1]["stderr"], subprocess.PIPE)
        self.assertTrue(calls[0][1]["text"])
        self.assertFalse(calls[0][1]["check"])

    def test_encoder_probe_parses_stderr(self):
        capabilities = detect_ffmpeg_capabilities(
            which=lambda _: "ffmpeg",
            runner=lambda *args, **kwargs: completed_process(
                stderr=" V..... libx264\n"
            ),
        )

        self.assertEqual(capabilities.encoder_order, ("libx264",))

    def test_encoder_probe_failure_reports_diagnostics(self):
        with self.assertRaisesRegex(RuntimeError, "probe failed.*broken"):
            detect_ffmpeg_capabilities(
                which=lambda _: "ffmpeg",
                runner=lambda *args, **kwargs: completed_process(
                    returncode=1,
                    stderr="broken probe",
                ),
            )

    def test_encoder_probe_requires_supported_h264_encoder(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "h264_nvenc.*libx264",
        ):
            detect_ffmpeg_capabilities(
                which=lambda _: "ffmpeg",
                runner=lambda *args, **kwargs: completed_process(
                    stdout=" V..... mpeg4\n"
                ),
            )


class TemporaryVideoPathTest(unittest.TestCase):
    def test_temporary_path_is_hidden_unique_and_beside_output(self):
        with TemporaryDirectory() as temp_dir:
            final_path = Path(temp_dir) / "rendered.mp4"
            first = TemporaryVideoPath.beside(
                final_path,
                "candidate",
                token="first",
            )
            second = TemporaryVideoPath.beside(
                final_path,
                "candidate",
                token="second",
            )

            self.assertEqual(first.path.parent, final_path.parent)
            self.assertTrue(first.path.name.startswith(".rendered.candidate."))
            self.assertEqual(first.path.suffix, ".mp4")
            self.assertNotEqual(first.path, second.path)

    def test_close_removes_temporary_file_idempotently(self):
        with TemporaryDirectory() as temp_dir:
            temporary = TemporaryVideoPath.beside(
                Path(temp_dir) / "rendered.mp4",
                "source",
                token="cleanup",
            )
            temporary.path.write_bytes(b"temporary")

            temporary.close()
            temporary.close()

            self.assertFalse(temporary.path.exists())


class H264TranscodeTest(unittest.TestCase):
    def make_capabilities(self, *encoders):
        return FFmpegCapabilities(
            executable="C:/ffmpeg/bin/ffmpeg.exe",
            encoders=tuple(encoders),
        )

    def test_nvenc_success_uses_compatibility_flags_and_publishes_output(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            final_path = Path(temp_dir) / "rendered.mp4"
            source_path.write_bytes(b"source")
            calls = []

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                Path(command[-1]).write_bytes(b"h264")
                return completed_process()

            encoder = transcode_h264(
                source_path,
                final_path,
                self.make_capabilities("h264_nvenc", "libx264"),
                runner=runner,
            )

            self.assertEqual(encoder, "h264_nvenc")
            self.assertEqual(final_path.read_bytes(), b"h264")
            self.assertEqual(len(calls), 1)
            command, kwargs = calls[0]
            self.assertEqual(command[0], "C:/ffmpeg/bin/ffmpeg.exe")
            self.assertIn("-an", command)
            self.assertEqual(command[command.index("-c:v") + 1], "h264_nvenc")
            self.assertEqual(command[command.index("-pix_fmt") + 1], "yuv420p")
            self.assertEqual(command[command.index("-movflags") + 1], "+faststart")
            self.assertEqual(kwargs["stdout"], subprocess.PIPE)
            self.assertEqual(kwargs["stderr"], subprocess.PIPE)
            self.assertTrue(kwargs["text"])
            self.assertFalse(kwargs["check"])
            self.assertEqual(
                list(Path(temp_dir).glob(".rendered.candidate.*.mp4")),
                [],
            )

    def test_nvenc_runtime_failure_falls_back_to_libx264(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            final_path = Path(temp_dir) / "rendered.mp4"
            source_path.write_bytes(b"source")
            encoders = []

            def runner(command, **kwargs):
                encoder = command[command.index("-c:v") + 1]
                encoders.append(encoder)
                if encoder == "h264_nvenc":
                    Path(command[-1]).write_bytes(b"partial")
                    return completed_process(
                        returncode=1,
                        stderr="NVENC initialization failed",
                    )
                Path(command[-1]).write_bytes(b"software")
                return completed_process()

            encoder = transcode_h264(
                source_path,
                final_path,
                self.make_capabilities("h264_nvenc", "libx264"),
                runner=runner,
            )

            self.assertEqual(encoder, "libx264")
            self.assertEqual(encoders, ["h264_nvenc", "libx264"])
            self.assertEqual(final_path.read_bytes(), b"software")
            self.assertEqual(
                list(Path(temp_dir).glob(".rendered.candidate.*.mp4")),
                [],
            )

    def test_all_encoder_failures_report_each_diagnostic(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            final_path = Path(temp_dir) / "rendered.mp4"
            source_path.write_bytes(b"source")

            def runner(command, **kwargs):
                encoder = command[command.index("-c:v") + 1]
                return completed_process(
                    returncode=7 if encoder == "h264_nvenc" else 8,
                    stderr="{} failed".format(encoder),
                )

            with self.assertRaises(RuntimeError) as caught:
                transcode_h264(
                    source_path,
                    final_path,
                    self.make_capabilities("h264_nvenc", "libx264"),
                    runner=runner,
                )

            message = str(caught.exception)
            self.assertIn("h264_nvenc", message)
            self.assertIn("return code 7", message)
            self.assertIn("NVENC".lower(), message.lower())
            self.assertIn("libx264", message)
            self.assertIn("return code 8", message)
            self.assertFalse(final_path.exists())
            self.assertEqual(
                list(Path(temp_dir).glob(".rendered.candidate.*.mp4")),
                [],
            )

    def test_success_without_candidate_raises_and_does_not_replace_existing_output(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            final_path = Path(temp_dir) / "rendered.mp4"
            source_path.write_bytes(b"source")
            final_path.write_bytes(b"old output")

            with self.assertRaisesRegex(
                RuntimeError,
                "completed but output file was not found",
            ):
                transcode_h264(
                    source_path,
                    final_path,
                    self.make_capabilities("libx264"),
                    runner=lambda *args, **kwargs: completed_process(),
                )

            self.assertEqual(final_path.read_bytes(), b"old output")
            self.assertEqual(
                list(Path(temp_dir).glob(".rendered.candidate.*.mp4")),
                [],
            )

    def test_success_atomically_replaces_existing_output(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            final_path = Path(temp_dir) / "rendered.mp4"
            source_path.write_bytes(b"source")
            final_path.write_bytes(b"old output")

            def runner(command, **kwargs):
                Path(command[-1]).write_bytes(b"new output")
                return completed_process()

            transcode_h264(
                source_path,
                final_path,
                self.make_capabilities("libx264"),
                runner=runner,
            )

            self.assertEqual(final_path.read_bytes(), b"new output")

    def test_transcode_requires_available_encoder(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            source_path.write_bytes(b"source")

            with self.assertRaisesRegex(RuntimeError, "H.264 encoder"):
                transcode_h264(
                    source_path,
                    Path(temp_dir) / "rendered.mp4",
                    self.make_capabilities(),
                    runner=lambda *args, **kwargs: completed_process(),
                )

    def test_cleanup_failure_does_not_mask_encoding_failure(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source.mp4"
            final_path = Path(temp_dir) / "rendered.mp4"
            source_path.write_bytes(b"source")

            class CleanupFailingCandidate:
                def __init__(self):
                    self.path = Path(temp_dir) / ".rendered.candidate.test.mp4"
                    self.close_calls = 0

                def close(self):
                    self.close_calls += 1
                    if self.close_calls > 1:
                        raise PermissionError("candidate cleanup failed")

            candidate = CleanupFailingCandidate()
            with patch(
                "gazelle.runtime.ffmpeg.TemporaryVideoPath.beside",
                return_value=candidate,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "FFmpeg H.264 encoding failed",
                ) as caught:
                    transcode_h264(
                        source_path,
                        final_path,
                        self.make_capabilities("libx264"),
                        runner=lambda *args, **kwargs: completed_process(
                            returncode=9,
                            stderr="encoder failed",
                        ),
                    )

        self.assertEqual(candidate.close_calls, 2)
        self.assertTrue(
            any(
                "candidate cleanup failed" in note
                for note in caught.exception.__notes__
            )
        )


if __name__ == "__main__":
    unittest.main()
