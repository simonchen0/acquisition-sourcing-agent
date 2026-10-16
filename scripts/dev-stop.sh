#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"
task_data_dir="${DATA_DIR:-$project_root/.data}"
for component in web worker; do
    file="$task_data_dir/$component.pid"
    [ -f "$file" ] || continue
    task_pid="$(cat "$file")"
    [[ "$task_pid" =~ ^[0-9]+$ ]] || continue
    [ "$(readlink "/proc/$task_pid/cwd" 2>/dev/null || true)" = "$project_root" ] || continue
    expected='app.main:app'; [ "$component" = 'worker' ] && expected='app.worker'
    if tr '\0' ' ' < "/proc/$task_pid/cmdline" | rg -q "$expected"; then kill -TERM "$task_pid"; fi
    rm -f "$file"
done
echo 'Stopped only development processes identified by this checkout.'
