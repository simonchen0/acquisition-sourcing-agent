# Shared POSIX process checks for Linux and macOS; no /proc or ripgrep dependency.
process_matches() {
    local task_pid="$1" expected="$2" project_root="$3" command_line process_dir executable
    [[ "$task_pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$task_pid" 2>/dev/null || return 1
    executable="$(ps -ww -p "$task_pid" -o comm= 2>/dev/null)" || return 1
    case "${executable##*/}" in python|python[0-9]*|Python|Python[0-9]*|uvicorn) ;; *) return 1 ;; esac
    command_line="$(ps -ww -p "$task_pid" -o command= 2>/dev/null)" || return 1
    printf '%s\n' "$command_line" | grep -F -- "$expected" > /dev/null || return 1
    # Absolute interpreter/uvicorn path establishes checkout ownership on both platforms.
    if printf '%s\n' "$command_line" | grep -F -- "$project_root/.venv/bin/" > /dev/null; then return 0; fi
    # Older launchers used relative commands. macOS ships lsof; verify cwd before matching them.
    if command -v lsof > /dev/null 2>&1; then
        process_dir="$(lsof -a -p "$task_pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
        [ "$process_dir" = "$project_root" ] && return 0
    fi
    return 1
}

server_matches() {
    local task_port="$1" expected_instance="$2"
    "$project_root/.venv/bin/python" - "$task_port" "$expected_instance" <<'PY_HEALTH'
import json, sys, urllib.request
try:
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:'+sys.argv[1]+'/health',timeout=1) as response:
        data=json.load(response)
    raise SystemExit(0 if isinstance(data,dict) and data.get('status')=='ok' and data.get('api_version')==2 and data.get('instance_id')==sys.argv[2] else 1)
except (OSError,ValueError): raise SystemExit(1)
PY_HEALTH
}
