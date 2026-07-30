import re
import shlex
import subprocess
import unittest
from dataclasses import fields
from pathlib import Path

from gazelle.runtime.cli import build_parser, parse_runtime_config
from gazelle.runtime.config import RuntimeConfig
from gazelle.runtime.media import SUPPORTED_VIDEO_SUFFIXES, detect_media_type


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENGLISH_GUIDE = REPOSITORY_ROOT / "docs" / "USAGE.md"
CHINESE_GUIDE = REPOSITORY_ROOT / "docs" / "USAGE_CN.md"
ENGLISH_README = REPOSITORY_ROOT / "README.md"
CHINESE_README = REPOSITORY_ROOT / "README_CN.md"
IMPLEMENTATION_PLAN = (
    REPOSITORY_ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-23-project-usage-guide-implementation-plan.md"
)
VIDEO_CODEC_DESIGN = (
    REPOSITORY_ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-30-video-codec-selection-design.md"
)
VIDEO_CODEC_PLAN = (
    REPOSITORY_ROOT
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-30-video-codec-selection-implementation-plan.md"
)


class UsageDocumentationTest(unittest.TestCase):
    def _read(self, path):
        return path.read_text(encoding="utf-8")

    def _long_options(self):
        return [
            (option, action)
            for action in build_parser()._actions
            for option in action.option_strings
            if option.startswith("--")
        ]

    def _documented_default(self, option, action):
        if option == "--help":
            return "`false`"
        if action.default is None:
            return "`None`"
        if isinstance(action.default, bool):
            return "`{}`".format(str(action.default).lower())
        return "`{}`".format(action.default)

    def _option_rows(self, guide_path):
        guide = self._read(guide_path)
        table = guide.split("## 6.", 1)[1].split("## 7.", 1)[0]
        rows = []
        for line in table.splitlines():
            if not line.startswith("| `--"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            self.assertEqual(5, len(cells), "{} has an incomplete option row: {}".format(guide_path, line))
            match = re.fullmatch(r"`(--[a-z0-9-]+)`", cells[0])
            self.assertIsNotNone(match, "{} must have exactly one option per row: {}".format(guide_path, line))
            for column_name, cell in zip(
                ("Option", "Accepted/validation", "Default", "Scope", "Behavior/activity"),
                cells,
            ):
                self.assertTrue(
                    cell and cell not in ("-", "—"),
                    "{} has an empty {} cell: {}".format(guide_path, column_name, line),
                )
            rows.append((match.group(1), cells[1:]))
        return rows

    def _numbered_sections(self, guide_path):
        return [
            int(match.group(1))
            for match in re.finditer(r"^## (\d+)\. .+$", self._read(guide_path), re.MULTILINE)
        ]

    def _section(self, guide_path, section_number):
        guide = self._read(guide_path)
        start = re.search(
            r"^## {}\. .+$".format(section_number),
            guide,
            re.MULTILINE,
        )
        self.assertIsNotNone(start, "{} is missing section {}".format(guide_path, section_number))
        end = re.search(r"^## {}\. .+$".format(section_number + 1), guide[start.end() :], re.MULTILINE)
        return guide[start.end() :] if end is None else guide[start.end() : start.end() + end.start()]

    def _powershell_blocks(self, text):
        return re.findall(r"```powershell\r?\n(.*?)\r?\n```", text, re.DOTALL)

    def _base_run_config_rows(self, guide_path):
        section = self._section(guide_path, 12)
        start_heading = "#### Base RuntimeConfig fields"
        end_heading = "#### Image/video additions and overrides"
        self.assertIn(start_heading, section)
        self.assertIn(end_heading, section)
        table = section.split(start_heading, 1)[1].split(end_heading, 1)[0]
        rows = []
        for line in table.splitlines():
            if not line.startswith("| `"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            self.assertEqual(3, len(cells), "{} has an incomplete RuntimeConfig row: {}".format(guide_path, line))
            match = re.fullmatch(r"`([a-z][a-z0-9_]*)`", cells[0])
            self.assertIsNotNone(match, "{} must have one RuntimeConfig field per row: {}".format(guide_path, line))
            for column_name, cell in zip(("Field", "JSON type/shape and nullability", "Meaning/source"), cells):
                self.assertTrue(
                    cell and cell not in ("-", "—"),
                    "{} has an empty {} cell: {}".format(guide_path, column_name, line),
                )
            rows.append((match.group(1), cells[1], cells[2]))
        return rows

    def _run_config_addition_rows(self, guide_path):
        section = self._section(guide_path, 12)
        heading = "#### Image/video additions and overrides"
        self.assertIn(heading, section)
        table = section.split(heading, 1)[1]
        rows = []
        for line in table.splitlines():
            if not line.startswith("| image |") and not line.startswith("| video |"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            self.assertEqual(4, len(cells), "{} has an incomplete run-config addition row: {}".format(guide_path, line))
            match = re.fullmatch(r"`([a-z][a-z0-9_]*)`", cells[1])
            self.assertIsNotNone(match, "{} must have one addition key per row: {}".format(guide_path, line))
            self.assertTrue(cells[2] and cells[2] not in ("-", "—"))
            self.assertTrue(cells[3] and cells[3] not in ("-", "—"))
            rows.append((cells[0], match.group(1), cells[2], cells[3]))
        return rows

    def test_option_tables_have_one_complete_row_per_long_option(self):
        option_actions = self._long_options()
        expected = [option for option, _ in option_actions]
        expected_defaults = {
            option: self._documented_default(option, action)
            for option, action in option_actions
        }
        english_rows = self._option_rows(ENGLISH_GUIDE)
        chinese_rows = self._option_rows(CHINESE_GUIDE)
        self.assertEqual(expected, [option for option, _ in english_rows])
        self.assertEqual(expected, [option for option, _ in chinese_rows])
        self.assertEqual(
            [option for option, _ in english_rows],
            [option for option, _ in chinese_rows],
        )
        for guide_path, rows in (
            (ENGLISH_GUIDE, english_rows),
            (CHINESE_GUIDE, chinese_rows),
        ):
            for option, cells in rows:
                self.assertEqual(
                    expected_defaults[option],
                    cells[1],
                    "{} documents the wrong default for {}".format(guide_path, option),
                )

    def test_guides_have_matching_numbered_section_structure(self):
        expected = list(range(1, 16))
        self.assertEqual(expected, self._numbered_sections(ENGLISH_GUIDE))
        self.assertEqual(expected, self._numbered_sections(CHINESE_GUIDE))

    def test_readmes_link_to_the_matching_usage_guides(self):
        english_readme = self._read(REPOSITORY_ROOT / "README.md")
        chinese_readme = self._read(REPOSITORY_ROOT / "README_CN.md")
        self.assertIn("(docs/USAGE.md)", english_readme)
        self.assertIn("(docs/USAGE_CN.md)", chinese_readme)

    def test_fenced_video_template_is_complete_and_parseable(self):
        required_options = {
            "--input",
            "--output-dir",
            "--overwrite",
            "--head-source",
            "--max-heads",
            "--pose-model",
            "--head-track-max-gap-ms",
            "--model",
            "--device",
            "--cache-dir",
            "--save-rendered",
            "--video-codec",
            "--head-box",
            "--face-box",
            "--face-keypoints",
            "--pose-head-points",
            "--face-mesh",
            "--face-pose-ray",
            "--pose-head-ray",
            "--reference-ray-length",
            "--gaze-inout-threshold",
        }
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            section = self._section(guide_path, 4)
            blocks = [
                block for block in self._powershell_blocks(section)
                if "USER_INPUT_PATH" in block
            ]
            self.assertEqual(1, len(blocks), "{} needs one section-4 video template".format(guide_path))
            command = blocks[0].replace("USER_INPUT_PATH", "contract-video.mp4")
            command = re.sub(r"`[ \t]*\r?\n", " ", command)
            tokens = shlex.split(command)
            self.assertEqual(["python", "main.py"], tokens[:2])
            argv = tokens[2:]
            self.assertTrue(required_options.issubset(set(argv)))
            config = parse_runtime_config(argv)
            self.assertEqual("video", detect_media_type(config.input_path))
            self.assertEqual("mediapipe", config.head_source)
            self.assertEqual(1, config.max_heads)
            self.assertEqual("full", config.pose_model)
            self.assertEqual(500.0, config.head_track_max_gap_ms)
            self.assertEqual("gazelle_dinov2_vitb14_inout", config.model)
            self.assertEqual("cuda", config.device)
            self.assertEqual("models", config.cache_dir)
            self.assertTrue(config.save_rendered)
            self.assertIn(config.video_codec, ("mp4v", "avc1"))
            self.assertTrue(config.draw_head_box)
            self.assertTrue(config.draw_face_box)
            self.assertTrue(config.draw_face_keypoints)
            self.assertTrue(config.draw_pose_head_points)
            self.assertTrue(config.draw_face_mesh)
            self.assertTrue(config.draw_face_pose_ray)
            self.assertTrue(config.draw_pose_head_ray)
            self.assertEqual(2.5, config.reference_ray_length)
            self.assertEqual(0.5, config.gaze_inout_threshold)
            self.assertIn("only the input path", section.lower())

    def test_video_codec_contract_is_documented_in_all_user_guides(self):
        required_tokens = (
            "--video-codec",
            "mp4v",
            "avc1",
            "FFmpeg",
            "h264_nvenc",
            "libx264",
            "yuv420p",
            "+faststart",
        )
        for guide_path in (
            ENGLISH_README,
            CHINESE_README,
            ENGLISH_GUIDE,
            CHINESE_GUIDE,
        ):
            text = self._read(guide_path)
            for token in required_tokens:
                self.assertIn(
                    token,
                    text,
                    "{} is missing video codec token {}".format(
                        guide_path,
                        token,
                    ),
                )

        self.assertIn("no audio", self._read(ENGLISH_README).lower())
        self.assertIn("no audio", self._read(ENGLISH_GUIDE).lower())
        self.assertIn("无音频", self._read(CHINESE_README))
        self.assertIn("无音频", self._read(CHINESE_GUIDE))

    def test_examples_distinguish_tracked_input_from_user_templates(self):
        tracked_asset = REPOSITORY_ROOT / "assets" / "the_office.png"
        self.assertTrue(tracked_asset.is_file())
        tracked = subprocess.run(
            [
                "git",
                "-c",
                "safe.directory={}".format(REPOSITORY_ROOT.as_posix()),
                "ls-files",
                "--error-unmatch",
                "assets/the_office.png",
            ],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, tracked.returncode, tracked.stderr)
        tracked_files = subprocess.run(
            [
                "git",
                "-c",
                "safe.directory={}".format(REPOSITORY_ROOT.as_posix()),
                "ls-files",
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        tracked_videos = [
            path for path in tracked_files
            if Path(path).suffix.lower() in SUPPORTED_VIDEO_SUFFIXES
        ]
        self.assertEqual([], tracked_videos)

        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            guide = self._read(guide_path)
            self.assertRegex(
                guide,
                re.compile(
                    r"--input\s+assets\\the_office\.png.*?"
                    r"--head-source\s+mediapipe",
                    re.DOTALL,
                ),
            )
            self.assertIn("--input USER_INPUT_PATH", guide)
            self.assertIn("USER_INPUT_PATH", guide)
            self.assertNotIn(r"samples\\", guide)

    def test_rendering_semantics_are_explicit_in_both_guides(self):
        required = (
            "MediaPipe primary perception head box",
            "Gazelle prediction bbox",
            "track-state labels default on",
            "--no-track-state",
            "--head-box",
            "--face-box",
            "--face-keypoints",
            "--pose-head-points",
            "--face-mesh",
            "--face-pose-ray",
            "--pose-head-ray",
            "reference ray",
            "gaze_status",
        )
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            section = self._section(guide_path, 10)
            for token in required:
                self.assertIn(token, section, "{} is missing rendering token {}".format(guide_path, token))

    def test_output_schema_contract_tokens_are_in_both_guides(self):
        required = (
            "Required",
            "Conditional",
            "Nullable",
            "frame_index",
            "timestamp_ms",
            "status",
            "width",
            "height",
            "provider",
            "timings_ms",
            "people",
            "person_id",
            "head_bbox_normalized",
            "confidence",
            "state",
            "view_state",
            "observed",
            "tracking",
            "track_age_frames",
            "missed_frames",
            "missed_ms",
            "face_bbox_normalized",
            "face_keypoints",
            "pose_head_landmarks",
            "pose_head_keypoints",
            "facial_transformation_matrix",
            "head_pose",
            "face_pose_reference_ray",
            "pose_head_reference_ray",
            "gaze_eligible",
            "gaze_status",
            "face_landmarks",
            "x",
            "y",
            "z",
            "visibility",
            "presence",
            "yaw_deg",
            "pitch_deg",
            "roll_deg",
            "face_pose",
            "face_only",
            "pose_only",
            "tracked_only",
            "frontal",
            "profile",
            "back_or_occluded",
            "unknown",
            "bbox_normalized",
            "gaze_peak_normalized",
            "heatmap_peak_value",
            "inout_score",
            "out_of_frame",
            "no_gaze",
            "heatmap_path",
            "inference_ms",
            "error",
            "input_path",
            "image_width",
            "image_height",
            "source_fps",
            "output_fps",
            "frames_read",
            "frames_written",
            "(xmin, ymin, xmax, ymax)",
            "[0, 1]",
        )
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            section = self._section(guide_path, 12)
            for token in required:
                self.assertIn(token, section, "{} is missing schema token {}".format(guide_path, token))

    def test_base_run_config_tables_match_dataclass_fields(self):
        expected = [field.name for field in fields(RuntimeConfig)]
        self.assertEqual(45, len(expected))
        english_rows = self._base_run_config_rows(ENGLISH_GUIDE)
        chinese_rows = self._base_run_config_rows(CHINESE_GUIDE)
        self.assertEqual(expected, [name for name, _, _ in english_rows])
        self.assertEqual(expected, [name for name, _, _ in chinese_rows])
        self.assertEqual(
            [name for name, _, _ in english_rows],
            [name for name, _, _ in chinese_rows],
        )

        rename_contracts = (
            "`--input` -> `input_path`",
            "`--bbox` -> `bboxes`",
            "`--person-id` -> `person_ids`",
            "`--no-heatmap` -> `draw_heatmap`",
            "`--head-box` -> `draw_head_box`",
            "`--no-gaze-peak` -> `draw_gaze_peak`",
            "`--no-gaze-arrow` -> `draw_gaze_arrow`",
            "`--no-labels` -> `draw_labels`",
            "`--face-box` -> `draw_face_box`",
            "`--face-keypoints` -> `draw_face_keypoints`",
            "`--pose-head-points` -> `draw_pose_head_points`",
            "`--face-mesh` -> `draw_face_mesh`",
            "`--no-track-state` -> `draw_track_state`",
            "`--face-pose-ray` -> `draw_face_pose_ray`",
            "`--pose-head-ray` -> `draw_pose_head_ray`",
        )
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            section = self._section(guide_path, 12)
            for contract in rename_contracts:
                self.assertIn(contract, section, "{} is missing config rename {}".format(guide_path, contract))
            self.assertIn("positive `draw_*` booleans", section)

    def test_run_config_addition_tables_have_exact_media_keys(self):
        expected = {
            "image": ["input_path", "image_width", "image_height"],
            "video": [
                "input_path",
                "width",
                "height",
                "source_fps",
                "output_fps",
                "frames_read",
                "frames_written",
            ],
        }
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            rows = self._run_config_addition_rows(guide_path)
            actual = {
                scope: [name for row_scope, name, _, _ in rows if row_scope == scope]
                for scope in ("image", "video")
            }
            self.assertEqual(expected, actual)

    def test_facial_transformation_matrix_contract_is_precise(self):
        required = (
            "serializer preserves supplied row lengths",
            "at least three rows",
            "at least three values in each of the first three rows",
            "does not enforce rectangularity",
        )
        prohibited = (
            "Rectangular finite matrix",
            "Rectangular, at least",
            "至少 `3 x 3` 的矩形",
            "矩形、至少 `3 x 3`",
        )
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            section = self._section(guide_path, 12)
            for contract in required:
                self.assertIn(contract, section, "{} is missing matrix contract {}".format(guide_path, contract))
            for claim in prohibited:
                self.assertNotIn(claim, section, "{} retains an overstrong matrix claim".format(guide_path))

    def test_implementation_plan_has_one_final_newline(self):
        for plan_path in (
            IMPLEMENTATION_PLAN,
            VIDEO_CODEC_DESIGN,
            VIDEO_CODEC_PLAN,
        ):
            content = self._read(plan_path)
            self.assertTrue(content.endswith("\n"))
            self.assertFalse(
                content.endswith("\n\n"),
                "{} has an extra blank line at EOF".format(plan_path),
            )

    def test_known_limitations_and_security_boundaries_are_documented(self):
        required = (
            "strictly increase after rounding",
            "sub-millisecond",
            "30 FPS",
            "--output-fps",
            "bridge timing",
            "known runtime limitation",
            "containment",
            "_gazelle",
            "recursively deletes",
            "before provider/model/resource setup",
            "same-stem",
            "collide",
            "torch.hub.load",
            "facebookresearch/dinov2",
            "unpinned",
            "remote Python",
            "trusted network",
            "pre-reviewed cache",
            "GazellePredictor",
            "HeadObservation",
            '"images"',
            '"bboxes"',
            "person_id",
            "confidence",
            "not model input",
            "visible-face",
            "pose-only",
            "stale bridge box",
            "profile",
            "PPE",
            "blur",
            "low resolution",
            "limited real multi-person validation",
        )
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            guide = self._read(guide_path)
            for token in required:
                self.assertIn(token, guide, "{} is missing limitation token {}".format(guide_path, token))

    def test_public_validation_commands_use_activated_python(self):
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            section = self._section(guide_path, 15)
            self.assertIn("conda activate Gazelle", section)
            self.assertIn("python -m unittest tests.test_usage_docs -v", section)
            self.assertNotRegex(section, re.compile(r"[A-Za-z]:\\Users\\"))


if __name__ == "__main__":
    unittest.main()
