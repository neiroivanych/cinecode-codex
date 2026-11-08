"""Non-rendering release onboarding and generated-guidance regressions."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(
    r"\bClaud[e]\b|\bSendUserFil[e]\b|\bwrap_u[p]\b|\brun_in_backgroun[d]\b|"
    r"\bcc[d]\b|mcp__cc[d]|\bCurso[r]:|\bAskUserQuestio[n]\b|\bAskQuestio[n]\b|"
    r"\bHVP[C]\b|\bShared Cor[e]\b|CineCode-La[b]|\bLightfol[d]\b|"
    r"\bN[I][ _-]+(?:AI Creator Tools|integration|dependency|APIs)|"
    r"\b[C]C-0\d[\w-]*|\bcc0[1-9]_evidence|"
    r"[A-Z]:[\\/](?:cinecode-code[x](?:-user-test)?|Users[\\/])|"
    r"/(?:Users|home)/[^\s/]+",
    re.IGNORECASE,
)
PROJECT_GUIDANCE = (
    "`$cinecode`", ".agents/skills/cinecode/SKILL.md", "docs/HOST_ADAPTATION.md",
    "Keep the copied project tools pinned", "scripts/cc.py tool",
)


def adapter_paths():
    if (ROOT / ".git").exists():
        paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        return [ROOT / name for name in paths.decode("utf-8").split("\0")
                if name and not name.startswith("cinecode/")]
    # Standalone qualification runs from a Git archive, with no index.
    paths = []
    for directory, subdirs, files in os.walk(ROOT):
        base = Path(directory)
        subdirs[:] = [d for d in subdirs if d != "__pycache__"
                      and (base / d).relative_to(ROOT).as_posix() not in
                      {"cinecode", "workspace", "evidence/local"}]
        paths.extend(base / name for name in files)
    return sorted(paths)


def surface_findings(paths):
    findings = []
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        for number, value in enumerate([name, *path.read_text(encoding="utf-8").splitlines()]):
            findings.extend((name, number, match.group()) for match in FORBIDDEN.finditer(value))
    return findings


class Onboarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="cinecode-onboarding-")
        cls.addClassCleanup(tmp.cleanup)
        base = Path(tmp.name)
        cls.workspace = base / "external workspace"
        env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        env.pop("CINECODE_KIT", None)
        for mode in ("quick", "film"):
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts/cc.py"), "init", mode,
                 "--mode", mode, "--workspace", str(cls.workspace)],
                cwd=base, env=env, capture_output=True, encoding="utf-8", timeout=30,
            )
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)

    def assert_checkpoint_guidance(self, value):
        # Upstream fills the Kit fields with the current installation path.
        self.assertIsNone(FORBIDDEN.search(value.replace(str(ROOT / "cinecode"), "<kit>")))
        self.assertNotIn("--update-tools", value)
        for instruction in PROJECT_GUIDANCE:
            self.assertIn(instruction, value)

    def assert_state(self, mode, template):
        state = (self.workspace / mode / "STATE.md").read_text(encoding="utf-8")
        self.assert_checkpoint_guidance(state)
        original = template.read_text(encoding="utf-8").replace("<working title>", "Untitled")
        original = original.replace("<kit path>", str(ROOT / "cinecode"))
        actual, expected = state.splitlines(), original.splitlines()
        self.assertEqual(actual[:2] + actual[3:], expected[:2] + expected[3:])
        if mode == "quick":
            self.assertEqual(actual[2].split(". Kit: ", 1)[1], expected[2].split(". Kit: ", 1)[1])
        else:
            self.assertIn('update "Now"', actual[2])

    def test_readme_selects_release_before_checks(self):
        version = (ROOT / "VERSION").read_text().strip()
        self.assertEqual(version, "0.1.3-alpha")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        recommended = readme.split("## Recommended installation", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("git clone", recommended)
        for asset, launcher in (("Windows", "INSTALL_CINECODE.cmd"), ("macOS", "INSTALL_CINECODE.command")):
            self.assertIn(f"CineCode-Setup-{asset}.zip", recommended)
            self.assertIn(launcher, recommended)
        manual = "## Advanced / manual installation"
        self.assertLess(readme.index("## Recommended installation"), readme.index(manual))
        onboarding = readme.split(manual, 1)[1].split("\n## ", 1)[0]
        command_block = re.search(r"(?m)^[ \t]*~~~sh[ \t]*\n([\s\S]*?)^[ \t]*~~~[ \t]*$", onboarding)
        self.assertIsNotNone(command_block)
        commands = [shlex.split(line, comments=True) for line in command_block[1].splitlines()]
        self.assertEqual([command for command in commands if command], [
            ["git", "clone", "--branch", f"v{version}", "--single-branch",
             "https://github.com/neiroivanych/cinecode-codex.git"],
            ["cd", "cinecode-codex"],
            ["python", "-B", "scripts/cc.py", "verify"],
            ["python", "-B", "scripts/cc.py", "doctor"],
        ])
        self.assertIn(f"· `{version}`.", readme)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(changelog, rf"(?m)^## {re.escape(version)} — \d{{4}}-\d{{2}}-\d{{2}}$")
        self.assertEqual(json.loads((ROOT / "adapter.json").read_text())["version_file"], "VERSION")

    def test_quick_initial_state_preserves_upstream_fields(self):
        self.assert_state("quick", ROOT / "cinecode/templates/quick/STATE.md")

    def test_film_initial_state_and_handoff(self):
        self.assert_state("film", ROOT / "cinecode/templates/STATE.md")
        handoff = (self.workspace / "film/HANDOFF.md").read_text(encoding="utf-8")
        self.assert_checkpoint_guidance(handoff)
        original = (ROOT / "cinecode/templates/HANDOFF.md").read_text(encoding="utf-8")
        checklist = original.split("- [ ] Silent snapshot saved", 1)[0]
        self.assertTrue(handoff.startswith(checklist))
        self.assertIn("If the film has its own Git root", handoff)
        self.assertIn("scripts/cc.py tool NAME snapshot", handoff)
        self.assertIn("only at the user's request", handoff)
        interview = (self.workspace / "film/INTERVIEW.md").read_text(encoding="utf-8")
        self.assertIsNone(FORBIDDEN.search(interview))
        original = (ROOT / "cinecode/templates/INTERVIEW.md").read_text(encoding="utf-8")
        intro = original.split("when the environment has an interactive multiple-choice tool", 1)[0]
        questions = original.split("), USE IT: ", 1)[1]
        self.assertEqual(interview, intro + "when Codex offers an interactive multiple-choice tool, use it:\n  " + questions)

    def test_project_agents_in_both_modes(self):
        for mode in ("quick", "film"):
            with self.subTest(mode=mode):
                agents = (self.workspace / mode / "AGENTS.md").read_text(encoding="utf-8")
                self.assert_checkpoint_guidance(agents)
                self.assertIn("Approval gates require actual user decisions", agents)
                self.assertIn("REDUCED_NO_HOOKS", agents)

    def test_owner_language_rule_reaches_quick_film_and_precedes_upstream(self):
        skill = (ROOT / ".agents/skills/cinecode/SKILL.md").read_text(encoding="utf-8")
        surfaces = [skill.split("Read REPO/docs/HOST_ADAPTATION.md", 1)[0]]
        for mode in ("quick", "film"):
            surfaces.extend((self.workspace / mode / name).read_text(encoding="utf-8")
                            for name in ("STATE.md", "AGENTS.md"))
        for text in surfaces:
            prose = " ".join(text.split())
            explicit = prose.index("explicit current owner language request")
            conversation = prose.index("language of the current owner conversation")
            preference = prose.index("preference", conversation)
            self.assertLess(explicit, conversation)
            self.assertLess(conversation, preference)
            self.assertIn("scope", prose[explicit:conversation])
            self.assertIn("unclear", prose[preference:])
            self.assertRegex(prose, r"[Tt]echnical briefs, attached specifications, filenames, code, "
                                    r"subtitles, on-screen text, narration and logs do(?:es)? not set")

    def test_motion_review_guidance_requires_playback_without_a_universal_limit(self):
        docs = (ROOT / "docs/HOST_ADAPTATION.md").read_text(encoding="utf-8")
        motion = docs.split("## Perceptual motion review", 1)[1].split("\n## ", 1)[0]
        prose = " ".join(motion.split())
        self.assertIn("continuous MP4 at normal playback speed", prose)
        self.assertIn("`UNVERIFIED` when playback was not assessed", prose)
        self.assertIn("no universal px/frame threshold", prose)
        self.assertNotRegex(prose, r"\d+(?:\.\d+)?\s*px\s*/\s*frame")
        self.assertIn("preserve the approved temporal treatment in final", prose)
        for mode in ("quick", "film"):
            for name in ("STATE.md", "AGENTS.md"):
                with self.subTest(mode=mode, file=name):
                    guidance = (self.workspace / mode / name).read_text(encoding="utf-8")
                    self.assertIn("MP4 at normal playback speed", guidance)
                    self.assertIn("UNVERIFIED if playback was not assessed", guidance)

    def test_tracked_adapter_surface_has_no_forbidden_terms(self):
        paths = adapter_paths()
        self.assertIn(ROOT / "README.md", paths)
        self.assertEqual(surface_findings(paths), [])

    def test_separate_authorship_and_licenses(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Codex adapter created and maintained by [@neiroivanych](https://github.com/neiroivanych).", readme)
        self.assertIn("Sarp Yıldız (@sarpstar)", readme)
        meta = json.loads((ROOT / "adapter.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["author"], {"name": "neiroivanych", "url": "https://github.com/neiroivanych"})
        self.assertIn("Copyright (c) 2026 neiroivanych", (ROOT / "LICENSE").read_text(encoding="utf-8"))
        vendor_license = (ROOT / "cinecode/LICENSE").read_bytes()
        manifest = json.loads((ROOT / "cinecode.sha256.json").read_text(encoding="utf-8"))
        license_entry = next(entry for entry in manifest["files"] if entry["path"] == "LICENSE")
        self.assertEqual(hashlib.sha256(vendor_license).hexdigest(), license_entry["sha256"])

    def test_distribution_boundary_is_linked_and_standalone(self):
        path = "docs/DISTRIBUTION_BOUNDARY.md"
        self.assertIn(f"]({path})", (ROOT / "README.md").read_text(encoding="utf-8"))
        boundary = (ROOT / path).read_text(encoding="utf-8")
        for term in ("adapter.json", "VERSION", "upstream.lock.json", "--workspace", "package-relative", "external accounts"):
            self.assertIn(term, boundary)
