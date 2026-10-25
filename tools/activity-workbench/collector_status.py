"""Only fixed aggregate recorder status files beside each configured database."""
from datetime import datetime,timezone
import json
from pathlib import Path

STATES={'active','waiting','degraded','partial_history','paused_capacity','source_unavailable','stopped','starting','failed'}
NUMBERS=('discovered_files','pending_files','error_files','events_saved_this_run','observation_gaps','database_bytes')

def read_status(database,client,now=None):
    now=now or datetime.now(timezone.utc)
    directory=Path(database).parent
    names=[client+'-workbench-status.json','collector-status.json' if client=='codex' else client+'-collector-status.json']
    candidates=[]
    for name in names:
        try:
            with (directory/name).open('rb') as stream:raw=stream.read(32769)
            if len(raw)>32768:continue
            data=json.loads(raw)
            if not isinstance(data,dict) or data.get('state') not in STATES:continue
            timestamp=datetime.fromisoformat(data['updated_at'].replace('Z','+00:00'))
            age=(now-timestamp).total_seconds()
            if age< -5:continue
            out={k:data[k] for k in NUMBERS if type(data.get(k)) is int and 0<=data[k]<2**63}
            state=data['state']
            out.update(state='stale' if age>15 and state not in ('stopped','failed') else state,updated_at=timestamp.isoformat())
            candidates.append((timestamp,out))
        except (OSError,ValueError,TypeError,KeyError,AttributeError):continue
    return max(candidates,key=lambda x:x[0])[1] if candidates else dict(state='unavailable')
