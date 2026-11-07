# cinecode-codex

**Independent community Codex adapter for CineCode.**
Free and open source. Version **0.1.0-alpha — Experimental**.

[CineCode](https://github.com/sarpstar/cinecode) was created by **sarpstar
(Sarp Yıldız)** and is used under its MIT License. This adapter is a separate
community project, not an official CineCode project or a GitHub fork. It is not
affiliated with or endorsed by OpenAI. The adapter layer is MIT licensed;
upstream's license and attribution remain in [cinecode/](cinecode/).
See [third-party notices](THIRD_PARTY_NOTICES.md).

## What it does

Provides a small native Codex project skill for CineCode's Quick/Film workflow,
an exact pinned vendor snapshot, drift verification, prerequisite doctor and
a local tool launcher. Film projects stay in ignored workspace/.
No hooks bridge, automatic upstream updates, NI dependency or global Codex
configuration is installed.

This is an experimental workflow adapter, not a standalone video editor or a
qualified HVPC renderer. See [actual qualification](docs/QUALIFICATION.md) and
[host differences/reduced protection](docs/HOST_ADAPTATION.md).
Hosted Windows/macOS qualification is tracked separately from Codex Desktop in the qualification report. Linux is **not verified**.

## Prerequisites

- Codex with repo-local skills and an existing user sign-in for native testing.
- Python 3.9+, Node.js 22+, FFmpeg and ffprobe.
- Chrome, Chromium or Edge for capture; CHROME_PATH can select an existing EXE.

Nothing installs automatically. Doctor checks existing tools without rendering
or contacting model/media services. This release's launcher exposes local tools;
external media, fonts/models/TTS, keys and paid services need separate explicit
approval and a reviewed invocation. No API key is required by the adapter.

## Open and check

Open this repository as a Codex project. From its root:

~~~sh
python -B scripts/cc.py verify
python -B scripts/cc.py doctor
~~~

On systems where Python is named python3, use python3. Doctor returns nonzero for
missing requirements and reports browser launch as NOT_RUN. Windows and macOS
browser discovery paths are separated; Linux uses PATH candidates.

Invoke **$cinecode** explicitly in Codex, for example:

> $cinecode Inspect adapter compatibility only; do not start a film.

The skill lives in .agents/skills/cinecode/SKILL.md. File presence and doctor
are not proof of native discovery. Existing local native test evidence is
described in QUALIFICATION.md; it does not certify every Codex Desktop build.

## User projects

After the user requests a film, the skill chooses Quick/Film from the brief
and uses STATE.md and notes for checkpoints. The launcher can initialize:

~~~sh
python -B scripts/cc.py init my-film --mode quick
python -B scripts/cc.py tool my-film make stills
~~~

Those commands are examples for an authorized future film, not startup commands.
The default is repository-owned workspace/my-film/. An explicit --workspace
directory supports a read-only installation. Nothing depends on a parent
research folder. Projects and state are ignored by Git; back them up separately.

No real Quick/Film output is claimed by the initial synthetic qualification.
Upstream's Claude hooks/session APIs are not available here; protection is
**REDUCED_NO_HOOKS**. A user's actual decision is required at approval gates.

## Reproduce checks

~~~sh
python -B -m unittest discover -s tests -v
python -B scripts/native_discovery.py --out evidence/local/native-new
# Only after the native test passes and media smoke is authorized:
python -B scripts/smoke.py --discovery evidence/local/native-new/summary.json --out evidence/local/smoke-new
~~~

Native testing uses existing Codex sign-in, a native skills/list request and an
ephemeral explicit invocation; it does not install/configure global skills.
Smoke creates only a 160x90 moving square, selected PNG frames and a 2-second
H.264/AAC MP4 with synthetic tone. It uses no network media, TTS or external
models. Output directories must be new. Logs/media remain ignored.

## Package layout

- .agents/skills/cinecode/ — small Codex wrapper.
- cinecode/ — unmodified snapshot pinned in upstream.lock.json.
- cinecode.sha256.json — exact file hashes; verification also detects extra files.
- scripts/ — standard-library adapter and opt-in qualification.
- tests/ — non-rendering regression tests.
- docs/ — host mapping, evidence scope and future packaging boundary.
- adapter.json and VERSION — machine-readable package metadata.

There is no NI AI Creator Tools integration. A future distributor can package
the same adapter using [this boundary](docs/NI_INTEGRATION_BOUNDARY.md).
The source is available ahead of the first tagged alpha release.
