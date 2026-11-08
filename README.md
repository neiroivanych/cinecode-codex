# cinecode-codex

**Independent community Codex adapter for CineCode.**
**Experimental alpha** · Free and open source · `0.1.3-alpha`.

## Recommended installation

Use the setup ZIP for your computer from the [CineCode GitHub Release](https://github.com/neiroivanych/cinecode-codex/releases/tag/v0.1.3-alpha).

### Windows

1. Download `CineCode-Setup-Windows.zip`.
2. Extract the whole ZIP.
3. Double-click `INSTALL_CINECODE.cmd`.
4. Wait for `CineCode is ready`.
5. Open the printed `cinecode-codex` folder in Codex.
6. Start a new chat and type `$cinecode`.

### macOS

1. Download `CineCode-Setup-macOS.zip`.
2. Extract the whole ZIP.
3. Open `INSTALL_CINECODE.command`.
4. Wait for `CineCode is ready`.
5. Open the printed `cinecode-codex` folder in Codex.
6. Start a new chat and type `$cinecode`.

The macOS installer is unsigned and not notarized. If macOS blocks it, try
opening it once, then use **System Settings → Privacy & Security → Open Anyway**
only for a package from the official CineCode GitHub Release linked above.

### What setup does

Setup checks your computer, reuses compatible components and prepares supported
ones that are missing. On Windows it can use the system package manager. Follow
any permission prompts. Setup installs CineCode and reports success after
CineCode's own checks pass. Run the same setup again to repair a same-version
installation while keeping your projects, state and other files.

The bootstrap was qualified on hosted Windows Server 2025 x64 and macOS 15.8.2
arm64. Those checks covered Install, Repair, dependency preparation for a tested
component, the installed runtime and repo-local skill discovery. The macOS path
that first needs to install Homebrew asks for explicit consent and has not been
qualified natively. Finder/browser-download behavior and the Codex Desktop UI
remain outside hosted qualification. See the [qualification details](docs/QUALIFICATION.md)
and the [technical setup guide](installer/README.md).

## What it does

CineCode for Codex provides a repo-local skill for CineCode's Quick and Film
workflows, a pinned upstream snapshot, integrity and prerequisite checks, and a
local tool launcher. The adapter has [reduced protection](docs/HOST_ADAPTATION.md)
without a lifecycle hook bridge (`REDUCED_NO_HOOKS`). Approval gates rely on the
owner's actual decisions. No API key is required by the adapter.

## Advanced / manual installation

For the manual route, use Git and a Codex installation that supports repo-local
skills. Install Python 3.9+, Node.js 22+, FFmpeg and ffprobe, and Chrome, Chromium
or Edge. `CHROME_PATH` can select an existing browser executable. Use `python3`
if that is your Python command. Run each check before continuing.

~~~sh
git clone --branch v0.1.3-alpha --single-branch https://github.com/neiroivanych/cinecode-codex.git
cd cinecode-codex
python -B scripts/cc.py verify
python -B scripts/cc.py doctor
~~~

Open the cloned folder in Codex, start a new chat and invoke `$cinecode`.
The [repo-local skill](.agents/skills/cinecode/SKILL.md) includes a compatibility-only
route. `doctor` checks prerequisites and reports browser launch as `NOT_RUN`.
The [technical setup guide](installer/README.md#runtime-launch-from-codex) explains
how to use an installer's runtime file for later adapter commands.

## User projects

Once you request a film, the skill chooses Quick or Film from the brief and
records checkpoints in `STATE.md` and notes. The default `workspace/` is ignored
by Git. Use `--workspace` with an explicit writable directory for a read-only
installation. Back up your projects and state separately.

~~~sh
python -B scripts/cc.py init my-film --mode quick
python -B scripts/cc.py tool my-film make stills
~~~

## Qualification scope

- CineCode QC can hold intentional sparse, dark or low-action compositions.
- Audio byte determinism is unverified. The local Quick final retained the
  owner-approved audio through lossless stream copy after CineCode regenerated
  different audio bytes.
- Hosted synthetic media checks cover Canvas and local tone. External TTS,
  models and assets require separate explicit approval and a reviewed invocation.

For maintainer checks, run `python -B -m unittest discover -s tests -v`.
Native discovery and the bounded media smoke are opt-in. See the
[qualification details](docs/QUALIFICATION.md) for their scope.

## Attribution

Codex adapter created and maintained by [@neiroivanych](https://github.com/neiroivanych).
Original [CineCode](https://github.com/sarpstar/cinecode) created by
**Sarp Yıldız (@sarpstar)** and used under its MIT License. This is an independent
community project. It is not affiliated with or endorsed by OpenAI. The adapter
is MIT licensed. The pinned [upstream snapshot](cinecode/) retains its license
and attribution. See [third-party notices](THIRD_PARTY_NOTICES.md) and the
[distribution boundary](docs/DISTRIBUTION_BOUNDARY.md).
