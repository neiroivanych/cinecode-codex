#!/usr/bin/env python3
"""Exercise a committed bootstrap ZIP on a disposable GitHub-hosted runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "installer"))
import install
import native_discovery


PIN = "67f9807112b97ae253d4a5f0eccaccc46c3b2633"
EXPECTED_VERSION = "0.1.3-alpha"
EXPECTED_INSTALLER_VERSION = "0.1.0-alpha"
EXPECTED_TESTS = 68
WINDOWS = "Windows"
MAC = "Darwin"
BASE_ENV = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL",
            "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "USERPROFILE", "HOME",
            "TEMP", "TMP", "TMPDIR", "LOCALAPPDATA", "APPDATA", "ALLUSERSPROFILE", "CI",
            "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432", "SYSTEMDRIVE", "USER", "LOGNAME", "SHELL"}


class Qualification:
    def __init__(self, output):
        self.out = output
        output.mkdir()
        self.system = platform.system()
        self.key = {WINDOWS: "windows", MAC: "macos"}[self.system]
        self.base = Path(os.environ["RUNNER_TEMP"]).resolve() / "CineCode bootstrap テスト"
        self.base.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k.upper() in BASE_ENV}
        self.env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", CINECODE_SETUP_NO_PAUSE="1",
                        HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_INSTALL_CLEANUP="1",
                        TEMP=str(self.base.parent), TMP=str(self.base.parent), TMPDIR=str(self.base.parent))
        self.summary = {"sha": os.environ["GITHUB_SHA"], "runner_os": os.environ["RUNNER_OS"],
                        "arch": os.environ["RUNNER_ARCH"], "platform": platform.platform(),
                        "image": os.environ.get("ImageVersion"), "status": "FAIL"}
        self.receipt()

    def receipt(self):
        (self.out / "summary.json").write_text(json.dumps(self.summary, indent=2), encoding="utf-8")

    def run(self, name, args, *, cwd=ROOT, env=None, check=True, timeout=240):
        result = subprocess.run(args, cwd=cwd, env=self.env if env is None else env,
                                stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                                errors="replace", timeout=timeout)
        (self.out / f"{name}.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (self.out / f"{name}.stderr.txt").write_text(result.stderr, encoding="utf-8")
        if check and result.returncode:
            raise RuntimeError(f"{name} exited {result.returncode}. See its qualification logs.")
        return result

    def package(self):
        sha = self.summary["sha"]
        assert self.run("head", ["git", "rev-parse", "HEAD"]).stdout.strip() == sha
        assert self.summary["arch"] == ("X64" if self.system == WINDOWS else "ARM64")
        if self.system == MAC:
            self.summary["macos_version"] = self.run("macos-version", ["sw_vers", "-productVersion"]).stdout.strip()
            assert self.summary["macos_version"].startswith("15.")
        assert (ROOT / "VERSION").read_text().strip() == EXPECTED_VERSION
        build_dir = self.base / "ZIPs"
        self.run("package", [sys.executable, "-B", "installer/build/package.py", "--platform", self.key,
                             "--ref", sha, "--version", EXPECTED_VERSION, "--out", str(build_dir)])
        label, entry, script = ("Windows", "INSTALL_CINECODE.cmd", "setup.ps1") if self.system == WINDOWS else (
            "macOS", "INSTALL_CINECODE.command", "setup.sh")
        archive = build_dir / f"CineCode-Setup-{label}.zip"
        self.bundle = self.base / "Extracted package"
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.testzip() is None
            manifest_bytes = zipped.read("manifest.json")
            manifest = json.loads(manifest_bytes)
            tracked = self.run("tracked-paths", ["git", "ls-tree", "-rz", "--name-only", sha]).stdout.strip("\0").split("\0")
            install.validate_names(tracked)
            assert set(manifest["files"]) == set(tracked)
            payload_prefix = "payload/cinecode-codex/"
            expected = {entry, script, "manifest.json", "README-INSTALL.txt", "install.py"}
            expected.update(payload_prefix + name for name in tracked)
            assert set(zipped.namelist()) == expected and len(zipped.namelist()) == len(expected)
            for member in zipped.infolist():
                assert member.compress_type == zipfile.ZIP_STORED
                assert stat.S_ISREG(member.external_attr >> 16)
                if self.system == MAC and member.filename in (entry, script):
                    assert member.external_attr >> 16 & 0o777 == 0o755
        if self.system == WINDOWS:
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(self.bundle)
        else:
            self.run("extract", ["/usr/bin/ditto", "-x", "-k", str(archive), str(self.bundle)])
            assert all(os.access(self.bundle / name, os.X_OK) for name in (entry, script))
        metadata, _ = install.verify_payload(self.bundle, self.system)
        assert metadata["source_commit"] == sha and metadata["adapter_version"] == EXPECTED_VERSION
        assert metadata["schema_version"] == 1 and metadata["installer_version"] == EXPECTED_INSTALLER_VERSION
        assert metadata["file_count"] == len(tracked)
        (self.out / "manifest.json").write_bytes(manifest_bytes)
        shutil.copyfile(archive, self.out / archive.name)
        self.summary["archive"] = {"name": archive.name, "sha256": install.digest(archive),
                                   "file_count": len(tracked), "platform": self.key, "hashes": "PASS",
                                   "compression": "ZIP_STORED",
                                   "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                                   "payload_manifest_sha256": hashlib.sha256(json.dumps(
                                       metadata["files"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                                   "executable_bits": "PASS" if self.system == MAC else "N/A"}
        self.entry = self.bundle / entry

    def adapter_baseline(self):
        vendor = json.loads(self.run("vendor", [sys.executable, "-B", "scripts/cc.py", "verify"]).stdout)
        assert vendor == {"ok": True, "commit": PIN, "files": 168, "errors": []}
        result = self.run("regressions", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"])
        counts = re.search(r"Ran (\d+) tests", result.stderr)
        assert counts and int(counts[1]) == EXPECTED_TESTS and result.stderr.rstrip().endswith("OK")
        assert len(re.findall(r" \.\.\. ok$", result.stderr, re.M)) == EXPECTED_TESTS
        self.summary.update(vendor=vendor, regressions={"run": EXPECTED_TESTS, "pass": EXPECTED_TESTS,
                                                       "fail": 0, "skip": 0})

    def launcher(self, name, destination, env=None, *, check=True):
        if self.system == WINDOWS:
            cmd = Path(self.env["SYSTEMROOT"]) / "System32/cmd.exe"
            args = f'"{cmd}" /d /s /c ""{self.entry}" -Destination "{destination}""'
        else:
            args = [str(self.entry), "--destination", str(destination)]
        result = self.run(name, args, cwd=self.bundle, env=env, check=check, timeout=600)
        log_path = re.search(r"^Setup log: (.+)$", result.stdout, re.M)
        if log_path:
            setup_log = Path(log_path[1])
            if setup_log.is_file() and setup_log.name.startswith("cinecode-setup-"):
                shutil.copyfile(setup_log, self.out / f"{name}.setup.log")
        if check:
            assert "Payload verified." in result.stdout and "CineCode is ready." in result.stdout
            assert all(f"[{stage}/5]" in result.stdout for stage in range(1, 6))
            assert "type: $cinecode" in result.stdout
        return result

    def runtime(self, name, destination):
        runtime = (destination / ".cinecode-runtime").read_text(encoding="utf-8").splitlines()
        assert len(runtime) == 3 and Path(runtime[0]).is_file() and Path(runtime[2]).is_file()
        assert (destination / ".agents/skills/cinecode/SKILL.md").is_file()
        env = dict(self.env)
        env.pop("CHROME_PATH", None)
        if self.system == WINDOWS:
            env["PATH"] = os.pathsep.join(str(Path(self.env["SYSTEMROOT"]) / name) for name in ("System32", "."))
            shell = Path(self.env["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
            command = ("$r = Get-Content -LiteralPath .cinecode-runtime -Encoding UTF8; "
                       "$env:PATH = $r[1] + [IO.Path]::PathSeparator + $env:PATH; "
                       "$env:CHROME_PATH = $r[2]; $env:NoDefaultCurrentDirectoryInExePath = '1'; "
                       "& $r[0] -B scripts/cc.py $env:CINECODE_QUALIFY_COMMAND; exit $LASTEXITCODE")
            args = [str(shell), "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            env["PATH"] = "/usr/bin:/bin"
            command = ('{ IFS= read -r python_path; IFS= read -r runtime_path; IFS= read -r browser_path; } < .cinecode-runtime; '
                       'PATH="$runtime_path:$PATH" CHROME_PATH="$browser_path" "$python_path" -B scripts/cc.py "$CINECODE_QUALIFY_COMMAND"')
            args = ["/bin/bash", "-c", command]
        for check in ("verify", "doctor"):
            env["CINECODE_QUALIFY_COMMAND"] = check
            result = json.loads(self.run(f"{name}-runtime-{check}", args, cwd=destination, env=env).stdout)
            assert result["ok"]
            if check == "verify":
                assert result["files"] == 168 and result["commit"] == PIN and not result["errors"]
            else:
                assert result["adapter_version"] == EXPECTED_VERSION and result["protection"] == "REDUCED_NO_HOOKS"
                for tool in ("python", "node", "ffmpeg", "ffprobe", "browser"):
                    assert Path(result["checks"][tool]["path"]).is_file()
                return result

    def missing_media(self, destination):
        env = dict(self.env)
        if self.system == WINDOWS:
            winget = install.binary("winget", env.get("PATH", ""), WINDOWS)
            if not winget:
                return {"status": "NOT_QUALIFIED", "reason": "WinGet executable absent from the hosted PATH"}
            probe = self.run("winget-version", [winget, "--version"], check=False, timeout=30)
            if probe.returncode:
                return {"status": "NOT_QUALIFIED", "reason": f"WinGet --version exited {probe.returncode}"}
            env["PATH"] = os.pathsep.join(folder for folder in env["PATH"].split(os.pathsep) if folder and not any(
                (Path(folder) / f"{tool}.exe").is_file() for tool in ("ffmpeg", "ffprobe")))
            if not install.binary("winget", env["PATH"], WINDOWS):
                return {"status": "NOT_QUALIFIED", "reason": "Removing the media PATH also hides WinGet"}
        else:
            brew = install.brew_path("arm64", env)
            self.summary["homebrew"] = brew
            if not brew:
                return {"status": "NOT_QUALIFIED", "reason": "Homebrew absent from the hosted image"}
            if install.find_tool("ffmpeg", MAC, env):
                prefix = self.run("brew-ffmpeg-prefix", [brew, "--prefix", "ffmpeg"], check=False).stdout.strip()
                paths = [Path(found[0]).resolve() for name in ("ffmpeg", "ffprobe")
                         if (found := install.find_tool(name, MAC, env))]
                if not prefix or not all(path.is_relative_to(Path(prefix).resolve()) for path in paths):
                    return {"status": "NOT_QUALIFIED", "reason": "A resolved media tool is outside Homebrew's ffmpeg formula prefix"}
                users = self.run("brew-ffmpeg-dependents", [brew, "uses", "--installed", "ffmpeg"])
                if users.stdout.strip():
                    return {"status": "NOT_QUALIFIED", "reason": "Installed Homebrew dependents require FFmpeg",
                            "dependents": users.stdout.split()}
                self.run("remove-disposable-ffmpeg", [brew, "uninstall", "ffmpeg"], env=env)
        if any(install.find_tool(tool, self.system, env) for tool in ("ffmpeg", "ffprobe")):
            return {"status": "NOT_QUALIFIED", "reason": "Installer's actual search still finds a media executable"}
        result = self.launcher("missing-media", destination, env, check=False)
        expected = "via WinGet" if self.system == WINDOWS else "via Homebrew"
        if result.returncode:
            if expected in result.stdout and "Required component could not be installed" in result.stderr:
                return {"status": "NOT_QUALIFIED", "reason": "Hosted package manager rejected FFmpeg installation",
                        "exit": result.returncode, "log": "missing-media.setup.log"}
            raise RuntimeError("Native missing-media route failed after an eligible setup. See logs.")
        assert expected in result.stdout and "CineCode is ready." in result.stdout
        result = self.runtime("missing-media", destination)
        return {"status": "PASS", "ffmpeg": result["checks"]["ffmpeg"]["version"],
                "ffprobe": result["checks"]["ffprobe"]["version"]}

    def discovery(self, destination, doctor):
        prefix = self.base / "Isolated Codex CLI"
        node = doctor["checks"]["node"]["path"]
        if self.system == WINDOWS:
            cli_entry = Path(node).parent / "node_modules/npm/bin/npm-cli.js"
            command = [node, str(cli_entry)] if cli_entry.is_file() else []
        else:
            npm = shutil.which("npm", path=self.env.get("PATH"))
            command = [npm] if npm else []
        if not command:
            return {"status": "NOT_QUALIFIED", "reason": "npm unavailable"}
        package = self.run("provision-metadata-cli", command + ["install", "--prefix", str(prefix), "--ignore-scripts",
                           "--no-audit", "--no-fund", "@openai/codex@0.160.1"], check=False)
        cli = prefix / "node_modules/@openai/codex/bin/codex.js"
        if package.returncode or not cli.is_file():
            return {"status": "NOT_QUALIFIED", "reason": f"Isolated metadata CLI unavailable, npm exit {package.returncode}"}
        home = self.base / "empty Codex home"
        for name in (".codex", "tmp", "appdata", "localappdata"):
            (home / name).mkdir(parents=True, exist_ok=True)
        env = dict(self.env, HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / ".codex"),
                   APPDATA=str(home / "appdata"), LOCALAPPDATA=str(home / "localappdata"),
                   TEMP=str(home / "tmp"), TMP=str(home / "tmp"), TMPDIR=str(home / "tmp"))
        native_discovery.cc.ROOT = destination
        assert native_discovery.discover([node, str(cli)], env, self.out)
        data = json.loads((self.out / "skills-list.json").read_text(encoding="utf-8"))
        assert any(item.get("scope") == "repo" and item.get("enabled") for item in data["selected"])
        return {"status": "PASS", "method": "credential-free initialize + skills/list"}

    def qualify(self):
        self.adapter_baseline()
        self.package()
        self.receipt()
        destination = self.base / "Install テスト" / "cinecode-codex"
        before_media = [install.find_tool(tool, self.system, self.env) for tool in ("ffmpeg", "ffprobe")]
        first = self.launcher("install", destination)
        assert " · Install" in first.stdout
        doctor = self.runtime("install", destination)
        self.summary["install"] = "PASS"
        markers = {"workspace/film/STATE.md": b"fixture", "workspace/.cinecode-state/marker": b"state",
                   "user file.txt": b"user-owned"}
        for path, value in markers.items():
            item = destination / path
            item.parent.mkdir(parents=True, exist_ok=True)
            item.write_bytes(value)
        corrupted = destination / "scripts/cc.py"
        missing = destination / "README.md"
        expected = (corrupted.read_bytes(), missing.read_bytes())
        corrupted.write_bytes(b"disposable corruption")
        missing.unlink()
        assert " · Repair" in self.launcher("repair", destination).stdout
        assert (corrupted.read_bytes(), missing.read_bytes()) == expected
        assert all((destination / path).read_bytes() == value for path, value in markers.items())
        self.runtime("repair", destination)
        self.summary.update(repair="PASS", runtime_after_setup="PASS", workspace_state_user_files="PRESERVED",
                            installed_verify="PASS", installed_doctor="PASS")
        self.receipt()
        if self.system == MAC:
            self.summary["homebrew"] = install.brew_path("arm64", self.env)
            self.summary["homebrew_absent_native"] = "NOT_QUALIFIED"
            self.summary["gatekeeper"] = "NOT FULLY QUALIFIED"
        if not any(before_media) and "Preparing ffmpeg via" in first.stdout:
            self.summary["missing_component_native"] = {"status": "PASS", "phase": "first install"}
        else:
            self.summary["missing_component_native"] = self.missing_media(self.base / "Missing media" / "cinecode-codex")
        self.receipt()
        self.summary["native_discovery"] = self.discovery(destination, doctor)
        self.summary["status"] = "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        parser.error("Use a disposable GitHub-hosted runner")
    qualification = Qualification(args.out)
    try:
        qualification.qualify()
    except Exception as exc:
        qualification.summary["error"] = str(exc)
        raise
    finally:
        qualification.receipt()
        print(json.dumps(qualification.summary), flush=True)


if __name__ == "__main__":
    main()
