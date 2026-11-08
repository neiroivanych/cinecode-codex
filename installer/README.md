# CineCode bootstrap

The Windows and macOS ZIPs contain the same tracked adapter payload, tied to
the selected commit by `manifest.json`. Extract the whole ZIP and open
`INSTALL_CINECODE.cmd` on Windows or `INSTALL_CINECODE.command` on macOS. When
setup reports `CineCode is ready`, open the printed folder in Codex and type
`$cinecode`. The default destination is `CineCode/cinecode-codex` under the
current user's home. Git is needed to build a ZIP. Setup uses the bundled files.

The manifest records setup and adapter versions, commit, file count, SHA-256,
size and mode. This detects corruption. Use a ZIP from a trusted source for
authenticity. Setup checks the extracted payload, then verifies and diagnoses
the installed adapter. The same setup can repair recorded payload paths and
preserves workspace, state and files outside the payload. A different version
or an ambiguous collision stops setup. Use a separate destination for a
different version. If setup was interrupted and says it is locked, ensure all
setup windows have closed before removing only `.cinecode-setup.lock` in the
printed installation folder. The next run can repair a partial copy.

The launchers locate Python 3.9+ first. With Python available, shared setup
verifies the payload before copying it or preparing the remaining components.
WinGet uses the exact IDs for [Python](https://github.com/microsoft/winget-pkgs/tree/master/manifests/p/Python/Python/3/13),
[Node LTS](https://github.com/microsoft/winget-pkgs/tree/master/manifests/o/OpenJS/NodeJS/LTS),
[FFmpeg](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Gyan/FFmpeg)
and [Chrome](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Google/Chrome).
macOS uses the Homebrew `python`, `node` and `ffmpeg` formulae and the
`google-chrome` cask. Homebrew setup requires an explicit answer and uses the
[official Homebrew installer](https://brew.sh/). A compatible installed browser
is reused. Setup checks both `ffmpeg` and `ffprobe`. Codex uses its normal
installation and sign-in separately.

On macOS the ZIP sets the executable mode on the entry point. The unsigned and unnotarized
bootstrap uses the file-specific Open Anyway fallback described in
`README-INSTALL.txt` for a trusted ZIP from the official GitHub Release. On Windows the CMD launcher applies
its PowerShell execution policy in the setup process only.

## Runtime launch from Codex

If `.cinecode-runtime` exists in the trusted installed folder, it contains the
verified Python executable, dependency PATH prefix and browser executable on
three UTF-8 lines. Use those settings for adapter commands so Codex launched
from the desktop can find components outside its inherited PATH. Set them in
the shell running each adapter command. Start in the adapter folder.

Windows PowerShell:

```powershell
$runtime = Get-Content -LiteralPath .cinecode-runtime -Encoding UTF8
$env:PATH = $runtime[1] + [IO.Path]::PathSeparator + $env:PATH
$env:CHROME_PATH = $runtime[2]
$env:NoDefaultCurrentDirectoryInExePath = '1'
& $runtime[0] -B scripts/cc.py doctor
```

macOS shell:

```sh
{
  IFS= read -r python_path
  IFS= read -r runtime_path
  IFS= read -r browser_path
} < .cinecode-runtime
PATH="$runtime_path:$PATH" CHROME_PATH="$browser_path" "$python_path" -B scripts/cc.py doctor
```

Use the same interpreter and environment when substituting another adapter
command for `doctor`. A normal checkout without the runtime file uses the
existing CLI instructions.

## Build and qualify

Set `output_dir` to a new directory outside the repository.

```sh
python -B installer/build/package.py --platform windows --ref HEAD --out "$output_dir"
python -B installer/build/package.py --platform macos --ref HEAD --out "$output_dir"
```

`--version` can assert the exact version in the chosen commit. Use a new output
directory for repeated builds. The builder prints each ZIP's SHA-256. Existing
files are reused during the Windows qualification by running the extracted
launcher with `-Destination` and `-ExistingOnly`. The macOS equivalents are
`--destination` and `--existing-only`. Use a disposable folder under your home
or temp directory. See [qualification scope](../docs/QUALIFICATION.md) for the real hosted
package-manager runs and the remaining deterministic-only routes.
