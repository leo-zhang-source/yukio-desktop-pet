"""User-owned CLI explanation transports. No shell, chat resume or shared API."""
import json
import os
from pathlib import Path
import shutil
import re
import signal
import subprocess
import tempfile
import threading
import time

from explanation import (ExplanationError, MAX_RESPONSE_BYTES, encode,
                         schema_for, complete_response, GLANCE_SYSTEM,
                         READING_SYSTEM, SYSTEM, load_config)

PROVIDERS = ('auto', 'codex', 'claude', 'lan')
LABELS = {'auto': '本机 Agent（跟随聊天）', 'codex': 'Codex（终端入口）',
          'claude': 'Claude Code（终端入口）', 'lan': '自选内网模型'}
SETTINGS = 'explanation-provider.json'
LOCAL_OPTIONS = 'local-explanation-options.json'


def local_lan_enabled(directory):
    """Private opt-in on the owner's installation; never shipped with the App."""
    if not directory:
        return False
    try:
        path = Path(directory) / LOCAL_OPTIONS
        with path.open('rb') as stream:
            raw = stream.read(513)
        if len(raw) > 512:
            return False
        value = json.loads(raw)
        return (isinstance(value, dict) and set(value) == {'lan'}
                and type(value['lan']) is bool and value['lan'])
    except (OSError, ValueError, TypeError):
        return False


def preferences(directory):
    path = Path(directory) / SETTINGS if directory else None
    if not path or not path.exists():
        return dict(provider='auto', automatic_on_open=False)
    raw = path.read_bytes()
    if len(raw) > 2048:
        raise ValueError('Explanation settings too large')
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {'provider', 'automatic_on_open'}
            or value['provider'] not in PROVIDERS or type(value['automatic_on_open']) is not bool):
        raise ValueError('Invalid explanation settings')
    if value['provider'] == 'lan' and not local_lan_enabled(directory):
        # A copied/old LAN preference must not enable or reveal a private model.
        return dict(provider='auto', automatic_on_open=False)
    return value


def configuration(directory, choice=None):
    choice = choice or preferences(directory)['provider']
    if choice == 'lan':
        if not local_lan_enabled(directory):
            raise ValueError('Local explanation option is disabled')
        return load_config(Path(directory) / 'lan-model.json')
    if choice not in PROVIDERS:
        raise ValueError('Invalid explanation provider')
    return dict(provider='agent', agent=choice, model=LABELS[choice], base_url='agent://' + choice,
                timeout_seconds=90, max_tokens=1000, max_calls_per_hour=20, cooldown_seconds=10)


def save_preferences(directory, provider, automatic_on_open):
    if not directory or provider not in PROVIDERS or type(automatic_on_open) is not bool:
        raise ValueError('Invalid explanation settings')
    if provider == 'lan' and not local_lan_enabled(directory):
        raise ValueError('Local explanation option is disabled')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Atomic, private, and contains no credentials, executable paths or excerpts.
    fd, name = tempfile.mkstemp(prefix='.explanation-', dir=str(directory))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(encode(dict(provider=provider, automatic_on_open=automatic_on_open)))
        os.replace(name, directory / SETTINGS)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def codex_desktop_candidates(home, application_roots=None):
    """Discover the versioned desktop layout without launching a client.

    Prefer the user's own Applications folder, then the system installation.
    Accept only the known package entrypoint; metadata cannot supply commands.
    Legacy single-binary bundles retain their existing fallback priority.
    """
    roots = application_roots if application_roots is not None else (home / 'Applications', Path('/Applications'))
    candidates = []
    for root in roots:
        for name in ('ChatGPT.app', 'Codex.app'):
            package = Path(root) / name / 'Contents/Resources/codex-cli'
            manifest = package / 'codex-package.json'
            executable = package / 'bin/codex'
            try:
                if not manifest.resolve().is_relative_to(package.resolve()):
                    continue
                with manifest.open('rb') as stream:
                    raw = stream.read(8193)
                if len(raw) > 8192:
                    continue
                value = json.loads(raw)
                if (not isinstance(value, dict) or type(value.get('layoutVersion')) is not int
                        or value['layoutVersion'] != 1 or value.get('entrypoint') != 'bin/codex'
                        or value.get('variant') != 'codex'
                        or not isinstance(value.get('target'), str)
                        or not value['target'].endswith('-apple-darwin')
                        or not executable.resolve().is_relative_to(package.resolve())
                        or not executable.is_file() or not os.access(executable, os.X_OK)):
                    continue
                candidates.append(executable)
            except (OSError, ValueError, TypeError, RuntimeError):
                continue
    return candidates


def find_agent(provider, *, environ=None, home=None, windows=None, application_roots=None,
               prefer_desktop=True):
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    windows = os.name == 'nt' if windows is None else windows
    override = env.get('YUKIO_' + provider.upper() + '_PATH')
    candidates = [Path(override).expanduser()] if override else []
    if not override:
        if provider == 'codex' and not windows and prefer_desktop:
            candidates += codex_desktop_candidates(home, application_roots)
        found = shutil.which(provider, path=env.get('PATH', ''))
        if found:
            candidates.append(Path(found))
        folders = [home / '.local/bin', home / '.npm-global/bin', home / '.volta/bin',
                   Path('/opt/homebrew/bin'), Path('/usr/local/bin')]
        folders += sorted((home / '.nvm/versions/node').glob('*/bin'), reverse=True)
        if windows:
            folders += [Path(env.get('APPDATA', str(home / 'AppData/Roaming'))) / 'npm',
                        Path(env.get('LOCALAPPDATA', str(home / 'AppData/Local'))) / 'Microsoft/WinGet/Links']
        for folder in folders:
            candidates += [folder / (provider + suffix) for suffix in (('.exe', '.cmd', '') if windows else ('',))]
        if provider == 'codex':
            candidates += [Path('/Applications/Codex.app/Contents/Resources/codex'),
                           home / 'Applications/Codex.app/Contents/Resources/codex']
    for path in candidates:
        if not path.is_file() or not (windows or os.access(path, os.X_OK)):
            continue
        if windows and path.suffix.lower() in ('.cmd', '.bat', '.ps1'):
            # npm shims are shell programs. Invoke their known JS entry directly,
            # so Unicode/spaces/metacharacters in paths never enter cmd.exe.
            package = '@openai/codex/bin/codex.js' if provider == 'codex' else '@anthropic-ai/claude-code/cli.js'
            script = path.parent / 'node_modules' / package
            nodes = [path.parent / 'node.exe']
            found_node = shutil.which('node', path=env.get('PATH', ''))
            if found_node:
                nodes.append(Path(found_node))
            # Start Menu apps can inherit an older PATH even after Node was
            # installed. Check its normal Windows locations without a shell.
            for folder in (env.get('NVM_SYMLINK'),
                           str(Path(env.get('ProgramFiles', 'C:/Program Files')) / 'nodejs'),
                           str(Path(env.get('LOCALAPPDATA', str(home / 'AppData/Local'))) / 'Programs/nodejs')):
                if folder:
                    nodes.append(Path(folder) / 'node.exe')
            node = next((str(p) for p in nodes if p.is_file()), None)
            if script.is_file() and node:
                return [node, str(script)]
            continue
        return [str(path)]
    return None


def probe_agent(provider, command):
    """Read only CLI help/login status; never send a chat or generate a turn.

    Probe every new request so signing in, upgrading or changing accounts takes
    effect without shared machine-specific state or stale login caches.
    """
    required = ({'--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                 '--sandbox', '--color', '--output-schema', '--output-last-message'} if provider == 'codex' else
                {'--print', '--safe-mode', '--output-format', '--no-session-persistence',
                 '--tools', '--disable-slash-commands', '--strict-mcp-config',
                 '--mcp-config', '--system-prompt', '--json-schema'})
    phase = 'compatibility'
    try:
        with tempfile.TemporaryDirectory(prefix='yukio-agent-check-') as folder:
            root = Path(folder)
            args = ['exec', '--help'] if provider == 'codex' else ['--help']
            code, out, err = run_bounded(command + args, '', root, 5)
            flags = set(re.findall(r'--[a-z][a-z0-9-]*', out.decode('utf-8', errors='replace')))
            if code or not required <= flags:
                return dict(state='unavailable', reason='agent_incompatible')
            if provider == 'claude' and not re.search(r'(?m)^\s+auth(?:\s|$)', out.decode('utf-8', errors='replace')):
                # Never guess a subcommand: an old CLI may treat it as a prompt.
                return dict(state='unknown')
            args = ['login', 'status'] if provider == 'codex' else ['auth', 'status', '--json']
            phase = 'login'
            code, out, err = run_bounded(command + args, '', root, 5)
            if provider == 'claude':
                try:
                    status = json.loads(out)
                    if isinstance(status, dict) and status.get('loggedIn') is False:
                        if status.get('authMethod') == 'third_party':
                            return dict(state='unknown')
                        return dict(state='unavailable', reason='agent_login_required')
                    if not isinstance(status, dict) or status.get('loggedIn') is not True:
                        return dict(state='unknown')
                except (ValueError, TypeError):
                    return dict(state='unknown')
            if code:
                reason = failure(out, err)
                if reason == 'agent_incompatible':
                    return dict(state='unknown')  # Help is compatible, login inspection is older.
                return dict(state='unavailable', reason=reason)
            return dict(state='ready')
    except ExplanationError as exc:
        return dict(state='unavailable', reason=('agent_compatibility_timeout' if phase == 'compatibility' else 'agent_login_check_timeout') if exc.code == 'agent_timeout' else exc.code)


def check_agent(provider):
    """Resolve and inspect the same entrypoint for setup and explanation."""
    command = find_agent(provider)
    if not command:
        return None, dict(state='unavailable', reason='agent_not_found')
    readiness = probe_agent(provider, command)
    if (readiness['state'] == 'unavailable' and provider == 'codex'
            and len(command) == 1
            and command[0].endswith('/Contents/Resources/codex-cli/bin/codex')
            and not os.environ.get('YUKIO_CODEX_PATH')
            and readiness.get('reason') in ('agent_incompatible', 'agent_start_failed',
                                           'agent_compatibility_timeout')):
        alternative = find_agent(provider, prefer_desktop=False)
        if alternative and alternative != command:
            command = alternative
            readiness = probe_agent(provider, command)
    return command, readiness


def select_agent(config, client=None):
    choice = config.get('agent', 'auto')
    order = ([client, 'claude' if client == 'codex' else 'codex'] if client in ('codex', 'claude')
             else ['codex', 'claude']) if choice == 'auto' else [choice]
    failures = []
    for provider in order:
        command, readiness = check_agent(provider)
        if command:
            if readiness['state'] in ('ready', 'unknown'):
                return dict(config, agent=provider, model=LABELS[provider], command=command)
            failures.append(readiness['reason'])
    raise ExplanationError(failures[0] if failures else 'agent_not_found')


def stop_process(process):
    if os.name == 'nt':
        # Kill this invocation's tree only; never terminate a user's other chats.
        taskkill = Path(os.environ.get('SystemRoot', 'C:/Windows'))/'System32/taskkill.exe'
        try:
            subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Some desktop execution policies disallow group signaling while
            # still allowing us to stop the exact child we launched.
            if process.poll() is None:
                process.kill()
    process.wait(timeout=5)


def run_bounded(command, prompt, cwd, timeout, extra_env=None):
    env = os.environ.copy()
    env.update(extra_env or {})
    # A frozen Python's loader paths must not leak into Node/native clients.
    for key in ('PYTHONHOME', 'PYTHONPATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH',
                'CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CODEX_THREAD_ID'):
        env.pop(key, None)
    env['CLAUDE_CODE_SKIP_PROMPT_HISTORY'] = '1'
    # Finder/Start Menu launches often omit the directory containing node.
    env['PATH'] = os.pathsep.join(dict.fromkeys([str(Path(command[0]).parent),
        str(Path.home() / '.local/bin'), '/opt/homebrew/bin', '/usr/local/bin', env.get('PATH', '')]))
    options = dict(cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options['start_new_session'] = True
    try:
        process = subprocess.Popen(command, **options)
    except OSError:
        raise ExplanationError('agent_start_failed') from None
    output = [bytearray(), bytearray()]
    oversized = threading.Event()
    def drain(pipe, target):
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                if len(target) + len(chunk) > MAX_RESPONSE_BYTES * 4:
                    oversized.set()
                    break
                target.extend(chunk)
        finally:
            pipe.close()
    workers = [threading.Thread(target=drain, args=(pipe, target), daemon=True)
               for pipe, target in zip((process.stdout, process.stderr), output)]
    for worker in workers:
        worker.start()
    def feed():
        try:
            process.stdin.write(prompt.encode('utf-8'))
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            process.stdin.close()
    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None or any(w.is_alive() for w in workers):
            if oversized.is_set():
                raise ExplanationError('response_too_large')
            if time.monotonic() >= deadline:
                raise ExplanationError('agent_timeout')
            time.sleep(.02)
        if oversized.is_set():
            raise ExplanationError('response_too_large')
        return process.returncode, bytes(output[0]), bytes(output[1])
    finally:
        if process.poll() is None or any(w.is_alive() for w in workers):
            stop_process(process)
        for worker in workers + [writer]:
            worker.join(timeout=1)


def failure(stdout, stderr):
    # Classify only; never expose provider output, paths, prompts or tokens.
    errors = []
    try:
        result = json.loads(stdout)
        if isinstance(result, dict) and (result.get('is_error') or result.get('subtype', '').startswith('error')):
            errors.append(str(result.get('result', '')) + str(result.get('errors', '')))
    except (ValueError, TypeError, AttributeError):
        pass
    lines = stderr.decode('utf-8', errors='replace').splitlines()
    for line in lines:
        if re.match(r'(?i)^(?:error|usage|unknown option|unexpected argument)', line):
            errors.append(line)
    # Codex can echo the source prompt before its final error. Never classify
    # from that echoed material or from incidental digits in timestamps.
    text = '\n'.join(errors or lines[-2:] or [stdout.decode('utf-8', errors='replace')[-2000:]]).lower()
    if any(s in text for s in ('model_not_found', 'model is not supported', 'model does not exist')) or re.search(r'model.{0,80}not supported', text):
        return 'agent_model_unavailable'
    if any(s in text for s in ('not logged in', 'not authenticated', 'authentication', 'unauthorized', 'please run /login', 'login required', 'invalid api key')) or re.search(r'(?:status|http|code)[\s"\x27:=]+401\b', text):
        return 'agent_login_required'
    if any(s in text for s in ('rate limit', 'rate_limit', 'usage limit', 'usage_limit', 'quota', 'credit balance')) or re.search(r'(?:status|http|code)[\s"\x27:=]+429\b', text):
        return 'agent_rate_limited'
    if any(s in text for s in ('unknown option', 'unexpected argument', 'unrecognized', 'unknown flag')):
        return 'agent_incompatible'
    return 'agent_failed'


def codex_overrides():
    """Retain model/provider choice without loading hooks, tools or instructions.

    Header secrets become child-only environment variables, never argv. Auth
    remains in the original CODEX_HOME and its normal credential store.
    """
    path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
    if not path.is_file():
        return [], {}
    try:
        raw = path.read_bytes()
        if len(raw) > 1024 * 1024:
            raise ValueError('Config too large')
        try:
            import tomllib
            value = tomllib.loads(raw.decode('utf-8'))
        except ImportError:
            # Python 3.9/3.10 source runs support ordinary account/model setup.
            # Packaged runtime uses Python 3.12, including full TOML support.
            value = {}
            for line in raw.decode('utf-8').splitlines():
                if line.lstrip().startswith('['):
                    break
                match = re.match(r'\s*(model|model_provider|profile)\s*=\s*("(?:[^"\\]|\\.)*"|\x27[^\x27]*\x27)\s*(?:#.*)?$', line)
                if match:
                    value[match[1]] = json.loads(match[2]) if match[2].startswith('"') else match[2][1:-1]
            if value.get('model_provider') not in (None, 'openai') or value.get('profile'):
                raise ExplanationError('agent_config_unsupported')
        profile = value.get('profile')
        if profile:
            value = dict(value, **value.get('profiles', {}).get(profile, {}))
        def toml(v):
            if isinstance(v, dict):
                return '{' + ','.join(json.dumps(k) + '=' + toml(x) for k, x in v.items()) + '}'
            if isinstance(v, list):
                return '[' + ','.join(toml(x) for x in v) + ']'
            if isinstance(v, (str, bool, int, float)):
                return json.dumps(v)
            raise ValueError('Unsupported config value')
        args, env = [], {}
        for key in ('model', 'model_provider', 'model_reasoning_effort', 'cli_auth_credentials_store',
                    'forced_login_method', 'forced_chatgpt_workspace_id'):
            if key in value:
                args += ['-c', key + '=' + toml(value[key])]
        provider = value.get('model_provider')
        selected = value.get('model_providers', {}).get(provider)
        if selected:
            selected = dict(selected)
            headers = dict(selected.pop('env_http_headers', {}))
            for index, (header, secret) in enumerate(selected.pop('http_headers', {}).items()):
                name = 'YUKIO_AGENT_HEADER_' + str(index)
                headers[header] = name
                env[name] = str(secret)
            if headers:
                selected['env_http_headers'] = headers
            if 'experimental_bearer_token' in selected:
                env['YUKIO_AGENT_BEARER'] = selected.pop('experimental_bearer_token')
                selected['env_key'] = 'YUKIO_AGENT_BEARER'
            args += ['-c', 'model_providers.' + json.dumps(provider) + '=' + toml(selected)]
        return args, env
    except (OSError, ValueError, TypeError, AttributeError):
        raise ExplanationError('agent_config_unsupported') from None


def call_agent(config, payload):
    from explanation import call_model
    if config.get('provider') != 'agent':
        return call_model(config, payload)
    provider = config['agent']
    from explanation import output_system
    system = output_system(payload)
    prompt = system + '\n只根据下面资料生成规定的 JSON；不要调用工具。\n' + encode(payload)
    with tempfile.TemporaryDirectory(prefix='yukio-explanation-') as folder:
        root = Path(folder)
        schema = schema_for(payload)
        extra_env = {}
        if provider == 'codex':
            overrides, extra_env = codex_overrides()
            schema_path = root / 'schema.json'
            schema_path.write_text(encode(schema), encoding='utf-8')
            result_path = root / 'answer.json'
            # Isolated config retains CLI auth, prevents user hooks/MCP/plugins.
            command = config['command'] + ['exec', '--ignore-user-config', '--ephemeral',
                '--skip-git-repo-check', '--sandbox', 'read-only', '--color', 'never',
                '-c', 'approval_policy="never"', '-c', 'project_doc_max_bytes=0', '-c', 'features.shell_tool=false',
                '-c', 'features.apply_patch_freeform=false', '-c', 'features.multi_agent=false',
                '-c', 'features.plugins=false', '-c', 'features.apps=false',
                '-c', 'web_search="disabled"', '--output-schema', str(schema_path),
                '--output-last-message', str(result_path)] + overrides + ['-']
        else:
            command = config['command'] + ['--print', '--safe-mode', '--output-format', 'json',
                '--no-session-persistence', '--tools', '', '--disable-slash-commands',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--system-prompt', system, '--json-schema', encode(schema)]
            prompt = encode(payload)
        code, stdout, stderr = run_bounded(command, prompt, root, config['timeout_seconds'], extra_env)
        if code:
            raise ExplanationError(failure(stdout, stderr))
        try:
            if provider == 'codex':
                if not result_path.is_file():
                    raise ExplanationError('incomplete_response')
                with result_path.open('rb') as stream:
                    raw = stream.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ExplanationError('response_too_large')
                content = raw.decode('utf-8')
            else:
                result = json.loads(stdout)
                if not isinstance(result, dict):
                    raise ExplanationError('invalid_response')
                if result.get('is_error') or result.get('subtype') != 'success':
                    raise ExplanationError(failure(stdout, stderr))
                content = encode(result['structured_output']) if isinstance(result.get('structured_output'), dict) else result.get('result')
            return complete_response(content, payload)
        except (ValueError, UnicodeError, TypeError, KeyError, RecursionError):
            raise ExplanationError('invalid_response') from None


def provider_options(directory):
    return [dict(id='auto', label=LABELS['auto'], available=True)] + [
        dict(id=p, label=LABELS[p], available=bool(find_agent(p))) for p in ('codex', 'claude')] + ([
        dict(id='lan', label=LABELS['lan'], available=(Path(directory) / 'lan-model.json').is_file())]
        if local_lan_enabled(directory) else [])
