# Qualification — 0.1.0-alpha

**Experimental. Windows native-skill + tiny synthetic smoke PASS.**
Date: 2026-11-07, Asia/Bangkok. macOS: **NOT VERIFIED**.
Linux: **NOT VERIFIED**. No full Quick film or Film-mode run.

| Check | Actual result | Scope |
|---|---|---|
| Vendor verification | PASS, 168 exact Git-blob files | Pinned commit 67f9807112b97ae253d4a5f0eccaccc46c3b2633 |
| Drift tests | PASS | Same-size edit, deletion, unexpected file, changed manifest/pin, unsafe path |
| Doctor | PASS | Existing prerequisites and writable workspace; not render proof |
| Standalone export/relocation | PASS | Package path with spaces, cwd outside package, explicit external workspace; no research dependency |
| Adapter regressions | PASS, 15 tests | Non-rendering stdlib tests, including relocation, missing tools, literal argv/cwd/exit propagation |
| Bundled Skill Creator validation | PASS | Skill frontmatter/naming; separate from native discovery |
| Native skill discovery | PASS | Real Codex app-server skills/list, scope=repo, enabled=true |
| Explicit invocation | PASS | Ephemeral $cinecode returned the marker and REDUCED_NO_HOOKS; zero tool calls |
| Deterministic frame probe | PASS | Same fixture frame24 twice, frame0 between |
| Frame capture/resume | PASS | Frames0/12/24; first rendered3/skipped0, second rendered0/skipped3 |
| Tiny MP4 | PASS | 160x90, 48 frames, 24fps, 2.000000s, H.264/yuv420p, BT.709 tags |
| Synthetic audio/mux | PASS | AAC, mono, 48kHz; stream starts0, declared duration2s |
| Full decode / motion hook | PASS | FFmpeg decode exit0; motion hook mean1.89, min1.637 |
| Desktop UI skill picker/playback | NOT RUN | Native CLI/app-server proof does not certify the visible Desktop UI |
| Full Quick / Film / three.js / typography / external services | NOT RUN | No end-to-end film or asset-quality claim |

Environment actually exercised: Windows 10.0.26200 x86_64 (build identifier),
Codex CLI/app-server0.160.1, Python3.14.3, Node26.4.0, FFmpeg/ffprobe8.1.2,
Chrome156.0.8078.80. WebGL2 READY diagnostic reported Intel Iris Xe via
ANGLE/D3D11. Synthetic captured frames use Canvas2D, not a qualified WebGL
renderer. Code paths for macOS/Linux exist but have not been run there.

These native/media checks ran in the approved host execution mode. Earlier
CC-01 sandbox Chrome startup failed on Crashpad; this release does not claim
that failure is fixed. One sandbox Git status attempt reported "must be run in
a work tree"; authorized host checks confirmed a normal non-bare repository.
Its root cause was not established. No browser --no-sandbox, global graphics changes or dependency installs
were used.

## Evidence

[Sanitized public summary](../evidence/qualification/windows-2026-11-07.json)
contains versions, exact assertions and output hashes. Raw commands/logs, native
events/answer, probe outputs, ffprobe JSON, PNG frames and MP4 are retained locally
under ignored evidence/local/native-02 and evidence/local/smoke-02. Personal paths
and account/session data are deliberately excluded from publication.

The original CC-01 research informed this adapter; it is not a runtime dependency
and its evidence was not edited. Vendor verification is against exact upstream
Git blobs, rather than Windows checkout line endings.

The first local import used git archive with inherited Windows CRLF conversion.
An independent Git-blob comparison caught this before commit/publication.
The snapshot was rebuilt from raw git cat-file blobs; the manifest was
regenerated and native/media checks repeated on those exact bytes. Earlier
attempt logs remain local and are not the final passing evidence.

## Readiness for a first real Quick experiment

The prerequisites, native instruction loading and tiny capture/encode path are
ready for a separately authorized **bounded local-asset Quick experiment**.
Open this repository in Codex and use its repository skill. This is not approval
to make that film now, nor a claim that the entire Quick workflow works.

Remaining gaps: no hooks, no automatic approval/presentation enforcement,
no Claude usage/handoff equivalence; font fetching has a global-cache issue;
three.js/fonts may need network assets; full audio/master/typography/story QA,
job interruption/resume, rendering inside a restricted sandbox, clean-machine
installation and cross-platform behavior remain unqualified. User taste and
listening decisions cannot be inferred from numerical checks.
