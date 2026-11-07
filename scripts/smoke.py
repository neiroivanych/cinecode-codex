#!/usr/bin/env python3
"""Opt-in 160x90, 48-frame offline smoke. Run only after native discovery PASS."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import cc

HTML = """<!doctype html><meta charset="utf-8">
<canvas id="c" width="160" height="90"></canvas><script>
const c=document.getElementById('c'),g=c.getContext('2d');
window.renderFrame=i=>{
  g.fillStyle='#204060';g.fillRect(0,0,160,90);
  g.fillStyle='#ffe080';g.fillRect((i*3)%132,30,24,24);
};
window.captureFrame=(i,type='image/png',quality=.95)=>{
  window.renderFrame(i);return c.toDataURL(type,quality);
};
window.READY=Promise.resolve({frames:48,fps:24,width:160,height:90,renderer:'Canvas2D synthetic'});
</script>
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--discovery", required=True, help="successful native_discovery.py summary.json")
    p.add_argument("--out", required=True, help="new directory under evidence/local/")
    a = p.parse_args()
    cc.require_vendor()
    discovery = json.loads(Path(a.discovery).read_text(encoding="utf-8"))
    skill_hash = cc.digest(cc.ROOT / ".agents/skills/cinecode/SKILL.md")
    if not (discovery.get("discovery_pass") and discovery.get("explicit_invocation_pass") and
            discovery.get("skill_sha256") == skill_hash and
            discovery.get("upstream_manifest_sha256") == cc.digest(cc.ROOT / "cinecode.sha256.json")):
        raise ValueError("native discovery and explicit invocation must PASS for this skill revision")
    out = Path(a.out).resolve()
    if not out.is_relative_to(cc.ROOT / "evidence/local") or out.exists():
        raise ValueError("output must be a new directory under evidence/local/")
    return run_smoke(out)


def run_smoke(out, workspace=None, *, probe_gpu=True):
    """Shared offline fixture. CLI callers retain the discovery gate in main()."""
    out.mkdir(parents=True)
    result = {"status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat(),
              "upstream_commit": cc.PIN, "scope": "offline synthetic only, 160x90, 24fps, 48 frames",
              "commands": []}
    env = cc.child_env(cc.workspace_path(workspace))
    browser = cc.browser_path()

    def run(label, cmd):
        r = subprocess.run([str(x) for x in cmd], cwd=cc.ROOT, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        (out / (label + ".log")).write_text(r.stdout + r.stderr, encoding="utf-8")
        result["commands"].append({"label": label, "argv": [str(x) for x in cmd], "exit": r.returncode})
        (out / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if r.returncode:
            raise RuntimeError(label + " failed; see " + str(out / (label + ".log")))
        return r.stdout

    try:
        if not browser:
            raise ValueError("browser missing")
        env["CHROME_PATH"] = browser
        fixture = out / "fixture.html"
        fixture.write_text(HTML, encoding="utf-8")
        capture = cc.ROOT / "cinecode/scripts/capture.mjs"
        base = ["node", capture, "--url", fixture]
        if probe_gpu:
            probe = run("gpu-probe", ["node", capture, "--url", cc.ROOT / "cinecode/starter/index.html",
                                      "--probe", "--params", "w=64&h=36"])
            result["gpu_probe"] = probe.strip()
        else:
            result["gpu_probe"] = "NOT RUN (Canvas-only CI scope)"
        verify = run("determinism", base + ["--verify"])
        if "IDENTICAL" not in verify:
            raise RuntimeError("determinism did not report IDENTICAL")
        frames = out / "frames"
        for label in ("frames-first", "frames-resume"):
            status = out / (label + ".json")
            run(label, base + ["--out", frames, "--frames", "0,12,24", "--workers", "1", "--status", status])
            s = json.loads(status.read_text())
            want = (3, 0) if label == "frames-first" else (0, 3)
            if s["state"] != "done" or (s["done"], s["skipped"]) != want:
                raise RuntimeError("unexpected frame/resume counts")
        result["frame_hashes"] = {x.name: cc.digest(x) for x in sorted(frames.glob("*.png"))}
        picture = out / "picture.mp4"
        run("encode", base + ["--video", picture, "--workers", "1", "--status", out / "video.json"])
        av = out / "av-smoke.mp4"
        run("mux", ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-n", "-i", picture,
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                    "-ar", "48000", "-t", "2", av])
        text = run("ffprobe", ["ffprobe", "-v", "error", "-count_frames", "-show_streams",
                               "-show_format", "-of", "json", av])
        meta = json.loads(text)
        (out / "ffprobe.json").write_text(text, encoding="utf-8")
        v = next(s for s in meta["streams"] if s["codec_type"] == "video")
        audio = next(s for s in meta["streams"] if s["codec_type"] == "audio")
        expected = {"codec_name": "h264", "width": 160, "height": 90, "pix_fmt": "yuv420p",
                    "r_frame_rate": "24/1", "nb_read_frames": "48", "color_space": "bt709",
                    "color_primaries": "bt709", "color_transfer": "bt709", "color_range": "tv"}
        if any(v.get(k) != value for k, value in expected.items()):
            raise RuntimeError("video metadata mismatch")
        if audio["codec_name"] != "aac" or audio["sample_rate"] != "48000":
            raise RuntimeError("audio metadata mismatch")
        if abs(float(meta["format"]["duration"]) - 2) > 1 / 24:
            raise RuntimeError("duration mismatch")
        run("decode", ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-xerror", "-i", av, "-f", "null", "-"])
        env["QC_OUT"] = str(out / "qc")
        run("motion-hook", [sys.executable, "-B", cc.ROOT / "cinecode/scripts/qc.py", "hook", av])
        result.update(status="PASS", video=v, audio=audio, duration=meta["format"]["duration"],
                      output_sha256=cc.digest(av), frame_test="PASS", mp4_test="PASS")
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
        result.update(status="FAIL", error=str(e))
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "evidence": str(out), "error": result.get("error")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
