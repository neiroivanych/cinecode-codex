# cinecode-codex

**Independent community Codex adapter for CineCode.**
**Experimental alpha** · Free and open source · `0.1.2-alpha`.

Codex adapter created and maintained by [@neiroivanych](https://github.com/neiroivanych).

Original [CineCode](https://github.com/sarpstar/cinecode) created by
**Sarp Yıldız (@sarpstar)** and used under its MIT License. This adapter is a separate
community project, not an official CineCode project or a GitHub fork. It is not
affiliated with or endorsed by OpenAI. The adapter layer is MIT licensed;
upstream's license and attribution remain in [cinecode/](cinecode/).
See [third-party notices](THIRD_PARTY_NOTICES.md).

## What it does

Provides a small native Codex project skill for CineCode's Quick/Film workflow,
an exact pinned vendor snapshot, drift verification, prerequisite doctor and
a local tool launcher. Film projects stay in ignored workspace/.
The adapter runs with reduced protection, pinned upstream tools and
repository-local Codex instructions.

This experimental adapter provides a Codex workflow for CineCode. See [actual qualification](docs/QUALIFICATION.md) and
[host differences/reduced protection](docs/HOST_ADAPTATION.md).

| Environment | Qualification |
| --- | --- |
| Windows x64 | Clean local qualification PASS for the implementation. Earlier hosted adapter and synthetic media qualification PASS. |
| macOS 15 arm64 | Earlier hosted adapter and synthetic media qualification PASS. Full Quick, Codex Desktop and model invocation remain unverified. |
| Intel macOS, Linux and Film production | NOT VERIFIED. |

Hosted Windows and macOS qualification for this candidate is pending. See the
[qualification report](docs/QUALIFICATION.md) for test scope and evidence.

## Prerequisites

- Git for cloning the release.
- Codex with repo-local skills and an existing user sign-in for native testing.
- Python 3.9+, Node.js 22+, FFmpeg and ffprobe.
- Chrome, Chromium or Edge for capture. `CHROME_PATH` can select an existing browser executable.

Nothing installs automatically. Doctor checks existing tools without rendering
or contacting model/media services. This release's launcher exposes local tools;
external media, fonts/models/TTS, keys and paid services need separate explicit
approval and a reviewed invocation. No API key is required by the adapter.

## Open and check

Once the `v0.1.2-alpha` tag is published, run these commands one at a time, in
order. The clone selects the release tag before either check. Continue after
each command succeeds.
Use `python3` in both lines if that is your Python command.

~~~sh
git clone --branch v0.1.2-alpha --single-branch https://github.com/neiroivanych/cinecode-codex.git
cd cinecode-codex
python -B scripts/cc.py verify
python -B scripts/cc.py doctor
~~~

Doctor returns nonzero for missing prerequisites and reports browser launch as
`NOT_RUN`.

Open the cloned `cinecode-codex` folder as a project in Codex and invoke
**$cinecode** explicitly, for example:

> $cinecode Inspect adapter compatibility only; do not start a film.

The repository skill lives in [.agents/skills/cinecode/SKILL.md](.agents/skills/cinecode/SKILL.md).
Native discovery is tested separately from `doctor` and Desktop behavior.

## User projects

After the user requests a film, the skill chooses Quick/Film from the brief
and uses STATE.md and notes for checkpoints. The launcher can initialize:

~~~sh
python -B scripts/cc.py init my-film --mode quick
python -B scripts/cc.py tool my-film make stills
~~~

Those commands are examples for an authorized future film, not startup commands.
The default is repository-owned workspace/my-film/. An explicit --workspace
directory supports a read-only installation. Git ignores the default project
workspace. Back up your projects and state separately.

## Known limitations

- Protection is **`REDUCED_NO_HOOKS`**. The adapter has no Codex lifecycle hook
  bridge. Approval gates rely on actual owner decisions.
- CineCode QC can hold intentional sparse, dark or low-action compositions.
- Audio byte determinism is unverified. The local Quick final retained the
  owner-approved audio through lossless stream copy after CineCode regenerated
  different audio bytes.
- External TTS, models and assets are outside this qualification. Hosted
  synthetic media checks cover Canvas and local tone.

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

A future distributor can package the same adapter using the
[distribution boundary](docs/DISTRIBUTION_BOUNDARY.md).
