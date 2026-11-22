"""Optional Claude process presence. No peer keys, sockets or task text are read.

Registry status supplements transcript evidence; idle never certifies success.
Unknown formats fail closed. Process start identity prevents PID reuse.
"""
import ctypes
import datetime
import json
import math
import os
from pathlib import Path
import stat
import sys
import threading
import time
import uuid


class _BSDInfo(ctypes.Structure):
    _fields_ = [('fields', ctypes.c_uint32 * 12), ('comm', ctypes.c_char * 16),
                ('name', ctypes.c_char * 32), ('counts', ctypes.c_uint32 * 6),
                ('started', ctypes.c_uint64), ('microseconds', ctypes.c_uint64)]


def matches_process(pid, start):
    if sys.platform != 'darwin':return False
    try:
        info = _BSDInfo()
        lib = ctypes.CDLL('/usr/lib/libproc.dylib')
        if lib.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info)) != ctypes.sizeof(info):return False
        # The observed Claude registry normalizes procStart to UTC, including
        # on a host whose local timezone is America/Los_Angeles.
        parsed = datetime.datetime.strptime(start, '%a %b %d %H:%M:%S %Y').replace(tzinfo=datetime.timezone.utc).timestamp()
        return info.fields[5] == os.getuid() and abs(parsed-info.started) < 1
    except (OSError, ValueError, OverflowError):return False


class ClaudeRuntimeIndex:
    def __init__(self, root=None, *, clock=time.time, process=matches_process):
        self.root=Path(root) if root is not None else None
        self.clock=clock;self.process=process;self.lock=threading.Lock()
        self.checked=None;self.cache={};self.known={}

    def get(self, session):
        with self.lock:
            now=self.clock()
            if self.checked is not None and 0<=now-self.checked<2:return self.cache.get(session)
            result={};conflicts=set()
            if self.root is not None and self.root.is_dir() and not self.root.is_symlink():
                try:
                    with os.scandir(self.root) as paths:
                        for n, entry in enumerate(paths):
                            if n>=1024:break
                            if not entry.name.endswith('.json') or not entry.name[:-5].isdecimal():continue
                            descriptor=None
                            try:
                                pid=int(entry.name[:-5])
                                if not 0<pid<2**31:continue
                                descriptor=os.open(entry.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                                with os.fdopen(descriptor,'rb') as stream:
                                    descriptor=None;info=os.fstat(stream.fileno())
                                    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>16384:continue
                                    raw=stream.read(16385)
                                if len(raw)>16384:continue
                                row=json.loads(raw)
                                if not isinstance(row,dict) or type(row.get('pid')) is not int or row['pid']!=pid or row.get('pidDomain')!='darwin':continue
                                sid=row.get('sessionId');uuid.UUID(sid)
                                if row.get('status') not in ('busy','waiting','idle'):continue
                                updated=row.get('updatedAt');start=row.get('procStart')
                                if type(updated) not in (float,int) or not math.isfinite(updated) or not 0<=updated<=now*1000+1000:continue
                                if not isinstance(start,str) or len(start)>64 or not self.process(pid,start):continue
                                if sid in result:conflicts.add(sid)
                                result[sid]=dict(status='working' if row['status']=='busy' else row['status'],updated_at=updated,pid=pid,process_start=start)
                            except (OSError,TypeError,ValueError,AttributeError,RecursionError):continue
                            finally:
                                if descriptor is not None:os.close(descriptor)
                except OSError:pass
            for sid in conflicts:result.pop(sid,None)
            for sid, old in list(self.known.items()):
                if sid not in result and not self.process(old['pid'],old['process_start']):
                    result[sid]=dict(status='offline',updated_at=now*1000)
            self.known.update({sid:row for sid,row in result.items() if row['status']!='offline'})
            for sid in conflicts:self.known.pop(sid,None)
            self.cache=result;self.checked=now
            return result.get(session)
