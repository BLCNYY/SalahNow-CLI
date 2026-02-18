#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v pipx >/dev/null 2>&1; then
  pipx install --force "$ROOT_DIR"
  echo "Installed with pipx. Run: salahnow"
  exit 0
fi

python3 -m pip install --user "$ROOT_DIR"

cat <<'EOF'
Installed with pip --user.
If 'salahnow' is not found, add this to your shell profile:
  export PATH="$HOME/.local/bin:$PATH"
EOF
