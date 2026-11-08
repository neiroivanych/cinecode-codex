"""Exercise score evidence and the adapter's boundary with native QC."""
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cc_score_events", ROOT / "scripts/cc.py")
cc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cc)


class ScoreEvents(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cinecode-score-events-")
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve() / "workspace with spaces"
        self.project = self.workspace / "fixture"
        self.video_name = "renders/Кадр final.mp4"
        self.video = self.project / self.video_name
        self.sidecar = self.project / "review/score-events.json"
        self.video.parent.mkdir(parents=True)
        self.sidecar.parent.mkdir()
        (self.project / "STATE.md").write_text("# Test project\n", encoding="utf-8")
        self.video.write_bytes(b"deterministic stand-in for the bound MP4")
        self.media_hash = hashlib.sha256(self.video.read_bytes()).hexdigest()
        # Exercise the command with a deterministic duration, without a media render.
        for mock in (patch.object(cc, "media_duration", return_value=Decimal("2")),
                     patch.object(cc, "require_vendor")):
            mock.start()
            self.addCleanup(mock.stop)

    def event(self, category="score_accent", **changes):
        return {"id": "hit-1", "start": 0.25, "end": 0.5,
                "category": category, **changes}

    def write_evidence(self, events, **changes):
        document = {"schema_version": 1, "media_sha256": self.media_hash,
                    "events": events, **changes}
        self.sidecar.write_text(json.dumps(document), encoding="utf-8")

    def report(self, *options, video_name=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cc.main(["score-events", "fixture", video_name or self.video_name,
                            "--workspace", str(self.workspace), *options])
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def assert_invalid(self, *, video_name=None):
        code, report, stderr = self.report(video_name=video_name)
        self.assertEqual(code, 2, (report, stderr))
        self.assertEqual(report["adapter_evidence"]["status"], "INVALID")
        self.assertTrue(report["adapter_evidence"]["reason"])
        self.assertEqual(report["upstream_qc"]["status"], "NOT_RUN")

    def assert_valid_counts(self, total, counts):
        code, report, stderr = self.report()
        self.assertEqual(code, 0, (report, stderr))
        evidence = report["adapter_evidence"]
        self.assertEqual(evidence["status"], "VALID")
        self.assertTrue(evidence["hash_matched"])
        self.assertEqual(evidence["declared_events"], total)
        self.assertEqual({key: count for key, count in evidence["by_category"].items() if count}, counts)
        self.assertEqual(report["upstream_qc"]["status"], "NOT_RUN")
        return report

    def test_declared_score_accent_binds_to_exact_mp4(self):
        self.write_evidence([self.event()])
        self.assert_valid_counts(1, {"score_accent": 1})

    def test_missing_evidence_is_unknown(self):
        code, report, stderr = self.report()
        self.assertEqual(code, 0, (report, stderr))
        self.assertEqual(report["adapter_evidence"]["status"], "UNKNOWN")
        self.assertIsNone(report["adapter_evidence"].get("declared_events"))
        self.assertEqual(report["upstream_qc"]["status"], "NOT_RUN")

    def test_native_check_rejects_unreadable_mp4_even_without_sidecar(self):
        with patch.object(cc, "media_duration", side_effect=ValueError("ffprobe could not read MP4 duration")):
            code, report, stderr = self.report("--check")
        self.assertEqual(code, 2, (report, stderr))
        self.assertEqual(report["adapter_evidence"]["status"], "INVALID")
        self.assertEqual(report["upstream_qc"]["status"], "NOT_RUN")

    def test_empty_list_is_zero_declared_events(self):
        self.write_evidence([])
        report = self.assert_valid_counts(0, {})
        self.assertNotIn("silent film", report["interpretation"].lower())

    def test_duplicate_ids_are_invalid(self):
        self.write_evidence([self.event(), self.event("sfx", start=0.5, end=0.75)])
        self.assert_invalid()

    def test_invalid_category_is_rejected(self):
        self.write_evidence([self.event("unsupported")])
        self.assert_invalid()

    def test_invalid_times_are_rejected(self):
        cases = ({"start": -0.1}, {"end": 0.25}, {"end": 0.1}, {"start": False},
                 {"start": "0.25"}, {"end": float("nan")}, {"end": float("inf")})
        for changes in cases:
            with self.subTest(changes=changes):
                self.write_evidence([self.event(**changes)])
                self.assert_invalid()

    def test_event_outside_duration_is_invalid(self):
        self.write_evidence([self.event(start=1.9, end=2.1)])
        self.assert_invalid()

    def test_event_ending_at_duration_is_valid(self):
        self.write_evidence([self.event(start=1.9, end=2)])
        self.assert_valid_counts(1, {"score_accent": 1})

    def test_changed_media_is_invalid(self):
        self.write_evidence([self.event()])
        self.video.write_bytes(b"a different render")
        self.assert_invalid()

    def test_missing_media_is_invalid(self):
        self.write_evidence([self.event()])
        self.video.unlink()
        self.assert_invalid()

    def test_music_only_and_ambience_only_remain_distinct(self):
        for category in ("music", "ambience"):
            with self.subTest(category=category):
                self.write_evidence([self.event(category)])
                self.assert_valid_counts(1, {category: 1})

    def test_mixed_events_keep_category_counts(self):
        self.write_evidence([self.event(), self.event("sfx", id="hit-2"),
                             self.event("foley", id="hit-3")])
        self.assert_valid_counts(3, {"score_accent": 1, "sfx": 1, "foley": 1})

    def test_malformed_or_unsupported_document_is_invalid(self):
        self.sidecar.write_text("{", encoding="utf-8")
        self.assert_invalid()
        for version in (2, True):
            with self.subTest(version=version):
                self.write_evidence([], schema_version=version)
                self.assert_invalid()

    def test_unsafe_media_paths_are_rejected(self):
        self.write_evidence([self.event()])
        for path in ("../fixture/" + self.video_name, str(self.video),
                     "C:relative.mp4", "renders/file.mp4:alternate", r"\\server\share\outside.mp4"):
            with self.subTest(path=path):
                self.assert_invalid(video_name=path)

    def test_native_hold_and_exit_status_are_preserved(self):
        self.write_evidence([self.event()])
        tools = self.project / "tools"
        tools.mkdir()
        native_line = "SOUND THIN: 0 event sounds in 30 s (at least 8)."
        (tools / "make.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "assert sys.argv[1] == 'check'\n"
            f"assert Path(sys.argv[2]).resolve() == Path({str(self.video)!r})\n"
            f"print({native_line!r})\n"
            "print('native diagnostic', file=sys.stderr)\n"
            "sys.exit(1)\n", encoding="utf-8")
        with patch.object(cc, "browser_path", return_value=str(self.video)):
            code, report, stderr = self.report("--check")
        self.assertEqual(code, 1, (report, stderr))
        native = report["upstream_qc"]
        self.assertEqual(native["status"], "REPORTED")
        self.assertEqual(native["exit_code"], 1)
        self.assertIn(native_line, native["stdout"])
        self.assertIn("native diagnostic", native["stderr"])
        self.assertEqual(report["adapter_evidence"]["status"], "VALID")
        self.assertEqual(report["adapter_evidence"]["declared_events"], 1)


if __name__ == "__main__":
    unittest.main()
