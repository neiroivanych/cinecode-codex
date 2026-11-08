#!/bin/bash
set -eu
bundle=$(cd -- "$(dirname "$0")" && pwd -P)
for required in manifest.json install.py payload/cinecode-codex/VERSION; do
    if [ ! -f "$bundle/$required" ]; then
        printf '%s\n' 'Extract the whole CineCode ZIP into one folder and run the launcher again.' >&2
        exit 2
    fi
done

find_brew() {
    case "$(uname -m)" in
        arm64) candidates=(/opt/homebrew/bin/brew /usr/local/bin/brew) ;;
        x86_64) candidates=(/usr/local/bin/brew /opt/homebrew/bin/brew) ;;
        *) return 1 ;;
    esac
    for candidate in "${candidates[@]}"; do
        if [ -x "$candidate" ]; then printf '%s\n' "$candidate"; return 0; fi
    done
    local detected
    detected=$(command -v brew) || return 1
    case "$detected" in /*) printf '%s\n' "$detected" ;; *) return 1 ;; esac
}

prepare_brew() {
    if find_brew >/dev/null; then return 0; fi
    printf '%s\n' 'CineCode needs Homebrew to install a missing component.' \
        'The official Homebrew installer may ask for your password or install Apple command line tools.'
    printf '%s' 'Run the official Homebrew installer from brew.sh? [y/N] '
    if ! IFS= read -r answer; then answer=''; fi
    case "$answer" in
        y|Y|yes|YES) ;;
        *) printf '%s\n' 'Setup paused. Install Homebrew from https://brew.sh/ and try again.' >&2; return 2 ;;
    esac
    (
        temporary=$(/usr/bin/mktemp -t cinecode-brew)
        trap '/bin/rm -f -- "$temporary"' EXIT
        /usr/bin/curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$temporary" &&
        /bin/bash "$temporary"
    ) || return 2
    find_brew >/dev/null
}

find_python() {
    local -a bins
    local bin path
    IFS=: read -r -a bins <<< "$PATH"
    bins+=(/opt/homebrew/bin /usr/local/bin)
    for bin in "${bins[@]}"; do
        case "$bin" in /usr/bin|/usr/bin/) continue ;; /*) ;; *) continue ;; esac
        for path in "$bin"/python3 "$bin"/python "$bin"/python3.[0-9]*; do
            if [[ "${path##*/}" =~ ^python(3(\.[0-9]+)?)?$ ]] && [ -f "$path" ] && [ -x "$path" ] &&
                "$path" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
                printf '%s\n' "$path"
                return 0
            fi
        done
    done
    # The system stub can prompt for command line tools. Probe it only if they exist.
    if /usr/bin/xcode-select -p >/dev/null 2>&1 &&
        /usr/bin/python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
        printf '%s\n' /usr/bin/python3
        return 0
    fi
    return 1
}

if [ "${1:-}" = --prepare-brew ]; then
    prepare_brew || { printf '%s\n' 'Homebrew setup could not finish.' >&2; exit 2; }
    exit 0
fi

case "$(uname -s):$(uname -m)" in
    Darwin:arm64|Darwin:x86_64) ;;
    *) printf '%s\n' 'This CineCode setup is for macOS on Apple Silicon or Intel.' >&2; exit 2 ;;
esac

if ! python_path=$(find_python); then
    for arg in "$@"; do
        if [ "$arg" = --existing-only ]; then
            printf '%s\n' 'Existing-components check could not verify Python 3.9 or later.' >&2; exit 2
        fi
    done
    prepare_brew || { printf '%s\n' 'Homebrew setup could not finish.' >&2; exit 2; }
    brew=$(find_brew)
    prefix=$("$brew" --prefix)
    export PATH="$prefix/bin:$PATH"
    log=$(/usr/bin/mktemp -t cinecode-python)
    printf '%s\n' 'Preparing Python via Homebrew...'
    if ! HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 "$brew" install python >"$log" 2>&1; then
        printf 'Python could not be installed. Setup log: %s\n' "$log" >&2; exit 2
    fi
    if ! python_path=$(find_python); then
        printf 'Python could not be verified after setup. Setup log: %s\n' "$log" >&2; exit 2
    fi
fi

exec "$python_path" -B "$bundle/install.py" "$@"
