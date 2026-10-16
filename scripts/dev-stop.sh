#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"
source "$project_root/scripts/process-helpers.sh"
task_data_dir="${DATA_DIR:-$("$project_root/.venv/bin/python" -c 'from app.config import DATA; print(DATA)')}"
for component in web worker; do
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
        rm -f "$file"
    else
        echo "Skipped $component: PID does not match this checkout; no unrelated process stopped."
    fi
done
echo 'Development stop check complete.'
