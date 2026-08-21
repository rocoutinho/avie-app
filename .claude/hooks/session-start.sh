#!/bin/bash
set -euo pipefail

# Só roda em sessões remotas (Claude Code na web) — localmente cada
# desenvolvedor já gerencia seu próprio venv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

if [ ! -d venv ]; then
  python3 -m venv venv
fi

./venv/bin/pip install -q -r requirements.txt

# Deixa python/pip/flask/pytest do venv disponíveis sem precisar de
# "source venv/bin/activate" em cada comando da sessão.
echo "export VIRTUAL_ENV=\"$CLAUDE_PROJECT_DIR/venv\"" >> "$CLAUDE_ENV_FILE"
echo "export PATH=\"$CLAUDE_PROJECT_DIR/venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"

if [ ! -f .env ]; then
  cp .env.example .env
fi
