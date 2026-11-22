"""Claude Code 会话转录（~/.claude/projects/<项目>/<会话>.jsonl）→ 事件。

保留这一路是因为：在 Windows 上把 Claude Code 指向 DeepSeek 的 Anthropic 兼容端点
（ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic）时，跑的是 DeepSeek 模型，
写出来的仍是 Claude Code 格式的转录。两种 DeepSeek 用法因此都能跟随。

这是 Claude Code 本地写入的会话记录，不是公开 API；字段可能随版本变化。
移植自 YukioPlayer/Sources/YukioCore/ClaudeParsers.swift。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .classify import CONTINUE_PREVIOUS, classify, describe, question
from .events import Kind, PetEvent, TodoItem, TodoStatus, parse_timestamp

SOURCE = "claude-transcript"


def prompt_line(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line or line.startswith("<"):
            continue
        return line[:80]
    return None


def _is_failure(result: Dict[str, Any]) -> bool:
    """工具结果是否算失败：is_error 为真，且不是用户拒绝授权或中断。"""
    if result.get("is_error") is not True:
        return False
    content = result.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    else:
        text = ""
    return not ("doesn't want to proceed" in text or text.startswith("[Request interrupted")
                or text in ('Permission denied by hook','The user declined this operation in Yukio.'))


def _todo_id(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _task_events(tool: str, input: Dict[str, Any]):
    """任务清单工具 → (事件类型, 条目)。"""
    if tool in ("TodoWrite", "mcp__ccd_turn__update_plan"):
        todos = input.get("todos" if tool == "TodoWrite" else "items")
        if not isinstance(todos, list):
            return None
        items = []
        for i, t in enumerate(todos):
            if not isinstance(t, dict):
                continue
            status = t.get("status")
            try:
                parsed = TodoStatus(status) if isinstance(status, str) else TodoStatus.pending
            except ValueError:
                parsed = TodoStatus.pending
            items.append(TodoItem(_todo_id(t.get("id")) or str(i),
                                  t.get("content") or t.get("activeForm"), parsed))
        return Kind.todo_list, items
    if tool == "TaskUpdate":
        tid = _todo_id(input.get("taskId"))
        if not tid:
            return None
        status = input.get("status")
        try:
            parsed = TodoStatus(status) if isinstance(status, str) else None
        except ValueError:
            parsed = None
        subject = input.get("subject") if isinstance(input.get("subject"), str) else None
        if parsed is None and subject is None:
            return None
        return Kind.todo_update, [TodoItem(tid, subject, parsed)]
    return None


def _task_created(result: Any) -> Optional[TodoItem]:
    """TaskCreate 的结果：{"task": {"id": "3", "subject": "…"}}。"""
    if not isinstance(result, dict):
        return None
    task = result.get("task")
    if not isinstance(task, dict):
        return None
    tid = _todo_id(task.get("id"))
    subject = task.get("subject")
    if not tid or not isinstance(subject, str):
        return None
    return TodoItem(tid, subject)


@dataclass
class _Turn:
    latest_timestamp: float = float('-inf')
    prompt_id: Optional[str] = None
    answer_id: Optional[str] = None
    completed_answer_id: Optional[str] = None
    response_id: Optional[str] = None
    response_has_tools: bool = False
    answer_entrypoint: Optional[str] = None
    answer_timestamp: Optional[float] = None
    confirmed_at: Optional[float] = None
    started_at: Optional[float] = None
    phase: str = 'unknown'
    calls: Dict[str, str] = field(default_factory=dict)
    seen: Dict[str, bool] = field(default_factory=dict)
    background: Dict[str, str] = field(default_factory=dict)
    background_limited: bool = False

    def pending(self):
        return bool(self.calls) or self.background_limited or (self.prompt_id or '') in self.background.values()


class ClaudeTranscriptParser:
    source = SOURCE

    def __init__(self):
        self._turns: Dict[str, _Turn] = {}

    def _turn(self, session):
        if session not in self._turns:
            if len(self._turns) >= 1024:
                del self._turns[min(self._turns, key=lambda key: self._turns[key].latest_timestamp)]
            self._turns[session] = _Turn()
        return self._turns[session]

    def history_checkpoint(self):
        turns = {key: asdict(value) for key, value in self._turns.items()}
        for value in turns.values():
            if not math.isfinite(value['latest_timestamp']): value['latest_timestamp'] = None
        return dict(claude_lifecycle_version=2, turns=turns)

    @classmethod
    def from_history_checkpoint(cls, state):
        if state.get('claude_lifecycle_version') != 2 or not isinstance(state.get('turns'), dict) or len(state['turns']) > 1024:
            raise ValueError('Invalid Claude lifecycle checkpoint')
        parser = cls()
        for session, value in state['turns'].items():
            if not isinstance(session, str) or not session or len(session) > 256 or not isinstance(value, dict) or set(value) != set(asdict(_Turn())):
                raise ValueError('Invalid Claude lifecycle scope')
            value = dict(value)
            for key in ('prompt_id', 'answer_id', 'completed_answer_id', 'response_id', 'answer_entrypoint'):
                if value[key] is not None and (not isinstance(value[key], str) or len(value[key]) > 256):
                    raise ValueError('Invalid Claude lifecycle identity')
            for key in ('response_has_tools', 'background_limited'):
                if type(value[key]) is not bool: raise ValueError('Invalid Claude lifecycle flag')
            stamp = value['latest_timestamp']
            if stamp is not None and (type(stamp) not in (int, float) or not math.isfinite(stamp)):
                raise ValueError('Invalid Claude lifecycle timestamp')
            value['latest_timestamp'] = stamp if stamp is not None else float('-inf')
            for key in ('answer_timestamp', 'confirmed_at', 'started_at'):
                if value[key] is not None and (type(value[key]) not in (int, float) or not math.isfinite(value[key])):
                    raise ValueError('Invalid Claude interaction timestamp')
            if value['phase'] not in ('unknown', 'working', 'completed', 'cancelled', 'failed'):
                raise ValueError('Invalid Claude interaction phase')
            for key in ('calls', 'seen'):
                items=value[key]
                if not isinstance(items, dict) or len(items)>4096 or any(not isinstance(k,str) or not 0<len(k)<=(320 if key=='seen' else 256) for k in items):
                    raise ValueError('Invalid Claude interaction identities')
            if any(not isinstance(v,str) or len(v)>256 for v in value['calls'].values()) or any(v is not True for v in value['seen'].values()):
                raise ValueError('Invalid Claude interaction values')
            jobs = value['background']
            if not isinstance(jobs, dict) or len(jobs) > 256 or any(not isinstance(x, str) or len(x) > 256 for pair in jobs.items() for x in pair):
                raise ValueError('Invalid Claude background identities')
            parser._turns[session] = _Turn(**value)
        return parser

    def snapshot(self, session):
        turn=self._turns.get(session)
        if turn is None:return None
        questions=[key for key,name in turn.calls.items() if name in ('AskUserQuestion','ExitPlanMode')]
        return dict(phase='waiting' if questions else turn.phase, started_at=turn.started_at,
                    interaction_kind='permission' if questions and all(turn.calls[key]=='ExitPlanMode' for key in questions) else 'question',
                    timestamp=turn.latest_timestamp if math.isfinite(turn.latest_timestamp) else None,
                    question_ids=questions, pending_calls=len(turn.calls), pending_background=len(turn.background),
                    limited=turn.background_limited)

    @staticmethod
    def _completion(turn, session):
        if turn.confirmed_at is None or not turn.answer_id or turn.pending():return []
        at=turn.confirmed_at;turn.completed_answer_id=turn.answer_id;turn.answer_id=None;turn.confirmed_at=None
        return [PetEvent(at,SOURCE,session,kind) for kind in (Kind.final_answer,Kind.task_end)]

    @staticmethod
    def _background_result(turn, obj):
        result = obj.get('toolUseResult')
        if not isinstance(result, dict): return
        job = result.get('backgroundTaskId')
        if isinstance(job, str) and 0 < len(job) <= 256:
            if job in turn.background or len(turn.background) < 256:
                turn.background[job] = turn.prompt_id or ''
            else: turn.background_limited = True
        task = result.get('task')
        if isinstance(task, dict) and task.get('status') in ('completed', 'failed', 'killed', 'cancelled', 'stopped'):
            identity = task.get('task_id') or task.get('id')
            if isinstance(identity, str): turn.background.pop(identity, None)

    @staticmethod
    def _notification(turn, obj, text):
        origin = obj.get('origin')
        if not isinstance(origin, dict) or origin.get('kind') != 'task-notification' or obj.get('promptSource') != 'system':
            return False
        # Client-tagged task notifications continue the original human request.
        # Never infer a job's completion from ordinary assistant/user prose.
        match = re.match(r'^\s*<task-notification>(.*?)</task-notification>', text[:16000], re.S)
        if match:
            ids = re.findall(r'<task-id>([A-Za-z0-9_-]{1,256})</task-id>', match[1])
            statuses = re.findall(r'<status>(completed|failed|killed|cancelled|stopped)</status>', match[1])
            if len(ids) == len(statuses) == 1: turn.background.pop(ids[0], None)
        return True

    def events_from_line(self, data: bytes, fallback_session: str = "",
                         fallback_ts: float = 0.0) -> List[PetEvent]:
        try:
            obj = json.loads(data.decode("utf-8", "replace"))
        except ValueError:
            return []
        return self.events(obj) if isinstance(obj, dict) else []

    def events(self, obj: Dict[str, Any]) -> List[PetEvent]:
        events=self._events(obj)
        for event in events:
            turn=self._turn(event.session)
            if event.kind==Kind.task_start:
                turn.phase='working';turn.started_at=event.ts
            elif event.kind==Kind.task_end:turn.phase='completed'
            elif event.kind==Kind.task_abort:turn.phase='cancelled'
            elif event.kind==Kind.task_failed:turn.phase='failed'
            elif event.kind in (Kind.thinking,Kind.activity_start):turn.phase='working'
        return events

    def _events(self, obj: Dict[str, Any]) -> List[PetEvent]:
        type_ = obj.get("type")
        session = obj.get("sessionId")
        if not isinstance(type_, str) or not isinstance(session, str) or not 0 < len(session) <= 256:
            return []
        # 子代理（sidechain）的活动不驱动主角色。
        if obj.get("isSidechain") is True or "agentId" in obj:
            return []
        if type_ in ("custom-title", "ai-title"):
            title = obj.get("customTitle") or obj.get("aiTitle")
            if not isinstance(title, str):
                return []
            return [PetEvent(0, SOURCE, session, Kind.session_title, detail=title)]
        turn = self._turn(session)
        if type_ == 'last-prompt':
            if (turn.answer_id and obj.get('leafUuid') == turn.answer_id
                    and turn.answer_entrypoint == 'sdk-cli'):
                turn.confirmed_at=turn.answer_timestamp
                return self._completion(turn,session)
            return []
        ts = parse_timestamp(obj.get("timestamp"))
        if ts is None:
            return []
        uuid=obj.get('uuid')
        if isinstance(uuid,str) and 0<len(uuid)<=256:
            identity=uuid if type_=='user' else uuid+':'+str(ts)
            if identity in turn.seen:return []
            turn.seen[identity]=True
            if len(turn.seen)>4096:del turn.seen[next(iter(turn.seen))]
        if ts < turn.latest_timestamp:
            message=obj.get('message')
            if (type_=='user' and isinstance(message,dict) and message.get('role') in (None,'user')
                    and obj.get('isMeta') is not True and obj.get('isCompactSummary') is not True
                    and isinstance(message.get('content'),list)):
                out=[]
                for block in message['content']:
                    if not isinstance(block,dict) or block.get('type')!='tool_result':continue
                    call=block.get('tool_use_id')
                    if not isinstance(call,str) or call not in turn.calls:continue
                    del turn.calls[call]
                    out.append(PetEvent(ts,SOURCE,session,Kind.activity_failed if _is_failure(block) else Kind.activity_end,event_id=call))
                if out:self._background_result(turn,obj);out+=self._completion(turn,session)
                return out
            return []

        def ev(kind, event_id=None, activity=None, tool=None, detail=None, todos=None, question=None):
            return PetEvent(ts, SOURCE, session, kind, event_id=event_id, activity=activity,
                            tool=tool, detail=detail, todos=todos, question=question)

        if type_ == "user":
            if obj.get("isMeta") is True or obj.get("isCompactSummary") is True:
                return []
            message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            if isinstance(message.get('role'), str) and message['role'] != 'user':
                return []
            content = message.get("content")

            def prompt_events(text, has_other_blocks):
                if self._notification(turn, obj, text):
                    turn.latest_timestamp = ts
                    turn.answer_id = None
                    return [ev(Kind.thinking)]
                kind = self._user_text(text, has_other_blocks)
                if not kind:
                    return []
                turn.latest_timestamp = ts
                turn.answer_id = None
                turn.confirmed_at = None
                turn.calls.clear()
                turn.prompt_id = next((obj[k] for k in ('promptId', 'uuid') if isinstance(obj.get(k), str) and len(obj[k]) <= 256), 'turn:' + str(ts))
                turn.response_id = None
                turn.response_has_tools = False
                return [ev(kind, detail=prompt_line(text))]

            if isinstance(content, list):
                results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if results:
                    turn.latest_timestamp = ts
                    if turn.answer_timestamp is None or ts>turn.answer_timestamp:
                        turn.answer_id = None;turn.confirmed_at=None
                    self._background_result(turn, obj)
                    out = []
                    for b in results:
                        tid = b.get("tool_use_id")
                        if not isinstance(tid, str):
                            continue
                        turn.calls.pop(tid,None)
                        out.append(ev(Kind.activity_failed if _is_failure(b) else Kind.activity_end, event_id=tid))
                    item = _task_created(obj.get("toolUseResult"))
                    if item:
                        out.append(ev(Kind.todo_update, todos=[item]))
                    return out+self._completion(turn,session)
                text = "\n".join(b.get("text", "") for b in content
                                 if isinstance(b, dict) and b.get("type") == "text")
                return prompt_events(text, bool(content))
            if isinstance(content, str):
                return prompt_events(content, False)
            return []

        if type_ == "assistant":
            message = obj.get("message")
            if not isinstance(message, dict):
                return []
            if isinstance(message.get('role'), str) and message['role'] != 'assistant':
                return []
            if obj.get('isMeta') is True or obj.get('isCompactSummary') is True:
                return []
            if isinstance(obj.get('uuid'), str) and obj['uuid'] == turn.completed_answer_id:
                return []
            turn.latest_timestamp = ts
            turn.answer_id = None
            turn.confirmed_at=None
            if message.get("model") == "<synthetic>":
                turn.calls.clear()
                # 客户端合成的消息：本轮不会再有真实回答。
                return [ev(Kind.task_failed if obj.get("isApiErrorMessage") is True else Kind.task_abort)]
            stop = message.get("stop_reason")
            blocks = message.get("content") if isinstance(message.get("content"), list) else []
            has_tools = any(isinstance(b, dict) and b.get('type') == 'tool_use' for b in blocks)
            response_id = message.get('id') if isinstance(message.get('id'), str) and len(message['id']) <= 256 else None
            if response_id is None or response_id != turn.response_id:
                turn.response_id = response_id
                turn.response_has_tools = False
            turn.response_has_tools = turn.response_has_tools or has_tools
            has_text = any(isinstance(b, dict) and b.get('type') == 'text'
                           and isinstance(b.get('text'), str) and b['text'].strip() for b in blocks)
            if stop == 'end_turn' and has_text and not turn.response_has_tools and isinstance(obj.get('uuid'), str) and 0 < len(obj['uuid']) <= 256:
                turn.answer_id = obj['uuid']
                turn.answer_timestamp=ts
                turn.answer_entrypoint = obj.get('entrypoint') if isinstance(obj.get('entrypoint'), str) and len(obj['entrypoint']) <= 256 else None
            out: List[PetEvent] = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                btype = b.get("type")
                if btype == "tool_use":
                    name = b.get("name") or ""
                    input = b.get("input") if isinstance(b.get("input"), dict) else {}
                    kind = classify(name, input)
                    activity = None if kind == CONTINUE_PREVIOUS else kind
                    bid = b.get("id") if isinstance(b.get("id"), str) else None
                    if bid and len(bid)<=256:
                        if len(turn.calls)<4096:turn.calls[bid]=name
                        else:turn.background_limited=True
                    out.append(ev(Kind.activity_start, event_id=bid, activity=activity,
                                  tool=name, detail=describe(name, input),
                                  question=question(name, input)))
                    task = _task_events(name, input)
                    if task:
                        out.append(ev(task[0], todos=task[1]))
                elif btype in ("thinking", "redacted_thinking"):
                    out.append(ev(Kind.thinking))
                elif btype == "text":
                    # Model response termination precedes the client's Stop-hook decision.
                    out.append(ev(Kind.thinking))
            return out

        if type_ == "system":
            if obj.get('subtype') == 'api_error':
                turn.latest_timestamp = ts
                turn.answer_id = None
                return [ev(Kind.thinking)]
            subtype = obj.get('subtype')
            if subtype not in ('stop_hook_summary', 'turn_duration') or not turn.answer_id or obj.get('parentUuid') != turn.answer_id:
                return []
            if subtype == 'turn_duration' and not (turn.answer_entrypoint == obj.get('entrypoint') == 'cli'
                    and type(obj.get('durationMs')) in (int, float) and math.isfinite(obj['durationMs']) and obj['durationMs'] >= 0):
                return []
            answer = turn.answer_id
            turn.latest_timestamp = ts
            stopped = subtype == 'turn_duration' or (obj.get('preventedContinuation') is False and obj.get('hasOutput') is False
                       and obj.get('hookErrors') == [] and obj.get('hookAdditionalContext') == []
                       and not obj.get('stopReason'))
            if not stopped:
                turn.answer_id=None;turn.confirmed_at=None
                return [ev(Kind.thinking)]
            turn.confirmed_at=ts
            return self._completion(turn,session) or [ev(Kind.thinking)]
        if type_ == 'api-request':
            if obj.get('querySource') != 'sdk':
                return []
            turn.latest_timestamp = ts
            turn.answer_id = None
            return [ev(Kind.thinking)]
        return []

    @staticmethod
    def _user_text(text: str, has_other_blocks: bool) -> Optional[Kind]:
        t = text.strip()
        if t.startswith("[Request interrupted by user"):
            return Kind.task_abort
        # 本地命令（/clear、/model 等）的回显不会触发模型回答。
        if t.startswith("<local-command-") or t.startswith("<command-name>") or t.startswith("<command-message>"):
            return None
        if not t and not has_other_blocks:
            return None
        return Kind.task_start
