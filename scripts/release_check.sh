#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install --user --quiet build twine
python3 -m build
python3 -m twine check dist/*

echo "Release artifacts look valid."
