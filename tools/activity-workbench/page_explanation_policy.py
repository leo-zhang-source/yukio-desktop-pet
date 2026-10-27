"""Local opt-in for page-owned explanations, bound to the configured recipient.

The policy is written only when the user requests automatic page explanations.
It is outside the distributable. A different destination does not inherit it.
"""
import json
from pathlib import Path


def enabled(directory,config):
    if not directory or not config:return False
    from agent_explanation import preferences
    try:
        own=Path(directory)/'explanation-provider.json'
        if own.exists():
            value=preferences(directory)
            return value['automatic_on_open'] and value['provider']==config.get('agent','lan')
    except (OSError,ValueError,RecursionError):return False
    if config.get('provider')=='agent':return False
    try:
        raw=(Path(directory)/'page-explanation-policy.json').read_bytes()
        if len(raw)>2048:return False
        value=json.loads(raw)
    except (OSError,ValueError,RecursionError):return False
    return (isinstance(value,dict) and value.get('version')==1 and value.get('automatic_on_open') is True
            and value.get('scope')=='selected_chat_short_excerpts'
            and value.get('destination')==config.get('base_url'))
