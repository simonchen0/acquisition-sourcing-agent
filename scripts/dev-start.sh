#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"
export DATA_DIR="${DATA_DIR:-$project_root/.data}"
export COOKIE_SECURE="${COOKIE_SECURE:-false}"
export DEV_PORT="${DEV_PORT:-8000}"
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"
.venv/bin/python -m app.cli init-db
running() {
    local component="$1" expected="$2" task_pid
    [ -f "$DATA_DIR/$component.pid" ] || return 1
    task_pid="$(cat "$DATA_DIR/$component.pid")"
    [[ "$task_pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$task_pid" 2>/dev/null || return 1
    [ "$(readlink "/proc/$task_pid/cwd")" = "$project_root" ] || return 1
    tr '\0' ' ' < "/proc/$task_pid/cmdline" | rg -q "$expected"
}
if ! running web 'app.main:app'; then
    nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$DEV_PORT" --no-access-log > "$DATA_DIR/web.log" 2>&1 &
    echo "$!" > "$DATA_DIR/web.pid"
fi
for attempt in {1..20}; do
    if curl --fail --silent "http://127.0.0.1:$DEV_PORT/health" > /dev/null; then break; fi
    sleep 0.5
done
running web 'app.main:app' || { echo 'Web startup failed. Inspect the private web log.'; exit 1; }
curl --fail --silent "http://127.0.0.1:$DEV_PORT/health" > /dev/null
if ! running worker 'app.worker'; then
    nohup .venv/bin/python -m app.worker > "$DATA_DIR/worker.log" 2>&1 &
    echo "$!" > "$DATA_DIR/worker.pid"
fi
sleep 0.5
running worker 'app.worker' || { echo 'Worker startup failed. Inspect the private worker log.'; exit 1; }
echo 'Development web service and worker started. Database health check passed.'
