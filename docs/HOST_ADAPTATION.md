# Codex host adaptation

This file translates host-specific instructions in the unmodified upstream.
Keep CineCode's Quick/Film creative methodology; apply these host mappings when
an upstream example assumes Claude Code. No Claude Skill tool, SendUserFile,
wrap_up, ccd session API or lifecycle hook is installed here.

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
then replaces only the new project's generated AGENTS pointer with Codex
guidance. Copied tools are not patched. It does not render. Existing projects
are refused; resume them from STATE.md rather than reinitializing.
Film methodology remains available with --mode film but has not been qualified
end-to-end by this MVP.

The tool launcher accepts a small list of local tools and passes arguments as
argv, with an explicit project cwd. It returns their actual exit code.
It is not a general-purpose subprocess security sandbox: authored HTML/scripts
and tool arguments must be reviewed. Do not run an untrusted film project.

## Upstream instruction -> Codex behavior

| Upstream assumption | Adapter behavior |
|---|---|
| Skill tool activates hooks | Native repo skill loads instructions; no hooks bridge |
| AskUserQuestion / AskQuestion | Available host question tool or clear text; retain actual user answer |
| SendUserFile / wrap_up | Host preview or absolute local media link; ordinary turn completion |
| run_in_background | Current exec session plus durable status/log/exit record |
| Claude transcripts / usage.py / helper model names | No equivalent meter claimed; record known status and UNKNOWN usage |
| ccd start_session / claude:// / handoff.py | Checkpoint files; continue current chat, create another only when requested |
| Automatic update-tools on resume | Keep project tools pinned; explicit reviewed update only |
| ~/.cinecode default storage | Supported paths redirected into workspace/.cinecode-state |
| qc.py all exit0 | Inspect report and relevant deciding checks; not all-checks-PASS |

The active Codex session's sandbox and approvals still apply. A browser startup
failure is a failure in that execution mode. Do not silently disable the browser
sandbox, change OS graphics settings or install another browser.

## Checkpoint and gates

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

## Reduced protection and remaining incompatibilities

Protection is REDUCED_NO_HOOKS. The adapter provides workflow instructions,
pin verification and supported state redirection. It does not intercept every
tool, prove that an artifact was seen, parse Claude transcripts, enforce helper
ownership, meter context, or make upstream's fail-open guard fail-closed.

Supported CINECODE_* stores and browser TEMP/TMP are project-owned. HOME,
USERPROFILE and CODEX_HOME are not reassigned. Fonts.py has a hard-coded global
cache and is not exposed by this runner. Asset search, fonts, sound/sample
downloads, TTS, keys, usage and handoff tools are likewise not exposed as runner
commands; approval of external work requires reviewing the exact direct
invocation, storage and licenses first. This release is not a network firewall.
The three.js starter and some typography load CDN assets: they are not an
offline-qualified route. The synthetic fixture uses no fonts, libraries or
remote resources.

Capture resume stamps do not validate cached output bytes. --verify tests only
one selected repeat/order sequence on that host. It does not prove cross-GPU
parity, exact Shared Core semantics or recipe identity.

## Qualification and upstream updates

See QUALIFICATION.md for actual platform evidence. Doctor is not native
discovery. Native discovery is not a full-film test. The synthetic smoke is not
a rendered Quick film, a mastered soundtrack or codec-shipping certification.

No automatic upstream updates. A future reviewed update must replace the exact
snapshot, update the code pin/lock/manifest/notices together, and repeat relevant
tests. A SHA-256 manifest detects drift against the reviewed lock; it is not a
digital signature or protection against someone replacing all trust anchors.
