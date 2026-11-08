#!/usr/bin/env python3
"""Build a bootstrap ZIP from an exact Git commit."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "installer"))
from install import validate_names


# Stored members keep release bytes independent of the host compressor.
ARCHIVE_METHOD = zipfile.ZIP_STORED


PLATFORMS = {
    "windows": ("Windows", "INSTALL_CINECODE.cmd", "setup.ps1"),
    "macos": ("macOS", "INSTALL_CINECODE.command", "setup.sh"),
}


def build(root, source, system, output, expected_version=None):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    commit = git("rev-parse", "--verify", "--end-of-options", f"{source}^{{commit}}").decode().strip()
    entries = {}
    for row in git("ls-tree", "-rz", commit).split(b"\0"):
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        mode, kind, _ = metadata.decode().split()
        path = raw_path.decode("utf-8")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError(f"Unsupported tracked path: {path}")
        entries[path] = int(mode, 8) & 0o777
    validate_names(entries)
    # cat-file batch reads committed blobs without checkout filters or archive exclusions.
    requests = b"".join(f"{commit}:{path}\n".encode() for path in entries)
    batch = io.BytesIO(subprocess.run(["git", "cat-file", "--batch"], cwd=root,
                                      input=requests, stdout=subprocess.PIPE, check=True).stdout)
    files = {}
    for path in entries:
        _, kind, size = batch.readline().split()
        assert kind == b"blob"
        data = batch.read(int(size))
        assert len(data) == int(size) and batch.read(1) == b"\n"
        files[path] = data
    version = files["VERSION"].decode().strip()
    if expected_version is not None and version != expected_version:
        raise ValueError(f"Commit VERSION is {version}, expected {expected_version}")
    metadata = json.loads(files["installer/manifest.json"])
    metadata.update(adapter_version=version, source_commit=commit, platform=system,
                    file_count=len(files), files={name: {"sha256": hashlib.sha256(data).hexdigest(),
                                                        "size": len(data), "mode": entries[name]}
                                                  for name, data in sorted(files.items())})
    label, entry, setup = PLATFORMS[system]
    prefix = f"installer/{system}/"
    launchers = {name: files[prefix + name] for name in (entry, setup, "README-INSTALL.txt")}
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"CineCode-Setup-{label}.zip"
    with zipfile.ZipFile(destination, "x", compression=ARCHIVE_METHOD) as archive:
        def write(name, data, mode=0o644):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, data, compress_type=ARCHIVE_METHOD)

        for name, data in launchers.items():
            write(name, data, 0o755 if system == "macos" and name != "README-INSTALL.txt" else 0o644)
        write("install.py", files["installer/install.py"])
        write("manifest.json", (json.dumps(metadata, sort_keys=True, indent=2) + "\n").encode())
        for path in sorted(files):
            write(f"payload/cinecode-codex/{path}", files[path], entries[path])
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=PLATFORMS, required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--version")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        destination = build(ROOT, args.ref, args.platform, args.out, args.version)
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Packaging failed: {exc}\n")
    print(f"{hashlib.sha256(destination.read_bytes()).hexdigest()}  {destination}")


if __name__ == "__main__":
    main()
