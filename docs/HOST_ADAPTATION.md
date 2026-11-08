# Codex host adaptation

This file translates host-specific instructions in the unmodified upstream.
Keep CineCode's Quick/Film creative methodology; apply these host mappings when
an upstream example relies on its own host. Codex discovers the repo-local
skill. Upstream lifecycle hooks and session APIs are unavailable.

## Local workflow

Resolve the installation from scripts/cc.py or the repository skill, not cwd.
Default projects live under installation-root/workspace/, ignored by Git.
An explicit --workspace path supports writable storage outside a read-only
installation. Never store a film inside cinecode/.

From the repository root, using python (or python3 where appropriate):

~~~sh
python -B scripts/cc.py verify
python -B scripts/cc.py doctor
# Only after a user requests a real film:
python -B scripts/cc.py init example --mode quick
python -B scripts/cc.py tool example make stills
~~~

The init command runs the upstream initializer with an absolute project path,
then normalizes the new project's STATE.md and AGENTS.md. For Film mode it
also updates host guidance in HANDOFF.md and INTERVIEW.md. The copied tools
remain pinned. Init creates the project
without rendering and refuses existing project directories. Resume an existing
project from STATE.md using the repository's `$cinecode` skill.
Film methodology remains available with --mode film but has not been qualified
end-to-end by this MVP.

The tool launcher accepts a small list of local tools and passes arguments as
argv, with an explicit project cwd. It returns their actual exit code.
It supplies the upstream-supported CINECODE_KIT variable from the adapter
installation's cinecode/ directory, so copied brief.py needs no caller override
and can read the pinned references after relocation.
It is not a general-purpose subprocess security sandbox: authored HTML/scripts
and tool arguments must be reviewed. Do not run an untrusted film project.

## Upstream instruction -> Codex behavior

| Upstream assumption | Adapter behavior |
|---|---|
| Skill activation triggers lifecycle hooks | Native repo skill loads instructions; no hooks bridge |
| Host question interface | Available host question tool or clear text; retain actual user answer |
| Host artifact presentation / turn completion | Host preview or absolute local media link; ordinary turn completion |
| Host background execution | Current exec session plus durable status/log/exit record |
| Upstream transcript-based usage and helper model selection | No equivalent meter claimed; record known status and UNKNOWN usage |
| Upstream session API and handoff mechanism | Checkpoint files; continue current chat, create another only when requested |
| Automatic update-tools on resume | Keep project tools pinned; explicit reviewed update only |
| ~/.cinecode default storage | Supported paths redirected into workspace/.cinecode-state |
| qc.py all exit0 | Inspect report and relevant deciding checks; not all-checks-PASS |

The active Codex session's sandbox and approvals still apply. A browser startup
failure is a failure in that execution mode. Do not silently disable the browser
sandbox, change OS graphics settings or install another browser.

## Checkpoint and gates

Use the explicit current owner language request within its intended scope.
Otherwise use the current owner conversation language, with a previously
established preference as fallback only when the conversation language is
unclear. Carry this rule through questions, production cards, progress notes,
owner gates, review prompts, revision summaries and delivery summaries.
Technical briefs, attached specifications, filenames, code, subtitles, on-screen
text, narration and logs do not set the conversation language. Keep technical
filenames, commands, code and machine-readable evidence in their technical format.

Update STATE.md before a handoff/gate: phase, actual approved gates, named
artifact/version shown, user music choice, open notes, one next action.
Save notes verbatim, split targeted changes, preserve Keep and unchanged shots.
Record running jobs with argv/cwd/PID/status/log and actual errors.
Check the real job/output on resume: a chat resume does not restore a process.
Do not automatically run snapshot.py in the adapter's parent Git repository;
upstream itself skips snapshots unless the film has its own Git root.

A pending question, a suggested choice, a line in STATE.md and elapsed time do
not constitute approval. A draft gate requires the user's decision on the
specific shown version. Don't infer final, cleanup, paid-service or publication
approval from a general film request.

## Perceptual motion review

Review potentially fast continuous motion as a continuous MP4 at normal playback
speed. Examples include zooms, pans, orbits, fast rotations, camera or object
passes and high-contrast edges crossing the frame. Spline continuity and frame
strips help diagnose timing, but cannot establish perceptual smoothness.
Frame-to-frame screen-space displacement is a diagnostic with no universal
px/frame threshold. Consider temporal exposure when the material warrants it.
Motion blur stays opt-in.

The normal Quick draft forces `shutter=0` and disables some finishing. Final
inherits the selected finishing. To review the intended exposure, use the
existing `cc.py tool PROJECT capture` with `--url`, `--video` and `--params`
for a separate project-local review MP4. A contiguous `--start`/`--end` range
can cover the affected interval. Present this picture-only capture as motion
evidence alongside any separate audio-video draft. Keep the intended FPS and scene settings,
including the actual shutter samples, angle, blur applicability and any sample
skip or always behavior. Use a short excerpt at final resolution if the preview
leaves thin edges or blur behavior ambiguous. A sharp draft cannot validate a
different temporal treatment.

In the checkpoint or review record, name the exact artifact shown (path or
version), FPS, playback assessment (`REVIEWED` for assessed playback or
`UNVERIFIED` when playback was not assessed), temporal treatment and actual
owner decision. The decision applies to the artifact shown. Repeat the motion
review after material timing or exposure changes and preserve the approved
temporal treatment in final. A separate capture supplies evidence for the gate.
The ordinary owner approval and upstream checks still apply.

## Programmatic score events

When deliberate events in `score()` are absent from upstream `SFX` and mix
metadata, keep a project-local `review/score-events.json` for the exact reviewed
or rendered MP4. The sidecar is optional. Record cues from the actual score or
production evidence. Schema 1 uses a SHA-256 hex digest of the whole MP4 and an
`events` array. Each event has a stable unique `id`, numeric `start` and `end`
in seconds from the beginning of the MP4, and one `category`. Use
`score_accent` for a deliberate cue in the score, `sfx` for a sound effect,
`foley` for action Foley, `music` for music and `ambience` for atmosphere.

```json
{
  "schema_version": 1,
  "media_sha256": "<SHA-256 of the MP4>",
  "events": [
    {"id": "transition-1", "start": 1.0, "end": 1.4, "category": "score_accent"}
  ]
}
```

Run `python -B scripts/cc.py score-events PROJECT "renders/draft v2.mp4"`.
The command uses project-relative paths and `ffprobe` for duration. Its JSON
reports `UNKNOWN` for an absent sidecar, `INVALID` for a failed validation and
`VALID` with counts by category when the hash and intervals match. An empty
list means zero declared events. The report measures neither audibility nor
owner listening.

Add `--check` to run the normal upstream `make check` for the same MP4 in a
trusted project. This mode writes the normal upstream QC files and includes
its output and exit code separately. The adapter checks the MP4 duration
before launching upstream QC, including when the optional sidecar is absent.
Validation errors skip the upstream command. A nonzero upstream exit is preserved.
Declarations do not feed the upstream `SOUND THIN` counter or change `HELD`.
The adapter count alone cannot establish whether the upstream density rule was met.

## Reduced protection and remaining incompatibilities

Protection is REDUCED_NO_HOOKS. The adapter provides workflow instructions,
pin verification and supported state redirection. It does not intercept every
tool, prove that an artifact was seen, parse upstream transcripts, enforce helper
ownership, meter context, or make upstream's fail-open guard fail-closed.

Supported CINECODE_* stores and browser TEMP/TMP are project-owned. HOME,
USERPROFILE and CODEX_HOME are not reassigned. Fonts.py has a hard-coded global
cache and is not exposed by this runner. Before preparing a child environment,
the launcher rejects pre-existing symlinks/junctions at .cinecode-state, its tmp
path and the exported mutable-store paths; all checks precede tmp creation and
child launch. These setup-time checks are not an OS sandbox or a guarantee
against concurrent path replacement.
Asset search, fonts, sound/sample
downloads, TTS, keys, usage and handoff tools are likewise not exposed as runner
commands; approval of external work requires reviewing the exact direct
invocation, storage and licenses first. This release is not a network firewall.
The three.js starter and some typography load CDN assets: they are not an
offline-qualified route. The synthetic fixture uses no fonts, libraries or
remote resources.

Capture resume stamps do not validate cached output bytes. --verify tests only
one selected repeat/order sequence on that host. It does not prove cross-GPU
parity across machines.

## Qualification and upstream updates

See QUALIFICATION.md for actual platform evidence. Doctor is not native
discovery. Native discovery is not a full-film test. The synthetic smoke is not
a rendered Quick film, a mastered soundtrack or codec-shipping certification.

No automatic upstream updates. A future reviewed update must replace the exact
snapshot, update the code pin/lock/manifest/notices together, and repeat relevant
tests. A SHA-256 manifest detects drift against the reviewed lock; it is not a
digital signature or protection against someone replacing all trust anchors.
