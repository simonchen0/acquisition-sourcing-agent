#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"
source "$project_root/scripts/process-helpers.sh"
# Python loads the repository .env safely, without executing shell code.
# Do not override settings from .env with development defaults in this script.
export DEV_PORT="${DEV_PORT:-8000}"
if [ -z "${DATA_DIR:-}" ]; then
    DATA_DIR="$("$project_root/.venv/bin/python" -c 'from app.config import DATA; print(DATA)')"
fi
export DATA_DIR
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"
"$project_root/.venv/bin/python" -m app.cli init-db
if [ -f "$DATA_DIR/web.pid" ] && process_matches "$(cat "$DATA_DIR/web.pid")" 'app.main:app' "$project_root"; then
    echo 'Development service is already running.'
else
    # Embedded worker is the development default; production Compose disables it.
    nohup "$project_root/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$DEV_PORT" --no-access-log > "$DATA_DIR/web.log" 2>&1 &
    echo "$!" > "$DATA_DIR/web.pid"
fi
for attempt in {1..20}; do
    if curl --fail --silent "http://127.0.0.1:$DEV_PORT/health" > /dev/null; then break; fi
    sleep 0.5
done
process_matches "$(cat "$DATA_DIR/web.pid")" 'app.main:app' "$project_root" || { echo 'Web startup failed. Inspect the private web log.'; exit 1; }
curl --fail --silent "http://127.0.0.1:$DEV_PORT/health" > /dev/null
echo 'Development service started. Worker mode is shown by /health.'
