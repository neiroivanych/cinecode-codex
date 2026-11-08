#!/bin/bash
set -eu
bundle=$(cd -- "$(dirname "$0")" && pwd -P)
exec /bin/bash "$bundle/setup.sh" "$@"
