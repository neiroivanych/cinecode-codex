"""Offline bootstrap and package regressions using disposable fixtures."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "installer"))
import install


SPEC = importlib.util.spec_from_file_location("cinecode_package", ROOT / "installer/build/package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)
build = package.build


class Packaging(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cinecode-package-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "source"
        self.repo.mkdir()
        self.git("init", "-q")
        for name in ("VERSION", "adapter.json", "scripts/cc.py", ".agents/skills/cinecode/SKILL.md",
                     "upstream.lock.json", "cinecode.sha256.json", "cinecode/SKILL.md"):
            self.write(name, b"0.1.3-alpha\n" if name == "VERSION" else b"fixture\n")
        for name in ("manifest.json", "install.py", "windows/INSTALL_CINECODE.cmd", "windows/setup.ps1",
                     "windows/README-INSTALL.txt", "macos/INSTALL_CINECODE.command", "macos/setup.sh",
                     "macos/README-INSTALL.txt"):
            self.write("installer/" + name, (ROOT / "installer" / name).read_bytes())
        self.git("add", ".")
        self.commit()
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        for name in ("workspace/film.txt", "evidence/local/run.txt", ".env", "credentials.json"):
            self.write(name, b"untracked fixture\n")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, stderr=subprocess.PIPE)

    def commit(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "Package fixture")

    def write(self, name, data):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def extract(self, platform, folder):
        artifact = build(self.repo, self.head, platform, self.root / folder)
        bundle = self.root / folder / "extracted"
        with zipfile.ZipFile(artifact) as archive:
            archive.extractall(bundle)
        return artifact, bundle

    def test_both_zips_are_reproducible_and_match_committed_payload(self):
        # A dirty tracked checkout and untracked user files must not enter a ZIP.
        self.write("VERSION", b"9.9.9\n")
        for system, os_name in (("windows", "Windows"), ("macos", "Darwin")):
            with self.subTest(system=system):
                artifact, bundle = self.extract(system, system)
                repeated = build(self.repo, self.head, system, self.root / (system + "-second"), "0.1.3-alpha")
                self.assertEqual(artifact.read_bytes(), repeated.read_bytes())
                manifest, payload = install.verify_payload(bundle, os_name)
                self.assertEqual(manifest["source_commit"], self.head)
                self.assertEqual(manifest["adapter_version"], "0.1.3-alpha")
                self.assertEqual(manifest["installer_version"], "0.1.0-alpha")
                self.assertEqual(set(manifest["files"]), set(self.git("ls-files").decode().splitlines()))
                for name, info in manifest["files"].items():
                    data = self.git("show", f"{self.head}:{name}")
                    self.assertEqual((payload / name).read_bytes(), data)
                    self.assertEqual(info["sha256"], hashlib.sha256(data).hexdigest())
                with zipfile.ZipFile(artifact) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertTrue(all(member.compress_type == zipfile.ZIP_STORED for member in archive.infolist()))
                    for name, info in manifest["files"].items():
                        mode = archive.getinfo(f"payload/cinecode-codex/{name}").external_attr >> 16
                        self.assertEqual(stat.S_IMODE(mode), info["mode"])
                    if system == "macos":
                        for entry in ("INSTALL_CINECODE.command", "setup.sh"):
                            self.assertEqual(archive.getinfo(entry).external_attr >> 16 & 0o777, 0o755)

    def test_release_zips_build_without_zlib(self):
        # Block the import before zipfile loads so it uses its standard CRC fallback.
        script = """import runpy, sys
from pathlib import Path
sys.modules['zlib'] = None
import zipfile
assert zipfile.zlib is None
builder, root, commit, system, output = sys.argv[1:]
archive_path = runpy.run_path(builder)['build'](Path(root), commit, system, Path(output))
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
"""
        for system in ("windows", "macos"):
            with self.subTest(system=system):
                baseline = build(self.repo, self.head, system, self.root / (system + "-baseline"))
                output = self.root / (system + "-without-zlib")
                subprocess.run([sys.executable, "-B", "-c", script, SPEC.origin, str(self.repo),
                                self.head, system, str(output)], check=True, timeout=30)
                self.assertEqual((output / baseline.name).read_bytes(), baseline.read_bytes())

    def test_version_must_match_selected_commit(self):
        with self.assertRaisesRegex(ValueError, "expected 9.9.9"):
            build(self.repo, self.head, "windows", self.root / "mismatch", "9.9.9")

    def test_packaging_rejects_tracked_secret(self):
        self.git("add", "-f", ".env")
        self.commit()
        with self.assertRaisesRegex(ValueError, "private payload path"):
            build(self.repo, "HEAD", "windows", self.root / "private")

    def test_packaging_rejects_git_symlink(self):
        blob = self.git("rev-parse", "HEAD:VERSION").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{blob},symlink")
        self.commit()
        with self.assertRaisesRegex(ValueError, "Unsupported tracked"):
            build(self.repo, "HEAD", "macos", self.root / "linked")

    def test_extracted_corruption_and_extra_files_are_rejected(self):
        _, bundle = self.extract("windows", "corrupt")
        payload = bundle / "payload/cinecode-codex"
        (payload / "scripts/cc.py").write_bytes(b"changed\n")
        with self.assertRaisesRegex(ValueError, "corrupted"):
            install.verify_payload(bundle, "Windows")
        (payload / "unexpected.txt").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            install.verify_payload(bundle, "Windows")

    def test_unsafe_paths_are_rejected(self):
        for name in ("../outside", "/rooted", r"a\b", "C:drive", "dir/CON.txt", "dir/a.", ".git/config",
                     "workspace/film.html", "evidence/local/log", "a/.env.prod", "a/creds.pem", "a/\npath"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                install.payload_path(name)
        with self.assertRaisesRegex(ValueError, "Case-colliding"):
            install.validate_names(["example/file-a", "Example/file-b"])

    def test_explicit_destination_cannot_use_system_temp_root(self):
        with patch.object(install.platform, "system", return_value="Windows"), \
                patch.dict(os.environ, {"SYSTEMROOT": str(self.root)}), \
                patch.object(install.tempfile, "gettempdir", return_value=str(self.root)):
            with self.assertRaisesRegex(ValueError, "outside system directories"):
                install.destination_path(self.root / "Temp" / "CineCode")

    def test_destination_accepts_alias_for_allowed_temp_path(self):
        temp_root = self.root / "Long temp directory"
        temp_root.mkdir()
        destination = temp_root / "CineCode"
        alias = self.root / "LONGTE~1" / "CineCode"
        resolve = type(alias).resolve

        def resolve_alias(path, *args, **kwargs):
            if path == alias:
                return destination
            return resolve(path, *args, **kwargs)

        with patch.object(type(alias), "resolve", resolve_alias), \
                patch.object(install.platform, "system", return_value="Windows"), \
                patch.object(install.tempfile, "gettempdir", return_value=str(temp_root)):
            self.assertEqual(install.destination_path(alias), destination)

    def test_same_version_repair_and_unrelated_files_survive(self):
        _, bundle = self.extract("windows", "repair")
        destination = self.root / "CineCode with spaces" / "Тест"
        tools = {name: (sys.executable, "fixture") for name in install.TOOLS}
        with patch.object(install.platform, "system", return_value="Windows"), \
                patch.object(install.platform, "machine", return_value="AMD64"), \
                patch.object(install, "prepare_dependencies", return_value=tools), \
                patch.object(install, "binary", return_value=sys.executable), \
                patch.object(install.subprocess, "run") as launched:
            launched.return_value.returncode = 0
            install.setup(bundle, destination, io.StringIO())
            paths = ("workspace/film/STATE.md", "workspace/.cinecode-state/record", "user-file.txt")
            for name in paths:
                path = destination / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"keep\n")
            (destination / "scripts/cc.py").write_bytes(b"corrupted")
            (destination / "cinecode/SKILL.md").unlink()
            install.setup(bundle, destination, io.StringIO())
            self.assertEqual([call.args[0][-1] for call in launched.call_args_list],
                             ["verify", "doctor", "verify", "doctor"])
        for name in paths:
            self.assertEqual((destination / name).read_bytes(), b"keep\n")
        self.assertEqual((destination / "scripts/cc.py").read_bytes(), b"fixture\n")
        self.assertTrue((destination / "cinecode/SKILL.md").is_file())

    def test_different_version_and_unknown_collision_stop(self):
        _, bundle = self.extract("windows", "collision")
        manifest, _ = install.verify_payload(bundle, "Windows")
        destination = self.root / "existing"
        destination.mkdir()
        version = destination / "VERSION"
        version.write_text("0.1.1-alpha", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different CineCode version"):
            install.install_plan(destination, manifest)
        version.write_text("0.1.3-alpha\n", encoding="utf-8")
        (destination / "adapter.json").write_text("user content", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not belong"):
            install.install_plan(destination, manifest)
        self.assertEqual((destination / "adapter.json").read_text(encoding="utf-8"), "user content")

    def test_macos_repair_uses_native_copy_and_preserves_workspace(self):
        _, bundle = self.extract("macos", "mac-repair")
        destination = self.root / "CineCode on Mac"
        tools = {name: (sys.executable, "fixture") for name in install.TOOLS}

        def run(argv, **_):
            if argv[:2] == ["/bin/cp", "-p"]:
                shutil.copy2(argv[2], argv[3])
            return subprocess.CompletedProcess(argv, 0)

        with patch.object(install.platform, "system", return_value="Darwin"), \
                patch.object(install.platform, "machine", return_value="arm64"), \
                patch.object(install, "prepare_dependencies", return_value=tools), \
                patch.object(install, "binary", return_value=sys.executable), \
                patch.object(install.subprocess, "run", side_effect=run) as launched:
            install.setup(bundle, destination, io.StringIO())
            workspace = destination / "workspace/.cinecode-state/sentinel"
            workspace.parent.mkdir(parents=True)
            workspace.write_bytes(b"keep Mac state\n")
            (destination / "adapter.json").write_bytes(b"corrupt")
            install.setup(bundle, destination, io.StringIO())
        self.assertTrue(any(call.args[0][:2] == ["/bin/cp", "-p"] for call in launched.call_args_list))
        self.assertEqual(workspace.read_bytes(), b"keep Mac state\n")
        self.assertEqual((destination / "adapter.json").read_bytes(), b"fixture\n")


class DependencyPlanning(unittest.TestCase):
    def exercise(self, system, missing=(), *, manager=True, succeeds=True, appears=True, allow_install=True):
        completed = set(install.TOOLS) - set(missing)
        calls = []

        def component(name, *_):
            return (sys.executable, "verified fixture") if name in completed else None

        def prepare(_system, _manager, package, *_):
            calls.append(package)
            if not succeeds:
                raise ValueError(f"install failed: {package}")
            if appears:
                completed.update(name for name, pkg in install.PACKAGE_IDS[system].items() if pkg == package)

        with tempfile.TemporaryDirectory() as base, \
                patch.object(install, "find_tool", side_effect=component), \
                patch.object(install, "install_package", side_effect=prepare), \
                patch.object(install, "binary", return_value="winget" if manager else None), \
                patch.object(install, "brew_path", return_value="brew" if manager else None), \
                patch.object(install, "probe", return_value=base):
            (Path(base) / "bin").mkdir()
            install.prepare_dependencies(system, "arm64", Path(base), {"PATH": ""}, io.StringIO(),
                                         allow_install=allow_install)
        return calls

    def test_healthy_systems_never_invoke_package_manager(self):
        for system in ("Windows", "Darwin"):
            self.assertEqual(self.exercise(system, manager=False), [])

    def test_windows_old_node_and_missing_media_tools(self):
        self.assertEqual(self.exercise("Windows", ("node", "ffmpeg", "ffprobe")),
                         ["OpenJS.NodeJS.LTS", "Gyan.FFmpeg"])
        self.assertEqual(self.exercise("Windows", ("ffprobe",)), ["Gyan.FFmpeg"])

    def test_windows_requires_winget_only_for_missing_tools(self):
        with self.assertRaisesRegex(ValueError, "Windows App Installer"):
            self.exercise("Windows", ("node",), manager=False)

    def test_missing_browser_and_macos_dependency_use_exact_packages(self):
        self.assertEqual(self.exercise("Windows", ("browser",)), ["Google.Chrome"])
        self.assertEqual(self.exercise("Darwin", ("ffmpeg", "ffprobe", "browser")), ["ffmpeg", "google-chrome"])

    def test_windows_browser_uses_environment_from_python_snapshot(self):
        program_files = Path("C:/Program Files")
        paths = list(install.browser_candidates("Windows", {"PROGRAMFILES": str(program_files)}))
        self.assertIn(program_files / "Google/Chrome/Application/chrome.exe", paths)
        self.assertIn(program_files / "Microsoft/Edge/Application/msedge.exe", paths)

    def test_package_failure_and_absent_executable_after_success(self):
        for system in ("Windows", "Darwin"):
            with self.subTest(system=system), self.assertRaisesRegex(ValueError, "install failed"):
                self.exercise(system, ("ffmpeg",), succeeds=False)
        with self.assertRaisesRegex(ValueError, "Could not verify ffprobe"):
            self.exercise("Windows", ("ffprobe",), appears=False)

    def test_existing_only_reports_missing_components(self):
        with self.assertRaisesRegex(ValueError, "Existing-components.*node"):
            self.exercise("Windows", ("node",), allow_install=False)

    def test_runtime_prioritizes_verified_bins_and_rejects_shadowing(self):
        tools = {name: (str(Path(sys.executable).parent / "deps" / name), "fixture")
                 for name in install.TOOLS}
        env = {"PATH": "inherited"}
        with patch.object(install, "binary", side_effect=lambda name, *_: tools[name][0]):
            runtime = install.runtime_environment(tools, env, "Windows")
        self.assertEqual(runtime[1].split(os.pathsep)[0], str(Path(tools["node"][0]).parent))
        self.assertEqual(env["CHROME_PATH"], tools["browser"][0])
        with patch.object(install, "binary", return_value=sys.executable):
            with self.assertRaisesRegex(ValueError, "verified node"):
                install.runtime_environment(tools, {}, "Windows")

    def test_windows_lookup_ignores_implicit_current_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "node.exe"
            with patch.object(install.shutil, "which", return_value="node.exe") as unsafe_lookup:
                self.assertIsNone(install.binary("node", str(path.parent), "Windows"))
                self.assertIsNone(install.binary("node", ".", "Windows"))
                path.touch()
                self.assertEqual(install.binary("node", str(path.parent), "Windows"), str(path))
                unsafe_lookup.assert_not_called()

    def test_native_brew_path_matches_process_architecture(self):
        with patch.object(Path, "is_file", return_value=True):
            self.assertEqual(install.brew_path("arm64", {}), "/opt/homebrew/bin/brew")
            self.assertEqual(install.brew_path("x86_64", {}), "/usr/local/bin/brew")

    def test_missing_brew_calls_consent_entrypoint(self):
        with patch.object(install, "find_tool", return_value=None), \
                patch.object(install, "brew_path", return_value=None), \
                patch.object(install.subprocess, "run") as run:
            run.side_effect = subprocess.CalledProcessError(2, "consent declined")
            with self.assertRaises(subprocess.CalledProcessError):
                install.prepare_dependencies("Darwin", "arm64", Path("bundle"), {}, io.StringIO())
            run.assert_called_once_with(["/bin/bash", str(Path("bundle/setup.sh")), "--prepare-brew"], check=True)
