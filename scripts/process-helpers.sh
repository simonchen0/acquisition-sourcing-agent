# Shared POSIX process checks for Linux and macOS; no /proc or ripgrep dependency.
process_matches() {
    local task_pid="$1" expected="$2" project_root="$3" command_line process_dir
    [[ "$task_pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$task_pid" 2>/dev/null || return 1
    command_line="$(ps -p "$task_pid" -o command= 2>/dev/null)" || return 1
    printf '%s\n' "$command_line" | grep -F -- "$expected" > /dev/null || return 1
    # Absolute interpreter/uvicorn path establishes checkout ownership on both platforms.
    printf '%s\n' "$command_line" | grep -F -- "$project_root/.venv/bin/" > /dev/null
}
