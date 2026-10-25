"""Optional local project brief, bound to an explicit client/chat/agent/branch.

This is supplied context, not activity evidence or proof of completed work. No
arbitrary file paths or transcript scanning are exposed through the HTTP API.
"""
import json
from pathlib import Path
from source_context import clean
from history_view import key_parts


def chat_identity(key):
    try:
        parts=key_parts(key)
        # Files and generations change when a client resumes/compacts a chat.
        # Explicit session, agent and branch identity survive that move.
        return tuple(parts[2:]) if parts[2] and not parts[2].startswith('source-') else None
    except (ValueError,TypeError):return None


class ProjectContext:
    def __init__(self,path):self.path=Path(path) if path else None

    def get(self,client,key):
        if not self.path:return None
        try:
            with self.path.open('rb') as stream:raw=stream.read(32769)
            if len(raw)>32768:return None
            data=json.loads(raw)
        except (OSError,ValueError,RecursionError):return None
        if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('contexts'),list):return None
        matches=[x for x in data['contexts'][:16] if isinstance(x,dict) and x.get('client')==client and x.get('key')==key]
        if not matches:
            identity=chat_identity(key)
            if identity:
                matches=[x for x in data['contexts'][:16] if isinstance(x,dict) and x.get('client')==client and chat_identity(x.get('key'))==identity]
        if len(matches)!=1:return None
        item=matches[0];result={}
        for field,limit in [('goal',320),('before',600),('now',240),('next',240),('benefit',240),('source_note',200),('object_names',600)]:
            if not isinstance(item.get(field,''),str):return None
            result[field]=clean(item.get(field,''),limit)
        return result if result['goal'] else None
