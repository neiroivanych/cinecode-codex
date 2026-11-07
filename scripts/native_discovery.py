#!/usr/bin/env python3
"""Opt-in native Codex discovery + ephemeral explicit invocation. Uses existing Codex sign-in."""
import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time

import cc


def codex_command(value=None):
    exe = value or shutil.which("codex")
    if not exe:
        raise ValueError("Codex executable not found; no installation is performed")
    p = Path(exe)
    if p.suffix.lower() == ".js":
        return ["node", str(p)]
    if p.suffix.lower() in (".cmd", ".ps1", ".bat"):
        entry = p.parent / "node_modules/@openai/codex/bin/codex.js"
        if not entry.is_file():
            raise ValueError("unsupported Codex shim; pass --codex path/to/codex.exe")
        return ["node", str(entry)]
    return [str(p)]


def discover(command, env, out):
    cmd = command + ["app-server", "--stdio", "-c", "features.hooks=false",
                     "-c", "features.apps=false", "-c", "analytics.enabled=false"]
    messages = queue.Queue()
    stderr = []
    proc = subprocess.Popen(cmd, cwd=cc.ROOT, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)

    def reader():
        for line in proc.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                pass
        messages.put(None)

    def err_reader():
        for line in proc.stderr:
            if sum(map(len, stderr)) < 24000:
                stderr.append(line)

    threading.Thread(target=reader, daemon=True).start()
    err_thread = threading.Thread(target=err_reader, daemon=True)
    err_thread.start()

    def send(value):
        proc.stdin.write(json.dumps(value) + "\n")
        proc.stdin.flush()

    def response(ident):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            msg = messages.get(timeout=max(0.1, deadline - time.monotonic()))
            if msg is None:
                raise RuntimeError("app-server closed before response")
            if msg.get("id") == ident:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"]))
                return msg["result"]
        raise RuntimeError("app-server response timeout")

    try:
        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "cinecode_codex_qualification",
                           "version": (cc.ROOT / "VERSION").read_text().strip()},
            "capabilities": {"experimentalApi": False}}})
        initialized = response(1)
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "skills/list", "params": {
            "cwds": [str(cc.ROOT)], "forceReload": True}})
        result = response(2)
        selected = []

        def walk(value):
            if isinstance(value, dict):
                if value.get("name") == "cinecode" and value.get("path"):
                    path = Path(value["path"])
                    if path.resolve() == (cc.ROOT / ".agents/skills/cinecode/SKILL.md").resolve():
                        selected.append(value)
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)

        walk(result)
        # Do not publish another user's skill catalog.
        data = {"initialization": initialized, "method": "skills/list",
                "selected": selected, "cwd": str(cc.ROOT)}
        (out / "skills-list.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        return bool(selected and all(s.get("enabled", True) for s in selected))
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        err_thread.join(timeout=1)
        (out / "app-server.stderr.log").write_text("".join(stderr), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--codex", help="native executable or npm codex.js entrypoint")
    p.add_argument("--out", required=True, help="new directory under evidence/local/")
    a = p.parse_args()
    cc.require_vendor()
    out = Path(a.out).resolve()
    if not out.is_relative_to(cc.ROOT / "evidence/local") or out.exists():
        raise ValueError("output must be new and under evidence/local/")
    out.mkdir(parents=True)
    command = codex_command(a.codex)
    env = cc.child_env(cc.workspace_path())
    # Existing Codex sign-in only; do not use a provider API key for qualification.
    env.pop("OPENAI_API_KEY", None)
    env.pop("CODEX_API_KEY", None)
    result = {"discovery_pass": False, "explicit_invocation_pass": False,
              "skill_sha256": cc.digest(cc.ROOT / ".agents/skills/cinecode/SKILL.md"),
              "upstream_manifest_sha256": cc.digest(cc.ROOT / "cinecode.sha256.json"),
              "scope": "native CLI/app-server, not a Desktop UI interaction test"}
    try:
        version = subprocess.run(command + ["--version"], cwd=cc.ROOT, env=env,
                                 capture_output=True, text=True, timeout=15)
        result["codex_version"] = version.stdout.strip()
        result["discovery_pass"] = discover(command, env, out)
        if not result["discovery_pass"]:
            raise RuntimeError("native skills/list did not discover enabled repository skill")
        prompt = ("$cinecode Compatibility inspection only. Using only the activated skill payload, "
                  "return its native invocation probe marker and its protection value exactly as written. "
                  "Do not use tools, read credentials, ask film questions, create files, install anything, "
                  "generate media or start a film. Do not invent values if the skill was not loaded.")
        cmd = command + ["exec", "--ignore-user-config", "--ephemeral", "--json",
                         "--sandbox", "read-only", "--disable", "hooks", "--disable", "apps",
                         "-c", "features.shell_tool=false", "-c", "analytics.enabled=false",
                         "-C", str(cc.ROOT), "-o", str(out / "last-message.txt"), prompt]
        r = subprocess.run(cmd, cwd=cc.ROOT, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        (out / "explicit-events.jsonl").write_text(r.stdout, encoding="utf-8")
        (out / "explicit.stderr.log").write_text(r.stderr, encoding="utf-8")
        answer_path = out / "last-message.txt"
        answer = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
        events = [json.loads(l) for l in r.stdout.splitlines() if l.strip().startswith("{")]
        tool_items = [e for e in events if e.get("type") in ("item.started", "item.completed")
                      and e.get("item", {}).get("type") in ("command_execution", "mcp_tool_call",
                                                          "web_search", "file_change")]
        result["explicit_exit"] = r.returncode
        result["tool_items"] = len(tool_items)
        result["explicit_invocation_pass"] = (
            r.returncode == 0 and not tool_items and
            "CINECODE_CODEX_SKILL_LOADED" in answer and "REDUCED_NO_HOOKS" in answer)
        if not result["explicit_invocation_pass"]:
            raise RuntimeError("explicit invocation did not meet no-tool marker/protection assertions")
    except (OSError, ValueError, RuntimeError, queue.Empty, subprocess.TimeoutExpired) as e:
        result["error"] = str(e)
    (out / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["discovery_pass"] and result["explicit_invocation_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
