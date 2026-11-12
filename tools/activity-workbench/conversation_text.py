"""Separate visible speech from known client-generated transcript envelopes.

This is presentation filtering, not an instruction parser or a transcript edit.
Keep real text beside a wrapper; never turn a continuation summary into a new
user request. Apply before clipping, since client context can be very long.
"""
import re

_TAGS = (
    'system-reminder', 'task-notification', 'local-command-caveat',
    'local-command-stdout', 'local-command-stderr', 'command-name',
    'command-message', 'command-args', 'environment_context',
    'in-app-browser-context', 'app-context', 'external_codex_apps_open_page',
    'recent-project-folders', 'INSTRUCTIONS',
)
_BLOCK = re.compile(r'<(' + '|'.join(_TAGS) + r')\b[^>]*>.*?(?:</\1\s*>|$)', re.S | re.I)
_ATTACHMENT = re.compile(r'<image\s+name=\[Image #\d+\]\s+path=.*?(?:</image\s*>|$)', re.S | re.I)
_CONTINUATION = re.compile(
    r'^This session is being continued from a previous conversation\b', re.I)
_INTERRUPTION = re.compile(r'^\[Request interrupted by user[^\]]*(?:\]|$)', re.I)


def conversation_text(text):
    if not isinstance(text, str):
        return ''
    text = _BLOCK.sub('', text).strip()
    # Desktop image envelopes contain a local attachment path, not a request.
    # Remove the full envelope before clipping; ordinary HTML examples remain.
    text = _ATTACHMENT.sub('', text).strip()
    if _CONTINUATION.match(text):
        return ''
    text = _INTERRUPTION.sub('', text).strip()
    return text
