#!/usr/bin/env python3
"""CineCode Codex adapter. Python standard library only; no automatic installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PIN = "67f9807112b97ae253d4a5f0eccaccc46c3b2633"
UPSTREAM = "https://github.com/sarpstar/cinecode"
TOOLS = {
    "capture": "capture.mjs", "make": "make.py", "qc": "qc.py",
    "scene-check": "scene_check.py", "validate-shots": "validate_shots.py",
    "mix": "mix.py", "master-audio": "master_audio.py",
    "words-check": "words_check.py", "captions": "captions.py",
    "beat-grid": "beat_grid.py", "brief": "brief.py", "snapshot": "snapshot.py",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root=ROOT):
    """Verify pinned metadata and the entire vendor file set, including unexpected files."""
    errors = []
    try:
        lock = json.loads((root / "upstream.lock.json").read_text(encoding="utf-8"))
        if lock["schema_version"] != 1 or lock["repository"] != UPSTREAM or lock["commit"] != PIN:
            raise ValueError("unsupported or changed upstream pin")
        if lock["directory"] != "cinecode" or lock["manifest"] != "cinecode.sha256.json":
            raise ValueError("unexpected vendor or manifest path")
        manifest_path = root / lock["manifest"]
        if digest(manifest_path) != lock["manifest_sha256"]:
            raise ValueError("manifest digest mismatch")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["schema_version"] != 1:
            raise ValueError("unsupported manifest schema")
        expected = {}
        for entry in manifest["files"]:
            name = entry["path"]
            parts = name.split("/")
            if (not name or "\\" in name or ":" in name or
                    any(p in ("", ".", "..") for p in parts) or name in expected):
                raise ValueError("unsafe or duplicate manifest path")
            expected[name] = entry
        if "LICENSE" not in expected or "SKILL.md" not in expected:
            raise ValueError("required upstream files missing from manifest")
        vendor = root / "cinecode"
        if vendor.is_symlink() or not vendor.is_dir():
            raise ValueError("vendor must be a real directory")
        actual = set()
        for base, dirs, files in os.walk(vendor, followlinks=False):
            blocked_dirs = []
            for name in dirs + files:
                p = Path(base) / name
                linked = p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                if linked or not p.resolve().is_relative_to(vendor.resolve()):
                    errors.append("linked resource: " + p.relative_to(vendor).as_posix())
                    if name in dirs:
                        blocked_dirs.append(name)
            dirs[:] = [name for name in dirs if name not in blocked_dirs]
            for name in files:
                p = Path(base) / name
                rel = p.relative_to(vendor).as_posix()
                actual.add(rel)
                if rel in expected and not p.is_symlink():
                    e = expected[rel]
                    if p.stat().st_size != e["bytes"] or digest(p) != e["sha256"]:
                        errors.append("changed: " + rel)
        errors += ["missing: " + p for p in sorted(set(expected) - actual)]
        errors += ["unexpected: " + p for p in sorted(actual - set(expected))]
        return {"ok": not errors, "commit": PIN, "files": len(expected), "errors": errors}
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {"ok": False, "commit": PIN, "errors": [str(e)]}


def workspace_path(value=None, root=ROOT):
    candidate = Path(value).expanduser() if value else root / "workspace"
    resolved = candidate.resolve()
    if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
        raise ValueError("workspace must not be a symlink or junction")
    if not value and resolved != root / "workspace":
        raise ValueError("default workspace must resolve inside the installation")
    if resolved == root or root.is_relative_to(resolved):
        raise ValueError("workspace cannot contain the adapter installation")
    if resolved.is_relative_to(root) and not resolved.is_relative_to(root / "workspace"):
        raise ValueError("in-repository projects belong under workspace/")
    return resolved


def project_path(name, workspace):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
        raise ValueError("project name: lowercase ASCII letters, digits and hyphens, max 64")
    p = workspace / name
    if (p.is_symlink() or getattr(p, "is_junction", lambda: False)() or
            not p.resolve().is_relative_to(workspace)):
        raise ValueError("project escapes workspace")
    return p


def child_env(workspace):
    """Redirect supported CineCode stores. This is not an OS security sandbox."""
    state = workspace / ".cinecode-state"
    tmp = state / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
               PYTHONIOENCODING="utf-8", CINECODE_NO_OPEN="1", CINECODE_DICE="offline",
               TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
    paths = {
        "CINECODE_KEYS": "keys.env", "CINECODE_FORMATS": "formats",
        "CINECODE_PYTHON_CACHE": "python.txt", "CINECODE_GUARD_SEEN": "guard-seen",
        "CINECODE_SPARKS": "sparks-seen.json", "CINECODE_FILMS": "films.json",
        "CINECODE_TASTE": "taste.json", "CINECODE_SHOWN": "shown.json",
        "CINECODE_SHOWN_MOVES": "shown-moves.json",
        "CINECODE_SHOWN_MUSIC": "shown-music.json",
        "CINECODE_SHOWN_SOUNDS": "shown-sounds.json",
        "CINECODE_SOUNDS_CACHE": "sounds", "CINECODE_SAMPLES_CACHE": "samples",
    }
    env.update({k: str(state / v) for k, v in paths.items()})
    return env


def browser_path(env=None, system=None):
    env = os.environ if env is None else env
    system = platform.system() if system is None else system
    if env.get("CHROME_PATH"):
        p = Path(env["CHROME_PATH"])
        return str(p) if p.is_file() else None
    if system == "Windows":
        bases = [env.get("PROGRAMFILES", "C:/Program Files"),
                 env.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")]
        candidates = [Path(b) / suffix for b in bases for suffix in (
            "Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe")]
        if env.get("LOCALAPPDATA"):
            candidates.append(Path(env["LOCALAPPDATA"]) / "Google/Chrome/Application/chrome.exe")
    elif system == "Darwin":
        candidates = [Path("/Applications") / p for p in (
            "Google Chrome.app/Contents/MacOS/Google Chrome",
            "Chromium.app/Contents/MacOS/Chromium",
            "Microsoft Edge.app/Contents/MacOS/Microsoft Edge")]
    else:
        candidates = [Path(p) for n in ("google-chrome", "google-chrome-stable", "chromium",
                                      "chromium-browser", "microsoft-edge")
                      for p in [shutil.which(n)] if p]
    return next((str(p) for p in candidates if p.is_file()), None)


def executable_check(name, args):
    exe = shutil.which(name)
    if not exe:
        return {"ok": False, "reason": "not found on PATH"}
    try:
        r = subprocess.run([exe] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
        first = (r.stdout or r.stderr).splitlines()
        return {"ok": r.returncode == 0, "path": exe,
                "version": first[0] if first else "", "exit_code": r.returncode}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "reason": type(e).__name__}


def doctor(workspace=None, root=ROOT):
    checks = {"upstream": verify(root)}
    skill = root / ".agents/skills/cinecode/SKILL.md"
    checks["skill_location"] = {"ok": skill.is_file(), "path": str(skill),
                               "native_discovery": "NOT_TESTED_BY_DOCTOR"}
    checks["python"] = {"ok": sys.version_info >= (3, 9), "version": platform.python_version(),
                        "path": sys.executable}
    checks["node"] = executable_check("node", ["--version"])
    match = re.match(r"v(\d+)", checks["node"].get("version", ""))
    checks["node"]["ok"] = bool(checks["node"]["ok"] and match and int(match[1]) >= 22)
    for tool in ("ffmpeg", "ffprobe"):
        checks[tool] = executable_check(tool, ["-version"])
    browser = browser_path()
    checks["browser"] = {"ok": bool(browser), "path": browser, "launch": "NOT_RUN"}
    try:
        ws = workspace_path(workspace, root)
        ws.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=ws) as f:
            f.write(b"doctor")
        checks["workspace"] = {"ok": True, "path": str(ws)}
    except (OSError, ValueError) as e:
        checks["workspace"] = {"ok": False, "reason": str(e)}
    system = platform.system()
    checks["os"] = {"ok": system in ("Windows", "Darwin", "Linux"), "detected": system,
                    "qualification": "See docs/QUALIFICATION.md; detection is not qualification"}
    return {"ok": all(c["ok"] for c in checks.values()),
            "adapter_version": (root / "VERSION").read_text().strip(),
            "checks": checks, "protection": "REDUCED_NO_HOOKS",
            "limitations": ["Doctor does not prove native skill discovery or browser startup.",
                            "No media, GPU, codec quality or full film is tested by doctor.",
                            "External-service and model tools are not exposed by this runner."]}


def require_vendor():
    result = verify()
    if not result["ok"]:
        raise ValueError("upstream verification failed: " + "; ".join(result["errors"][:5]))


def init_project(name, mode, workspace):
    require_vendor()
    project = project_path(name, workspace)
    if project.exists():
        raise ValueError("project exists; resume from STATE.md or choose another name")
    workspace.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-B", str(ROOT / "cinecode/scripts/init_film.py"), str(project)]
    if mode == "quick":
        cmd.append("--quick")
    r = subprocess.run(cmd, cwd=workspace, env=child_env(workspace))
    if r.returncode:
        return r.returncode
    # Replace only the adapter-created project guidance, never vendored files.
    (project / "AGENTS.md").write_text(
        "# CineCode Codex film project\n\n"
        "Use the repository .agents/skills/cinecode/SKILL.md and docs/HOST_ADAPTATION.md.\n"
        "Host adapter instructions take precedence over Claude-specific upstream examples.\n"
        "Read STATE.md and notes before resuming. Never update tools automatically.\n"
        "No hooks are installed; approvals must be actual user decisions.\n", encoding="utf-8")
    print("Project created. No film or media was generated.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    doc = sub.add_parser("doctor")
    doc.add_argument("--workspace")
    init = sub.add_parser("init")
    init.add_argument("name")
    init.add_argument("--mode", choices=("quick", "film"), default="quick")
    init.add_argument("--workspace")
    tool = sub.add_parser("tool")
    tool.add_argument("project")
    tool.add_argument("--workspace")
    tool.add_argument("tool", choices=sorted(TOOLS))
    tool.add_argument("args", nargs=argparse.REMAINDER)
    a = parser.parse_args(argv)
    try:
        if a.command in ("doctor", "verify"):
            result = doctor(a.workspace) if a.command == "doctor" else verify()
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 1
        ws = workspace_path(a.workspace)
        if a.command == "init":
            return init_project(a.name, a.mode, ws)
        require_vendor()
        project = project_path(a.project, ws)
        if not (project / "STATE.md").is_file():
            raise ValueError("no project STATE.md; do not infer a project from its filename")
        script = project / "tools" / TOOLS[a.tool]
        if not script.is_file():
            raise ValueError("tool not present in this project/mode")
        env = child_env(ws)
        if a.tool in ("make", "capture"):
            chrome = browser_path()
            if not chrome:
                raise ValueError("Chrome/Chromium/Edge missing; set CHROME_PATH or ask the owner")
            env["CHROME_PATH"] = chrome
        cmd = (["node", str(script)] if script.suffix == ".mjs" else
               [sys.executable, "-B", str(script)])
        args = a.args[1:] if a.args[:1] == ["--"] else a.args
        return subprocess.call(cmd + args, cwd=project, env=env)
    except (OSError, ValueError) as e:
        print("cinecode-codex: " + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
