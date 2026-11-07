"""Targeted adapter regressions. No render, media, models or service calls."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cc_corrections", ROOT / "scripts/cc.py")
cc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cc)


class Corrections(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cinecode-correction-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.cwd = self.base / "unrelated cwd"
        self.cwd.mkdir()
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        self.env.pop("CINECODE_KIT", None)

    def run_adapter(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/cc.py"), *map(str, args)],
            cwd=self.cwd, env=self.env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30)

    def directory_link(self, link, target):
        """Real Windows junction; a directory symlink on other platforms."""
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True, text=True, timeout=10)
            if result.returncode:
                self.skipTest("Windows junction creation unavailable: " + result.stderr.strip())
        else:
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as e:
                self.skipTest("Directory symlink creation unavailable: " + str(e))

        def remove_link():
            # Remove only this fixture link before TemporaryDirectory cleanup.
            if link.is_symlink():
                link.unlink()
            elif (os.name == "nt" and
                  link.lstat().st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT):
                link.rmdir()
            else:
                raise AssertionError("fixture link changed unexpectedly")

        self.addCleanup(remove_link)

    def fake_project(self, workspace, watched="TEMP"):
        project = workspace / "fixture"
        (project / "tools").mkdir(parents=True)
        (project / "STATE.md").write_text("No-media correction fixture", encoding="utf-8")
        (project / "tools/words_check.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "destination=Path(os.environ[" + repr(watched) + "])\n"
            "destination.mkdir(parents=True,exist_ok=True)\n"
            "(destination/'child-ran').write_text('synthetic')\n", encoding="utf-8")

    def assert_state_refused(self, workspace, target):
        tmp_was_present = os.path.lexists(workspace / ".cinecode-state/tmp")
        result = self.run_adapter("tool", "fixture", "--workspace", workspace, "words-check")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("managed state", result.stderr.lower())
        self.assertEqual(list(target.iterdir()), [], "a managed write or child escaped through the link")
        if not tmp_was_present:
            self.assertFalse((workspace / ".cinecode-state/tmp").exists(),
                             "environment validation should precede tmp creation")

    def test_real_copied_brief_from_initialized_external_project(self):
        workspace = self.base / "external workspace with spaces"
        initialized = self.run_adapter("init", "brief-fixture", "--workspace", workspace, "--mode", "quick")
        self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)
        copied = workspace / "brief-fixture/tools/brief.py"
        self.assertEqual(copied.read_bytes(), (ROOT / "cinecode/scripts/brief.py").read_bytes())
        listed = self.run_adapter("tool", "brief-fixture", "--workspace", workspace, "brief", "list")
        self.assertEqual(listed.returncode, 0, listed.stdout + listed.stderr)
        self.assertIn("sound", listed.stdout)
        # This reads real vendored reference sections, not just a fake helper.
        brief = self.run_adapter(
            "tool", "brief-fixture", "--workspace", workspace, "brief", "sound",
            "--task", "inspect a local sound plan", "--writes", "audio/sfx/*",
            "--reads", "STATE.md", "--done", "coverage checked")
        self.assertEqual(brief.returncode, 0, brief.stdout + brief.stderr)
        self.assertIn("<!-- cinecode brief: sound -->", brief.stdout)
        self.assertIn("What the picture does", brief.stdout)

    def test_managed_state_root_junction_rejected_before_child_write(self):
        workspace = self.base / "root state workspace"
        self.fake_project(workspace)
        target = self.base / "root state target"
        target.mkdir()
        self.directory_link(workspace / ".cinecode-state", target)
        self.assert_state_refused(workspace, target)

    def test_managed_tmp_junction_rejected_before_child_write(self):
        workspace = self.base / "tmp workspace"
        self.fake_project(workspace)
        (workspace / ".cinecode-state").mkdir()
        target = self.base / "tmp target"
        target.mkdir()
        self.directory_link(workspace / ".cinecode-state/tmp", target)
        self.assert_state_refused(workspace, target)

    def test_exported_store_junctions_rejected_before_child_write(self):
        for variable, name in [("CINECODE_FORMATS", "formats"),
                               ("CINECODE_GUARD_SEEN", "guard-seen"),
                               ("CINECODE_SOUNDS_CACHE", "sounds"),
                               ("CINECODE_SAMPLES_CACHE", "samples")]:
            with self.subTest(variable=variable):
                workspace = self.base / (name + " workspace")
                self.fake_project(workspace, variable)
                (workspace / ".cinecode-state").mkdir()
                target = self.base / (name + " target")
                target.mkdir()
                self.directory_link(workspace / ".cinecode-state" / name, target)
                self.assert_state_refused(workspace, target)

    def test_root_vendor_junction_rejected_with_real_pinned_manifest(self):
        self.assertTrue(cc.verify()["ok"], "the ordinary pinned vendor must remain valid")
        install = self.base / "linked vendor install"
        install.mkdir()
        for name in ("upstream.lock.json", "cinecode.sha256.json"):
            shutil.copy2(ROOT / name, install / name)
        self.directory_link(install / "cinecode", ROOT / "cinecode")
        result = cc.verify(install)
        self.assertFalse(result["ok"], result)
        self.assertIn("vendor root", " ".join(result["errors"]).lower())


if __name__ == "__main__":
    unittest.main()
