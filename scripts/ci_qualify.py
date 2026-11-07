#!/usr/bin/env python3
"""Run bounded adapter qualification on a disposable Windows or macOS runner."""
import argparse
import io
import json
import os
from pathlib import Path
import platform
import plistlib
import queue
import re
import subprocess
import sys
import tempfile
import zipfile

import cc
import native_discovery
import smoke


def qualify(out, codex):
    out.mkdir(parents=True, exist_ok=False)
    summary = {
        "runner": {key: os.environ.get(key) for key in (
            "CI_RUNNER_LABEL", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion", "GITHUB_SHA")},
        "system": platform.platform(), "machine": platform.machine(),
        "version": (cc.ROOT / "VERSION").read_text().strip(),
        "codex_model_invocation": "NOT VERIFIED (no credential or model turn)",
        "codex_desktop": "NOT VERIFIED",
    }

    def command(label, args, cwd=cc.ROOT, env=None):
        try:
            result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env,
                capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            (out / f"{label}.log").write_text(str(exc), encoding="utf-8")
            raise
        (out / f"{label}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        return result

    def step(name, action):
        try:
            summary[name] = {"status": "PASS", **action()}
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError, AssertionError, KeyError) as exc:
            summary[name] = {"status": "FAIL", "error": str(exc)}
        print(f"{name}: {summary[name]['status']}", flush=True)

    with tempfile.TemporaryDirectory(prefix="cinecode-ci-") as temp:
        base = Path(temp).resolve()
        install = base / "relocated adapter with spaces"
        cwd = base / "unrelated cwd"
        cwd.mkdir()
        workspace = base / "external workspace with spaces"
        py = [sys.executable, "-B"]
        exported = subprocess.check_output(["git", "archive", "--format=zip", "HEAD"], cwd=cc.ROOT)
        with zipfile.ZipFile(io.BytesIO(exported)) as archive:
            archive.extractall(install)
        cli = py + [install / "scripts/cc.py"]

        def verify():
            result = command("verify-relocated", cli + ["verify"], cwd)
            data = json.loads(result.stdout)
            assert result.returncode == 0 and data["ok"] and data["files"] == 168, data
            return {"files": data["files"], "upstream": data["commit"], "relocated": True}

        def doctor():
            result = command("doctor", cli + ["doctor", "--workspace", workspace], cwd)
            data = json.loads(result.stdout)
            summary["doctor_components"] = data["checks"]
            assert result.returncode == 0 and data["ok"], "See doctor.log for component results"
            browser = Path(data["checks"]["browser"]["path"])
            if platform.system() == "Darwin":
                with (browser.parents[1] / "Info.plist").open("rb") as info:
                    version = plistlib.load(info)["CFBundleShortVersionString"]
            else:
                script = "(Get-Item -LiteralPath $env:CINECODE_CI_BROWSER).VersionInfo.ProductVersion"
                env = dict(os.environ, CINECODE_CI_BROWSER=str(browser))
                version_result = command("browser-version", ["pwsh", "-NoProfile", "-Command", script], env=env)
                assert version_result.returncode == 0, "Browser version query failed"
                version = version_result.stdout.strip()
            assert version, "Browser version missing"
            return {"browser_version": version}

        def regressions():
            result = command("regressions", py + ["-m", "unittest", "discover", "-s", "tests", "-v"], install)
            report = result.stdout + result.stderr
            count = re.search(r"Ran (\d+) tests?", report)
            assert count, "Regression runner did not report test count"
            counts = {"run": int(count[1]), "pass": len(re.findall(r" \.\.\. ok$", report, re.M)),
                      "fail": len(re.findall(r" \.\.\. (?:FAIL|ERROR)$", report, re.M)),
                      "skip": len(re.findall(r" \.\.\. skipped ", report, re.M)),
                      "containment_fixture": "junction" if os.name == "nt" else "directory symlink"}
            summary["test_counts"] = counts
            assert result.returncode == 0 and counts["run"] >= 20 and counts["pass"] == counts["run"], counts
            return counts

        def initialize():
            args = ["--workspace", workspace]
            result = command("init", cli + ["init", "ci-fixture", "--mode", "quick"] + args, cwd)
            assert result.returncode == 0, "No-media initialization failed"
            project = workspace / "ci-fixture"
            assert (project / "STATE.md").is_file() and not (install / "workspace").exists()
            assert (project / "tools/brief.py").read_bytes() == (install / "cinecode/scripts/brief.py").read_bytes()
            result = command("copied-brief", cli + ["tool", "ci-fixture"] + args + ["brief", "sound", "--task",
                             "inspect a synthetic local sound plan", "--writes", "audio/sfx/*", "--reads", "STATE.md",
                             "--done", "references resolved"], cwd)
            assert result.returncode == 0 and "What the picture does" in result.stdout, "Copied KIT lookup failed"
            assert not any(p.suffix.lower() in {".mp4", ".wav", ".png", ".jpg"} for p in project.rglob("*") if p.is_file())
            assert (workspace / ".cinecode-state/tmp").is_dir()
            return {"relocated": True, "external_workspace": True, "copied_kit_resolution": True, "media_created": False}

        def skill_package():
            skill = install / json.loads((install / "adapter.json").read_text(encoding="utf-8"))["skill"]
            first, frontmatter, _ = skill.read_text(encoding="utf-8").split("---", 2)
            assert not first.strip() and skill.parent.name == "cinecode"
            assert re.search(r"^name: cinecode$", frontmatter, re.M)
            assert re.search(r"^description: \S", frontmatter, re.M)
            assert (install / "docs/HOST_ADAPTATION.md").is_file() and (install / "cinecode/SKILL.md").is_file()
            return {"method": "static package validation"}

        def discovery():
            if not codex.is_file():
                return {"status": "UNVERIFIABLE", "reason": "CLI provisioning unavailable",
                        "setup": os.environ.get("CI_CODEX_SETUP")}
            # Allow only process/runtime variables. In particular, no API keys or GitHub token.
            allowed = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL",
                       "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA"}
            env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
            home = base / "empty native discovery home"
            home.mkdir()
            codex_home = home / ".codex"
            codex_home.mkdir()
            tmp = home / "tmp"
            tmp.mkdir()
            env.update(HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(codex_home),
                       APPDATA=str(home / "appdata"), LOCALAPPDATA=str(home / "localappdata"),
                       TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp), CI="true")
            version = command("codex-version", ["node", codex, "--version"], env=env)
            assert version.returncode == 0, "Codex CLI did not start"
            destination = out / "native-discovery"
            destination.mkdir()
            try:
                found = native_discovery.discover(["node", str(codex)], env, destination)
            except (RuntimeError, OSError, queue.Empty) as exc:
                return {"status": "UNVERIFIABLE", "version": version.stdout.strip(),
                        "reason": f"Metadata handshake unavailable: {exc}"}
            assert found, "Native skills/list did not find an enabled repo skill"
            return {"version": version.stdout.strip(), "method": "initialize + skills/list only"}

        def media():
            rc = smoke.run_smoke(out / "synthetic", workspace / "synthetic", probe_gpu=False)
            assert rc == 0, "Synthetic media failed. See synthetic/summary.json and logs."
            return {"scope": "synthetic Canvas and tone only", "full_quick": "NOT VERIFIED"}

        for name, action in (("vendor_relocation", verify), ("doctor", doctor), ("regressions", regressions),
                             ("external_workspace_init", initialize), ("skill_package", skill_package),
                             ("native_discovery", discovery), ("synthetic_media", media)):
            step(name, action)

    (out / "qualification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return int(any(isinstance(result, dict) and result.get("status") == "FAIL" for result in summary.values()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--codex", required=True, type=Path)
    args = parser.parse_args()
    sys.exit(qualify(args.out.resolve(), args.codex.resolve()))
