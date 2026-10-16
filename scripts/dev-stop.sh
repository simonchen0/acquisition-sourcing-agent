#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$project_root"
source "$project_root/scripts/process-helpers.sh"
task_data_dir="${DATA_DIR:-$("$project_root/.venv/bin/python" -c 'from app.config import DATA; print(DATA)')}"
web_component=web
[ "${DEV_PORT:-8000}" = 8000 ] || web_component="web-${DEV_PORT}"
components=("$web_component")
[ "${DEV_PORT:-8000}" != 8000 ] || components+=(worker)
for component in "${components[@]}"; do
    file="$task_data_dir/$component.pid"
    [ -f "$file" ] || continue
    task_pid="$(cat "$file")"
    expected='app.main:app'; [ "$component" = 'worker' ] && expected='app.worker'
    if process_matches "$task_pid" "$expected" "$project_root"; then
        kill -TERM "$task_pid"
        for attempt in {1..20}; do
            kill -0 "$task_pid" 2>/dev/null || break
            sleep 0.25
        done
        if process_matches "$task_pid" "$expected" "$project_root"; then
            echo "$component is still shutting down. Its PID file was kept; wait and rerun this command."
            exit 1
        fi
        rm -f "$file"
        [ "$component" = 'worker' ] || rm -f "$task_data_dir/$component.instance"
    else
        echo "Skipped $component: PID does not match this checkout; no unrelated process stopped."
    fi
done
echo 'Development stop check complete.'
