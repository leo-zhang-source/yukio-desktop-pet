#!/bin/zsh
# Local diagnostics only: no collection, model requests, configuration edits,
# security changes or termination of an existing Yukio process.
emulate -LR zsh
setopt NULL_GLOB

diagnostic_dir=$(/usr/bin/mktemp -d "${TMPDIR:-/tmp/}yukio-connection.XXXXXX") || exit 1
report="$diagnostic_dir/Yukio-connection.txt"
probe_pid=""
cleanup() {
    if [[ -n "$probe_pid" ]]; then
        kill -TERM "$probe_pid" 2>/dev/null
        wait "$probe_pid" 2>/dev/null
        probe_pid=""
    fi
}
trap cleanup EXIT INT TERM

probe() {
    local label="$1" port=$((20000 + RANDOM)) ready=0 result=0
    shift
    # Pick a free test address; the production port and its owner are untouched.
    while /usr/sbin/lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; do
        port=$((20000 + RANDOM))
    done
    "$runtime" --no-browser --port "$port" "$@" >"$diagnostic_dir/$label.log" 2>&1 &
    probe_pid=$!
    for attempt in {1..40}; do
        if ! kill -0 "$probe_pid" 2>/dev/null; then break; fi
        if /usr/bin/curl --noproxy '*' --silent --fail --max-time 1 \
            -H 'X-Yukio-Workbench: 1' "http://127.0.0.1:$port/api/health" >/dev/null 2>&1; then
            ready=1
            break
        fi
        /bin/sleep 0.2
    done
    if kill -0 "$probe_pid" 2>/dev/null; then kill -TERM "$probe_pid" 2>/dev/null; fi
    wait "$probe_pid" 2>/dev/null
    result=$?
    probe_pid=""
    print -r -- "$label: connected=$ready, exit=$result"
    # Startup diagnostics only; redact common local paths. Never read histories
    # or print the contents of model/configuration files.
    local line count=0
    while IFS= read -r line && (( count++ < 30 )); do
        line="${line//$HOME/\~}"
        line="${line//$diagnostic_dir/<diagnostic-temp>}"
        line="${line//$app/<Yukio.app>}"
        print -r -- "  $line"
    done <"$diagnostic_dir/$label.log"
}

{
    print 'Yukio 工作台连接诊断 / Workbench connection diagnostics'
    print -r -- "macOS: $(/usr/bin/sw_vers -productVersion)"
    print -r -- "architecture: $(/usr/bin/uname -m)"
    app="${1:-}"
    if [[ -z "$app" ]]; then
        candidates=(/Applications/Yukio.app "$HOME/Applications/Yukio.app" "$HOME/Desktop/Yukio.app"
                    "$HOME/Downloads/Yukio.app" /Volumes/*/Yukio.app)
        for candidate in "${candidates[@]}"; do
            if [[ -d "$candidate/Contents" ]]; then app="$candidate"; break; fi
        done
    fi
    if [[ ! -d "$app/Contents" ]]; then
        print '未找到 Yukio.app。请将 App 放进“应用程序”文件夹，再运行此检查。'
        print 'App not found. Put Yukio.app in Applications and rerun this check.'
    else
        print -r -- "app: ${app//$HOME/\~}"
        /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist"
        /usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$app/Contents/Info.plist"
        /usr/bin/codesign --verify --deep --strict "$app" >"$diagnostic_dir/signature.log" 2>&1
        print -r -- "signature_check_exit: $?"
        runtime="$app/Contents/Resources/activity-workbench/runtime/YukioRuntime/YukioRuntime"
        if [[ ! -x "$runtime" ]]; then
            print 'runtime_missing: 安装包缺少可运行的工作台组件。'
        else
            print 'default_port_8767_listener:'
            /usr/sbin/lsof -nP -iTCP:8767 -sTCP:LISTEN -F pc 2>/dev/null
            probe fresh_profile --data-dir "$diagnostic_dir/empty-data"
            probe existing_profile
        fi
    fi
    print ''
    print '请将上面的结果发给开发者。此检查没有采集聊天、修改设置或关闭现有程序。'
    print 'Send the results above to the developer. No chat collection, settings changes or existing processes stopped.'
} 2>&1 | /usr/bin/tee "$report"
print -r -- "报告 / Report: $report"
