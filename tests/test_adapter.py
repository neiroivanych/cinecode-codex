import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("cc", Path(__file__).resolve().parents[1] / "scripts/cc.py")
cc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cc)


class Verification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        vendor = self.root / "cinecode"
        vendor.mkdir()
        (vendor / "LICENSE").write_bytes(b"synthetic license\n")
        (vendor / "SKILL.md").write_bytes(b"synthetic skill\n")
        files = [{"path": p.name, "bytes": p.stat().st_size, "sha256": cc.digest(p)}
                 for p in sorted(vendor.iterdir())]
        manifest = self.root / "cinecode.sha256.json"
        manifest.write_text(json.dumps({"schema_version": 1, "files": files}), encoding="utf-8")
        self.lock = {"schema_version": 1, "repository": cc.UPSTREAM, "commit": cc.PIN,
                     "directory": "cinecode", "manifest": manifest.name,
                     "manifest_sha256": cc.digest(manifest)}
        self.write_lock()

    def write_lock(self):
        (self.root / "upstream.lock.json").write_text(json.dumps(self.lock), encoding="utf-8")

    def test_clean_snapshot(self):
        self.assertTrue(cc.verify(self.root)["ok"])

    def test_content_drift_even_with_same_size(self):
        p = self.root / "cinecode/SKILL.md"
        p.write_bytes(b"x" * p.stat().st_size)
        self.assertFalse(cc.verify(self.root)["ok"])

    def test_deleted_file(self):
        (self.root / "cinecode/LICENSE").unlink()
        self.assertIn("missing: LICENSE", cc.verify(self.root)["errors"])

    def test_unexpected_file(self):
        (self.root / "cinecode/extra").write_text("extra")
        self.assertIn("unexpected: extra", cc.verify(self.root)["errors"])

    def test_manifest_digest_drift(self):
        p = self.root / "cinecode.sha256.json"
        p.write_bytes(p.read_bytes() + b" ")
        self.assertFalse(cc.verify(self.root)["ok"])

    def test_pin_change(self):
        self.lock["commit"] = "0" * 40
        self.write_lock()
        self.assertFalse(cc.verify(self.root)["ok"])

    def test_path_traversal_in_manifest(self):
        p = self.root / "cinecode.sha256.json"
        data = json.loads(p.read_text())
        data["files"][0]["path"] = "../outside"
        p.write_text(json.dumps(data))
        self.lock["manifest_sha256"] = cc.digest(p)
        self.write_lock()
        self.assertFalse(cc.verify(self.root)["ok"])

    def test_relocated_copy_verifies(self):
        copied = self.root / "install elsewhere"
        copied.mkdir()
        for name in ("cinecode",):
            shutil.copytree(self.root / name, copied / name)
        for name in ("upstream.lock.json", "cinecode.sha256.json"):
            shutil.copy2(self.root / name, copied / name)
        self.assertTrue(cc.verify(copied)["ok"])


class WorkspaceAndDoctor(unittest.TestCase):
    def test_workspace_cannot_include_installation_or_vendor(self):
        for p in (cc.ROOT, cc.ROOT.parent, cc.ROOT / "cinecode", cc.ROOT / "docs"):
            with self.subTest(p=p), self.assertRaises(ValueError):
                cc.workspace_path(str(p))

    def test_project_rejects_traversal(self):
        ws = cc.ROOT / "workspace"
        for name in ("../escape", "C:/elsewhere", ".", "a/b", "a\\b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                cc.project_path(name, ws)

    def test_missing_tool_is_reported(self):
        with patch.object(cc.shutil, "which", return_value=None):
            self.assertFalse(cc.executable_check("node", ["--version"])["ok"])

    def test_invalid_explicit_browser_is_not_silently_ignored(self):
        self.assertIsNone(cc.browser_path({"CHROME_PATH": "/nonexistent/cinecode-test-browser"}))

    def test_state_redirection_without_home_reassignment(self):
        with tempfile.TemporaryDirectory() as d:
            env = cc.child_env(Path(d))
            for name in ("CINECODE_KEYS", "CINECODE_FORMATS", "CINECODE_TASTE",
                         "TEMP", "CINECODE_GUARD_SEEN"):
                self.assertTrue(Path(env[name]).is_relative_to(Path(d)))
            self.assertEqual(env.get("HOME"), os.environ.get("HOME"))
            self.assertEqual(env.get("USERPROFILE"), os.environ.get("USERPROFILE"))

    def test_doctor_missing_browser_is_failure_not_pass(self):
        with tempfile.TemporaryDirectory() as d, patch.object(cc, "browser_path", return_value=None):
            result = cc.doctor(str(Path(d) / "workspace"))
            self.assertFalse(result["ok"])
            self.assertFalse(result["checks"]["browser"]["ok"])

    def test_tool_preserves_failure_exit_cwd_and_literal_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d) / "workspace with spaces"
            project = ws / "fixture"
            (project / "tools").mkdir(parents=True)
            (project / "STATE.md").write_text("synthetic runner test")
            (project / "tools/words_check.py").write_text(
                "import json,os,sys\n"
                "open('observed.json','w').write(json.dumps([os.getcwd(),sys.argv[1:]]))\n"
                "sys.exit(7)\n", encoding="utf-8")
            literal = "$(must-not-execute)"
            code = cc.main(["tool", "fixture", "--workspace", str(ws),
                            "words-check", literal])
            self.assertEqual(code, 7)
            cwd, args = json.loads((project / "observed.json").read_text())
            self.assertEqual(Path(cwd).resolve(), project.resolve())
            self.assertEqual(args, [literal])


if __name__ == "__main__":
    unittest.main()
