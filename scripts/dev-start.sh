#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$project_root"
source "$project_root/scripts/process-helpers.sh"
export DEV_PORT="${DEV_PORT:-8000}"
web_component=web
[ "$DEV_PORT" = 8000 ] || web_component="web-$DEV_PORT"
if [ -z "${DATA_DIR:-}" ]; then
    DATA_DIR="$("$project_root/.venv/bin/python" -c 'from app.config import DATA; print(DATA)')"
fi
export DATA_DIR
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"
"$project_root/.venv/bin/python" -m app.cli init-db
if [ -f "$DATA_DIR/$web_component.pid" ] && process_matches "$(cat "$DATA_DIR/$web_component.pid")" 'app.main:app' "$project_root"; then
    if [ -f "$DATA_DIR/$web_component.instance" ] && server_matches "$DEV_PORT" "$(cat "$DATA_DIR/$web_component.instance")"; then
        echo 'Development service is already running; this instance and API version were verified.'
        exit 0
    fi
    echo 'An existing process has not been verified as the current app. Run scripts/dev-stop.sh first, or use a different DEV_PORT.'
    exit 1
fi
# A health response alone can belong to an old process. Never mistake it for a new startup.
if ! "$project_root/.venv/bin/python" - "$DEV_PORT" <<'PY_BIND'
import socket,sys
try:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind(('127.0.0.1',int(sys.argv[1])))
except (OSError,ValueError): raise SystemExit(1)
PY_BIND
then
    echo "Port $DEV_PORT is already in use; no new server was started and no unrelated process was stopped."
    echo 'Try DEV_PORT=8001 scripts/dev-start.sh and open port 8001, or stop the previous app through its original terminal.'
    exit 1
fi
instance_id="$("$project_root/.venv/bin/python" -c 'import secrets; print(secrets.token_hex(16))')"
APP_INSTANCE_ID="$instance_id" nohup "$project_root/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$DEV_PORT" --no-access-log > "$DATA_DIR/web.log" 2>&1 &
task_pid="$!"
for attempt in {1..20}; do
    if server_matches "$DEV_PORT" "$instance_id"; then
        echo "$task_pid" > "$DATA_DIR/$web_component.pid"
        echo "$instance_id" > "$DATA_DIR/$web_component.instance"
        echo 'Development service started. This server instance and API version were verified.'
        exit 0
    fi
    kill -0 "$task_pid" 2>/dev/null || break
    sleep 0.5
done
if process_matches "$task_pid" 'app.main:app' "$project_root"; then kill -TERM "$task_pid"; fi
echo 'Web startup failed: this server instance could not be verified. Inspect the private web log.'
exit 1
