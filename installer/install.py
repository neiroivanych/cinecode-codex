#!/usr/bin/env python3
"""Validate, install or repair an extracted CineCode bootstrap payload."""
import argparse
import hashlib
import json
import ntpath
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile


RECEIPT = ".cinecode-install.json"
RUNTIME = ".cinecode-runtime"
LOCK = ".cinecode-setup.lock"
VERSION_PATTERN = r"\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?"
TOOLS = ("node", "ffmpeg", "ffprobe", "browser")
PACKAGE_IDS = {
    "Windows": {"node": "OpenJS.NodeJS.LTS", "ffmpeg": "Gyan.FFmpeg",
                "ffprobe": "Gyan.FFmpeg", "browser": "Google.Chrome"},
    "Darwin": {"node": "node", "ffmpeg": "ffmpeg", "ffprobe": "ffmpeg", "browser": "google-chrome"},
}


def payload_path(name):
    if not isinstance(name, str) or not name or any(ord(c) < 32 or c in '\\:<>"|?*' for c in name):
        raise ValueError(f"Unsafe payload path: {name!r}")
    parts = name.split("/")
    lower = [part.casefold() for part in parts]
    blocked = {".git", "__pycache__", ".ds_store", "thumbs.db", ".cinecode-state", RECEIPT, RUNTIME, LOCK,
               "credentials.json", "auth.json", "secrets.json", "id_rsa", "id_ed25519"}
    reserved = getattr(ntpath, "isreserved", lambda p: PureWindowsPath(p).is_reserved())
    if (any(not p or p in (".", "..") or p.endswith((".", " ")) or reserved(p)
            for p in parts) or lower[0] == "workspace" or lower[:2] == ["evidence", "local"] or
            any(p in blocked or p == ".env" or p.startswith(".env.") or
                p.endswith((".pem", ".key", ".pfx", ".p12", ".pyc")) for p in lower)):
        raise ValueError(f"Unsafe or private payload path: {name}")
    return Path(*parts)


def validate_names(names):
    prefixes = {}
    for name in names:
        relative = payload_path(name)
        for part in (relative, *relative.parents):
            spelling = part.as_posix()
            if prefixes.setdefault(spelling.casefold(), spelling) != spelling:
                raise ValueError(f"Case-colliding payload path: {name}")


def guarded(path):
    for entry in [*reversed(path.parents), path]:
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"Linked setup path: {entry}")
    return path


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as data:
        for block in iter(lambda: data.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def matches(path, info):
    return path.is_file() and path.stat().st_size == info["size"] and digest(path) == info["sha256"]


def verify_payload(bundle, system):
    manifest = json.loads(guarded(bundle / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    expected = {"Windows": "windows", "Darwin": "macos"}[system]
    if (manifest["schema_version"] != 1 or manifest["platform"] != expected or
            not re.fullmatch(VERSION_PATTERN, manifest["installer_version"]) or
            not re.fullmatch(VERSION_PATTERN, manifest["adapter_version"]) or
            not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]) or
            not isinstance(files, dict) or len(files) != manifest["file_count"]):
        raise ValueError("Invalid setup manifest")
    required = {"VERSION", "adapter.json", "scripts/cc.py", ".agents/skills/cinecode/SKILL.md",
                "upstream.lock.json", "cinecode.sha256.json", "cinecode/SKILL.md"}
    if not required <= files.keys():
        raise ValueError("Setup manifest is missing required files")
    validate_names(files)
    payload = guarded(bundle / "payload/cinecode-codex")
    actual = set()
    for directory, dirs, names in os.walk(payload, followlinks=False):
        folder = Path(directory)
        for child in dirs + names:
            payload_path((folder / child).relative_to(payload).as_posix())
            guarded(folder / child)
        actual.update((folder / name).relative_to(payload).as_posix() for name in names)
    if actual != files.keys():
        raise ValueError("Extracted setup has missing or unexpected payload files")
    for name, info in files.items():
        path = guarded(payload / payload_path(name))
        if info["mode"] not in (0o644, 0o755) or not matches(path, info):
            raise ValueError(f"Setup payload is corrupted: {name}. Extract a fresh ZIP.")
    if (payload / "VERSION").read_text(encoding="utf-8").strip() != manifest["adapter_version"]:
        raise ValueError("Setup payload version differs from its manifest")
    return manifest, payload


def destination_path(value):
    home = Path.home()
    path = Path(os.path.abspath(value if value else home / "CineCode/cinecode-codex"))
    guarded(path)
    allowed = (home.resolve(), Path(tempfile.gettempdir()).resolve())
    if not any(path != parent and path.is_relative_to(parent) for parent in allowed):
        raise ValueError("Choose a CineCode folder inside your home or temporary directory")
    if platform.system() == "Windows":
        protected = [os.environ.get(key, fallback) for key, fallback in (
            ("SYSTEMROOT", "C:/Windows"), ("PROGRAMFILES", "C:/Program Files"),
            ("PROGRAMFILES(X86)", "C:/Program Files (x86)"), ("PROGRAMDATA", "C:/ProgramData"))]
    else:
        protected = ["/Applications", "/System", "/Library", "/usr/local", "/opt/homebrew"]
    if any(path.is_relative_to(Path(folder).resolve()) for folder in protected if folder):
        raise ValueError("Choose a CineCode folder outside system directories")
    return path


def install_plan(destination, manifest, *, locked=False):
    if not destination.exists():
        return False, list(manifest["files"])
    if not destination.is_dir() or (destination / ".git").exists():
        raise ValueError("Choose a dedicated CineCode installation folder")
    receipt_path = guarded(destination / RECEIPT)
    version_path = guarded(destination / "VERSION")
    if not locked and guarded(destination / LOCK).exists():
        raise ValueError("Another CineCode setup is running or was interrupted. See the setup guide.")
    if not receipt_path.exists() and not version_path.exists() and any(
            path.name != LOCK for path in destination.iterdir()):
        raise ValueError("This folder already contains files. Choose an empty CineCode folder.")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    if receipt and (receipt.get("schema_version") != 1 or not isinstance(receipt.get("files"), list)):
        raise ValueError("Existing CineCode setup receipt is invalid")
    try:
        version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else ""
    except UnicodeError:
        if not receipt:
            raise
        version = ""
    target = manifest["adapter_version"]
    if ((receipt and receipt.get("adapter_version") != target) or
            (version != target and (not receipt or re.fullmatch(VERSION_PATTERN, version)) and version_path.exists())):
        raise ValueError("A different CineCode version is already installed. Choose another folder.")
    owned = set(receipt.get("files", []))
    if guarded(destination / RUNTIME).exists() and not receipt:
        raise ValueError("Existing runtime settings do not belong to this setup")
    restore = []
    for name, info in manifest["files"].items():
        path = guarded(destination / payload_path(name))
        if path.exists():
            if not path.is_file():
                raise ValueError(f"Existing folder blocks a payload file: {name}")
            if matches(path, info):
                continue
            if name not in owned:
                raise ValueError(f"Existing file does not belong to this setup: {name}")
        restore.append(name)
    return bool(receipt or version), restore


def atomic_write(path, write):
    guarded(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".cinecode-setup-")
    os.close(fd)
    temporary = Path(temporary)
    try:
        write(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def copy_payload(source, target, info, system):
    def write(temporary):
        if system == "Darwin":
            # Native cp preserves extended attributes from the extracted package.
            subprocess.run(["/bin/cp", "-p", str(source), str(temporary)], check=True)
        else:
            shutil.copy2(source, temporary)
        if not matches(temporary, info):
            raise ValueError(f"Setup payload changed during copy: {source.name}")
        temporary.chmod(info["mode"])

    atomic_write(target, write)


def tool_directories(system, env):
    if system == "Darwin":
        return [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    local = Path(env["LOCALAPPDATA"]) if env.get("LOCALAPPDATA") else Path.home() / "AppData/Local"
    winget = local / "Microsoft/WinGet"
    program_files = Path(env.get("PROGRAMFILES", "C:/Program Files"))
    return [program_files / "nodejs", local / "Programs/nodejs", winget / "Links",
            *sorted((winget / "Packages").glob("Gyan.FFmpeg_*/*/bin"), reverse=True)]


def binary(name, search, system):
    for folder in search.split(os.pathsep):
        if not folder or not Path(folder).is_absolute():
            continue
        if system == "Windows":
            # shutil.which can implicitly search the current directory on Windows.
            candidate = Path(folder) / f"{name}.exe"
            if candidate.is_file():
                return str(candidate)
        else:
            found = shutil.which(name, path=folder)
            if found:
                return found
    return None


def brew_path(machine, env):
    candidates = ("/opt/homebrew/bin/brew", "/usr/local/bin/brew")
    if machine == "x86_64":
        candidates = candidates[::-1]
    return next((p for p in candidates if Path(p).is_file()), None) or binary("brew", env.get("PATH", ""), "Darwin")


def probe(command, env):
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def browser_candidates(system, env):
    if env.get("CHROME_PATH"):
        yield Path(env["CHROME_PATH"])
    if system == "Windows":
        roots = [Path(env[key]) for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if env.get(key)]
        names = ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe",
                 "Chromium/Application/chrome.exe")
    else:
        roots = [Path("/Applications"), Path.home() / "Applications"]
        names = ("Google Chrome", "Chromium", "Microsoft Edge")
        names = tuple(f"{name}.app/Contents/MacOS/{name}" for name in names)
    for root in roots:
        for name in names:
            yield root / name
    for executable in ("chrome", "chromium", "google-chrome", "msedge"):
        found = binary(executable, env.get("PATH", ""), system)
        if found:
            yield Path(found)


def find_tool(name, system, env):
    if name == "browser":
        for candidate in browser_candidates(system, env):
            if not candidate.is_absolute() or not candidate.is_file():
                continue
            if system == "Windows":
                powershell = Path(env.get("SYSTEMROOT", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
                version = probe([str(powershell), "-NoProfile", "-NonInteractive", "-Command",
                                 "(Get-Item -LiteralPath $env:CINECODE_BROWSER_PROBE).VersionInfo.ProductVersion"],
                                dict(env, CINECODE_BROWSER_PROBE=str(candidate)))
            else:
                version = probe([str(candidate), "--version"], env)
            if version:
                return str(candidate), version
        return None

    paths = [*env.get("PATH", "").split(os.pathsep), *map(str, tool_directories(system, env))]
    for folder in dict.fromkeys(paths):
        if not folder or not Path(folder).is_absolute():
            continue
        executable = binary(name, folder, system)
        if not executable:
            continue
        version = probe([executable, "--version" if name == "node" else "-version"], env)
        if name == "node":
            major = re.match(r"v(\d+)", version)
            valid = bool(major and int(major[1]) >= 22)
        else:
            valid = version.startswith(f"{name} version ")
        if valid:
            return executable, version.splitlines()[0]
    return None


def install_package(system, manager, package, env, log):
    if system == "Windows":
        command = [manager, "install", "--id", package, "--exact", "--source", "winget", "--silent",
                   "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"]
    else:
        command = [manager, "install"] + (["--cask"] if package == "google-chrome" else []) + [package]
    result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError(f"Required component could not be installed: {package}")


def prepare_dependencies(system, machine, bundle, env, log, *, allow_install=True):
    if system == "Darwin":
        env.update(HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_INSTALL_CLEANUP="1")
    found = {name: find_tool(name, system, env) for name in TOOLS}
    if not allow_install and not all(found.values()):
        missing = ", ".join(name for name in TOOLS if not found[name])
        raise ValueError(f"Existing-components check could not verify: {missing}")
    attempted = set()
    manager = None
    for name in TOOLS:
        if found[name]:
            continue
        if manager is None:
            if system == "Windows":
                manager = binary("winget", env.get("PATH", ""), system)
                if not manager:
                    raise ValueError("Windows App Installer / WinGet is required. See https://learn.microsoft.com/windows/package-manager/winget/")
            else:
                manager = brew_path(machine, env)
                if not manager:
                    subprocess.run(["/bin/bash", str(bundle / "setup.sh"), "--prepare-brew"], check=True)
                    manager = brew_path(machine, env)
                if not manager:
                    raise ValueError("Homebrew could not be located after setup")
                prefix = probe([manager, "--prefix"], env)
                if not Path(prefix).is_absolute() or not (Path(prefix) / "bin").is_dir():
                    raise ValueError("Homebrew did not report a usable installation prefix")
                env["PATH"] = str(Path(prefix) / "bin") + os.pathsep + env.get("PATH", "")
        package = PACKAGE_IDS[system][name]
        if package not in attempted:
            print(f"Preparing {'Google Chrome' if name == 'browser' else name} via {'WinGet' if system == 'Windows' else 'Homebrew'}...", flush=True)
            install_package(system, manager, package, env, log)
            attempted.add(package)
        for tool in TOOLS:
            if not found[tool]:
                found[tool] = find_tool(tool, system, env)
        if not found[name]:
            raise ValueError(f"Could not verify {name} after package setup")
    for name, value in found.items():
        print(f"{name}: {value[0]} ({value[1]})", file=log, flush=True)
    return found


def runtime_environment(tools, env, system):
    directories = [str(Path(tools[name][0]).parent) for name in TOOLS[:-1]]
    directories.append(str(Path(sys.executable).parent))
    prefix = os.pathsep.join(dict.fromkeys(directories))
    browser = tools["browser"][0]
    runtime = [sys.executable, prefix, browser]
    if any("\n" in value or "\r" in value for value in runtime):
        raise ValueError("An installed component has an unsupported path")
    env["PATH"] = prefix + os.pathsep + env.get("PATH", "")
    env["CHROME_PATH"] = browser
    if system == "Windows":
        env["NoDefaultCurrentDirectoryInExePath"] = "1"
    for name in TOOLS[:-1]:
        active = binary(name, env["PATH"], system)
        if not active or Path(active).resolve() != Path(tools[name][0]).resolve():
            raise ValueError(f"Could not select the verified {name} in the runtime environment")
    return runtime


def setup(bundle, destination, log, *, allow_install=True):
    system, machine = platform.system(), platform.machine().lower()
    if system not in PACKAGE_IDS or machine not in ("amd64", "x86_64", "arm64", "aarch64"):
        raise ValueError(f"Unsupported computer: {system} {machine}")
    print("[1/5] Checking your computer...", flush=True)
    manifest, payload = verify_payload(bundle, system)
    repair, restore = install_plan(destination, manifest)
    parent = next(p for p in (destination, *destination.parents) if p.exists())
    required = 10 * 1024 * 1024 + sum(manifest["files"][p]["size"] for p in restore)
    free = shutil.disk_usage(parent).free
    if free < required:
        raise ValueError("Free up disk space for the CineCode payload and run setup again")
    print(f"{system} {machine} · setup {manifest['installer_version']} · CineCode {manifest['adapter_version']} · {'Repair' if repair else 'Install'}")
    print(f"Payload verified. Available disk: {free // (1024 * 1024)} MiB.")
    print("[2/5] Preparing required components...", flush=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    print(f"python: {sys.executable} ({platform.python_version()})", file=log, flush=True)
    tools = prepare_dependencies(system, machine, bundle, env, log, allow_install=allow_install)
    runtime = runtime_environment(tools, env, system)
    print("[3/5] Installing CineCode...", flush=True)
    destination.mkdir(parents=True, exist_ok=True)
    lock = guarded(destination / LOCK)
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(f"{os.getpid()}\n")
    try:
        _, restore = install_plan(destination, manifest, locked=True)
        receipt = {key: manifest[key] for key in ("schema_version", "adapter_version", "source_commit")}
        receipt["files"] = sorted(manifest["files"])
        atomic_write(destination / RECEIPT, lambda p: p.write_text(json.dumps(receipt) + "\n", encoding="utf-8"))
        for name in restore:
            relative = payload_path(name)
            copy_payload(guarded(payload / relative), destination / relative, manifest["files"][name], system)
        for name, info in manifest["files"].items():
            if not matches(guarded(destination / payload_path(name)), info):
                raise ValueError(f"Installed file failed its integrity check: {name}")
        # Older Windows Python may search cwd regardless of PATH. Check from an empty folder.
        with tempfile.TemporaryDirectory(prefix="cinecode-check-") as check_cwd:
            for stage, check in ((4, "verify"), (5, "doctor")):
                print(f"[{stage}/5] {'Verifying installation' if stage == 4 else 'Final check'}...", flush=True)
                result = subprocess.run([sys.executable, "-B", str(destination / "scripts/cc.py"), check],
                                        cwd=check_cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise ValueError(f"Installed CineCode did not pass {check}")
        atomic_write(destination / RUNTIME, lambda p: p.write_text("\n".join(runtime) + "\n", encoding="utf-8"))
    finally:
        lock.unlink()
    print(f"CineCode is ready.\nInstalled at: {destination}")
    if not shutil.which("codex", path=env.get("PATH", "")):
        print("CineCode is installed. Install/open Codex separately, then open the CineCode folder.")
    print("Open this folder in Codex, start a new chat, and type: $cinecode")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--existing-only", action="store_true", help="use installed components only")
    args = parser.parse_args()
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="cinecode-setup-",
                                         suffix=".log", delete=False) as log:
            print(f"CineCode Setup\nSetup log: {log.name}", flush=True)
            try:
                setup(Path(__file__).resolve().parent, destination_path(args.destination), log,
                      allow_install=not args.existing_only)
            except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
                print(str(exc), file=log, flush=True)
                print(f"CineCode setup could not finish.\n{exc}\nSee setup log: {log.name}", file=sys.stderr)
                return 2
    except OSError as exc:
        print(f"CineCode setup could not open its log: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
