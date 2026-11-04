"""Local, read-only onboarding checks for user-owned explanation assistants."""
import shlex
import threading

from agent_explanation import find_agent, probe_agent


class AgentSetup:
    def __init__(self):
        self._locks = {name: threading.Lock() for name in ('codex', 'claude')}

    def inventory(self):
        # Opening settings does not start either client or inspect credentials.
        return {'agents': [dict(provider=name, state='not_checked' if find_agent(name)
                                else 'not_found') for name in self._locks]}

    def check(self, provider):
        if not isinstance(provider, str) or provider not in self._locks:
            raise ValueError('Invalid assistant')
        lock = self._locks[provider]
        if not lock.acquire(blocking=False):
            return dict(provider=provider, state='checking')
        try:
            command = find_agent(provider)
            if not command:
                return dict(provider=provider, state='not_found')
            result = probe_agent(provider, command)
            if result['state'] == 'ready':
                state = 'ready'
            elif result['state'] == 'unknown':
                state = 'unverified'
            else:
                state = {'agent_login_required': 'login_required',
                         'agent_incompatible': 'incompatible',
                         'agent_compatibility_timeout': 'compatibility_timeout',
                         'agent_login_check_timeout': 'login_check_timeout'}.get(
                             result.get('reason'), 'check_failed')
            value = dict(provider=provider, state=state)
            if state == 'login_required':
                # Only offer a known login subcommand after compatible CLI help
                # and a definite logged-out result. Never include account data.
                args = ['login'] if provider == 'codex' else ['auth', 'login']
                value['login_command'] = shlex.join(command + args)
            return value
        except OSError:
            return dict(provider=provider, state='check_failed')
        finally:
            lock.release()
