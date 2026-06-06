#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Install Merch Scout as a local Codex skill.

Usage:
  ./install.sh [options]

Options:
  --codex-home PATH   Codex home directory. Default: $CODEX_HOME or ~/.codex
  --venv PATH         Python virtualenv path. Default: <codex-home>/skills/.venvs/merch-scout
  --copy              Copy the skill instead of symlinking it.
  --force             Replace an existing non-symlink target.
  --no-deps           Do not install Python dependencies.
  --demo              Run a small demo generation after install.
  --skip-doctor       Do not run the local capability report after install.
  -h, --help          Show this help.

Examples:
  ./install.sh
  ./install.sh --copy --demo
  CODEX_HOME=/custom/codex ./install.sh
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/merch-scout"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
VENV_DIR=""
COPY_MODE=0
FORCE=0
INSTALL_DEPS=1
RUN_DEMO=0
RUN_DOCTOR=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --codex-home)
      CODEX_HOME_DIR="$2"
      shift 2
      ;;
    --venv)
      VENV_DIR="$2"
      shift 2
      ;;
    --copy)
      COPY_MODE=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --no-deps)
      INSTALL_DEPS=0
      shift
      ;;
    --demo)
      RUN_DEMO=1
      shift
      ;;
    --skip-doctor)
      RUN_DOCTOR=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$SKILL_SRC/SKILL.md" ]]; then
  echo "Could not find merch-scout/SKILL.md next to install.sh" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON:-python3}"
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required.")
PY

mkdir -p "$CODEX_HOME_DIR/skills"
if [[ -z "$VENV_DIR" ]]; then
  VENV_DIR="$CODEX_HOME_DIR/skills/.venvs/merch-scout"
fi

RUNTIME_PY="$PYTHON_BIN"
if [[ "$INSTALL_DEPS" -eq 1 ]]; then
  echo "Preparing private Python environment:"
  echo "  $VENV_DIR"
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  RUNTIME_PY="$VENV_DIR/bin/python"
  "$RUNTIME_PY" -m pip install --upgrade pip
  "$RUNTIME_PY" -m pip install -r "$SKILL_SRC/requirements.txt"
else
  echo "Skipping dependency installation (--no-deps)."
fi

TARGET="$CODEX_HOME_DIR/skills/merch-scout"

if [[ -e "$TARGET" || -L "$TARGET" ]]; then
  if [[ -L "$TARGET" || ! -d "$TARGET" ]]; then
    rm -f "$TARGET"
  elif [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$TARGET"
  else
    echo "Target already exists and is a directory: $TARGET" >&2
    echo "Use --force to replace it, or --codex-home to choose another Codex home." >&2
    exit 1
  fi
fi

if [[ "$COPY_MODE" -eq 1 ]]; then
  mkdir -p "$TARGET"
  (cd "$SKILL_SRC" && tar -cf - .) | (cd "$TARGET" && tar -xf -)
else
  ln -s "$SKILL_SRC" "$TARGET"
fi

chmod +x "$SKILL_SRC"/scripts/*.py "$SKILL_SRC"/bin/merch-scout
if [[ "$COPY_MODE" -eq 1 ]]; then
  chmod +x "$TARGET"/scripts/*.py "$TARGET"/bin/merch-scout
fi

mkdir -p "$CODEX_HOME_DIR/bin"
ln -sfn "$TARGET/bin/merch-scout" "$CODEX_HOME_DIR/bin/merch-scout"

echo "Installed Merch Scout skill:"
echo "  $TARGET"
echo "Command wrapper:"
echo "  $CODEX_HOME_DIR/bin/merch-scout"
echo "Python runtime:"
echo "  $RUNTIME_PY"
echo
echo "Invoke from Codex:"
echo '  Use $merch-scout to generate 10 ready-to-upload Amazon Merch on Demand designs.'
echo
echo "Run production preparation manually, then let Codex research, call image_gen, and finalize:"
echo "  \"$CODEX_HOME_DIR/bin/merch-scout\" autopilot --depth standard --count 1 --products standard_apparel --marketplaces US --output-root \"$SCRIPT_DIR/runs\""
echo "  \"$CODEX_HOME_DIR/bin/merch-scout\" research-free \"$SCRIPT_DIR/runs/<timestamp>_research\""
echo "  \"$CODEX_HOME_DIR/bin/merch-scout\" research-browser \"$SCRIPT_DIR/runs/<timestamp>_research\""
echo
echo "Run local demo/test mode without image_gen:"
echo "  \"$CODEX_HOME_DIR/bin/merch-scout\" autopilot --generator demo --depth quick --count 1 --products popsockets --marketplaces US --output-root \"$SCRIPT_DIR/runs\""

if [[ "$RUN_DOCTOR" -eq 1 ]]; then
  echo
  "$CODEX_HOME_DIR/bin/merch-scout" doctor
fi

if [[ "$RUN_DEMO" -eq 1 ]]; then
  "$CODEX_HOME_DIR/bin/merch-scout" autopilot --generator demo --depth quick --count 1 --products popsockets --marketplaces US --output-root "$SCRIPT_DIR/runs"
fi
