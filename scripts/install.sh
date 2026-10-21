#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo '请使用 sudo sh install.sh，或以 root 运行。' >&2; exit 1; }
TASK_SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /bin/python3 -I "$TASK_SCRIPT_DIR/install.py" "$@"
