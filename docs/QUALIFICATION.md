# Qualification — 0.1.0-alpha

## Historical local Windows qualification

**Experimental. Windows native-skill + tiny synthetic smoke PASS.**
Date: 2026-11-07, Asia/Bangkok. This historical local run used Windows. That historical smoke did not run a full Quick film or Film mode.

| Check | Actual result | Scope |
|---|---|---|
| Vendor verification | PASS, 168 exact Git-blob files | Pinned commit 67f9807112b97ae253d4a5f0eccaccc46c3b2633 |
| Drift tests | PASS | Same-size edit, deletion, unexpected file, changed manifest/pin, unsafe path |
| Doctor | PASS | Existing prerequisites and writable workspace; not render proof |
| Standalone export/relocation | PASS | Package path with spaces, cwd outside package, explicit external workspace; standalone installation |
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
renderer. See the separate hosted qualification below for subsequent macOS results.

These native/media checks ran in the approved host execution mode. Earlier
sandbox Chrome startup failed on Crashpad; this release does not claim
that failure is fixed. One sandbox Git status attempt reported "must be run in
a work tree"; authorized host checks confirmed a normal non-bare repository.
Its root cause was not established. No browser --no-sandbox, global graphics changes or dependency installs
were used.

## Hosted Windows and macOS qualification

Both jobs passed on this published commit
`3e151ca82c5c8d4223fa8810c2188965568dc7e1`.
[GitHub Actions run 42349274464](https://github.com/neiroivanych/cinecode-codex/actions/runs/42349274464)

| Check | Windows | macOS |
| --- | --- | --- |
| Hosted runner | `windows-2025`, Server 2025 build 26100, x64 | `macos-15`, macOS 15.8.2, arm64 |
| Image | `win25-vs2026` `20261103.298.1` | `macos15` `20261104.0514.1` |
| Python / Node | 3.12.10 / 22.23.4 | 3.12.10 / 22.23.4 |
| FFmpeg / ffprobe | 9.0.2 Gyan essentials / 9.0.2 | 9.0.2 / 9.0.2 |
| Chrome | 156.0.8078.80 | 157.0.8103.39 |
| Adapter CI / vendor / doctor | PASS / 168 of 168 / PASS | PASS / 168 of 168 / PASS |
| Regressions | 20 run, 20 pass, 0 fail, 0 skip. Real junctions. | 20 run, 20 pass, 0 fail, 0 skip. Real directory symlinks. |
| Relocation / external workspace / copied KIT | PASS / PASS / PASS | PASS / PASS / PASS |
| Synthetic browser/media | PASS, selected-frame repeat, capture/resume, H.264/AAC metadata and full decode | PASS, same checks |
| Codex skill package | PASS | PASS |
| Native Codex discovery | PASS, credential-free `skills/list`, CLI 0.160.1 | PASS, credential-free `skills/list`, CLI 0.160.1 |
| Hosted model invocation | NOT VERIFIED | NOT VERIFIED |
| Codex Desktop UI | NOT VERIFIED | NOT VERIFIED |

Mac CI verified the adapter and synthetic media path on the stated hosted
arm64 runner. Codex Desktop on a real user Mac, Intel macOS, a full Quick or
Film workflow on macOS, and Linux remain unverified.

The job sets up Python 3.12 and Node 22, provisions FFmpeg only in the disposable
runner when missing, and uses the image's browser. It checks the tracked Git
export from a path with spaces, an unrelated cwd and a separate writable
workspace. Link tests use Windows junctions or real directory symlinks on
macOS. The no-media initialization checks the real copied brief helper.

The CI synthetic route reuses the local Canvas/tone fixture without a model
turn. The separate WebGL diagnostic is outside the CI Canvas scope. The opt-in
local smoke command still requires its discovery/invocation receipt. CI
separately attempts app-server metadata discovery in a fresh credential-free home. A model invocation and Codex Desktop are separate
checks. The synthetic result does not qualify a full Quick or Film run.

Runner labels and mutable images are documented in
[GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [runner images](https://github.com/actions/runner-images).
The [Codex app-server protocol](https://learn.chatgpt.com/docs/app-server#api-overview)
defines the metadata call; hosted discovery is measured independently.

## Evidence

[Sanitized public summary](../evidence/qualification/windows-2026-11-07.json)
contains versions, exact assertions and output hashes. Raw commands/logs, native
events/answer, probe outputs, ffprobe JSON, PNG frames and MP4 are retained locally
under the ignored `evidence/local/` directory. The public summary omits personal
paths and account/session data.

Vendor verification checks exact upstream Git blob bytes.

The first local import used git archive with inherited Windows CRLF conversion.
An independent Git-blob comparison caught this before commit/publication.
The snapshot was rebuilt from raw git cat-file blobs; the manifest was
regenerated and native/media checks repeated on those exact bytes. Earlier
attempt logs remain local and are not the final passing evidence.

## Local Windows Quick experiment

One local experiment exercised a complete bounded Quick workflow on Windows. The
12-second film used code-generated visuals and locally synthesized sound, went
through two owner revision rounds and finished at 1920×1080 and 24 fps with
288 decoded frames. Full audio and video decode passed. The experiment used
no external AI image or video generation.

CineCode automatic delivery remained **HELD**. Its hook, low-action, repeat
and brightness checks flagged this sparse, dark composition. The owner
approved picture and sound. CineCode regenerated different audio bytes at
the final stage, so the final review file paired the native final picture with
the approved AAC stream by lossless stream copy. The approved packets and
decoded audio matched. Audio rendering determinism remains unverified.

The experiment qualifies this Windows Quick path only. The film, workspace
and raw evidence remain local. Film mode, Intel macOS, Linux, full Quick on
macOS, Mac Desktop, and Mac model invocation remain outside
verified scope. The adapter has no lifecycle hook bridge (`REDUCED_NO_HOOKS`).
External TTS, models, assets and broader render paths such as WebGL are outside
the hosted qualification.

Other gaps include automatic presentation enforcement, upstream usage and
handoff equivalents, font fetching with a global cache, typography and story
QA, clean-machine setup, interruption recovery and restricted-sandbox capture.
