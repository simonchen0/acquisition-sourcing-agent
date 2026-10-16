#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"
task_data_dir="${DATA_DIR:-$project_root/.data}"
proc_cwd() {
    if [ -e "/proc/$1/cwd" ]; then readlink "/proc/$1/cwd"
    else lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'; fi
}
proc_cmdline() {
    if [ -r "/proc/$1/cmdline" ]; then tr '\0' ' ' < "/proc/$1/cmdline"
    else ps -p "$1" -o command= 2>/dev/null; fi
}
for component in web worker; do
    file="$task_data_dir/$component.pid"
    [ -f "$file" ] || continue
    task_pid="$(cat "$file")"
    [[ "$task_pid" =~ ^[0-9]+$ ]] || continue
    [ "$(proc_cwd "$task_pid" || true)" = "$project_root" ] || continue
    expected='app.main:app'; [ "$component" = 'worker' ] && expected='app.worker'
    if proc_cmdline "$task_pid" | grep -q "$expected"; then kill -TERM "$task_pid"; fi
    rm -f "$file"
done
echo 'Stopped only development processes identified by this checkout.'
