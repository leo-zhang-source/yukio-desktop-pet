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
    return not ("doesn't want to proceed" in text or text.startswith("[Request interrupted"))


def _todo_id(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _task_events(tool: str, input: Dict[str, Any]):
    """任务清单工具 → (事件类型, 条目)。"""
    if tool == "TodoWrite":
        todos = input.get("todos")
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
    background: Dict[str, str] = field(default_factory=dict)
    background_limited: bool = False

    def pending(self):
        return self.background_limited or (self.prompt_id or '') in self.background.values()


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
        return dict(claude_lifecycle_version=1, turns=turns)

    @classmethod
    def from_history_checkpoint(cls, state):
        if state.get('claude_lifecycle_version') != 1 or not isinstance(state.get('turns'), dict) or len(state['turns']) > 1024:
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
            jobs = value['background']
            if not isinstance(jobs, dict) or len(jobs) > 256 or any(not isinstance(x, str) or len(x) > 256 for pair in jobs.items() for x in pair):
                raise ValueError('Invalid Claude background identities')
            parser._turns[session] = _Turn(**value)
        return parser

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
        if isinstance(task, dict) and task.get('status') in ('completed', 'failed', 'killed', 'cancelled'):
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
            statuses = re.findall(r'<status>(completed|failed|killed|cancelled)</status>', match[1])
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
                    and turn.answer_entrypoint == 'sdk-cli' and not turn.pending()):
                turn.completed_answer_id = turn.answer_id
                turn.answer_id = None
                return [PetEvent(turn.latest_timestamp, SOURCE, session, kind) for kind in (Kind.final_answer, Kind.task_end)]
            return []
        ts = parse_timestamp(obj.get("timestamp"))
        if ts is None:
            return []
        if ts < turn.latest_timestamp:
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
                turn.prompt_id = next((obj[k] for k in ('promptId', 'uuid') if isinstance(obj.get(k), str) and len(obj[k]) <= 256), 'turn:' + str(ts))
                turn.response_id = None
                turn.response_has_tools = False
                return [ev(kind, detail=prompt_line(text))]

            if isinstance(content, list):
                results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if results:
                    turn.latest_timestamp = ts
                    turn.answer_id = None
                    self._background_result(turn, obj)
                    out = []
                    for b in results:
                        tid = b.get("tool_use_id")
                        if not isinstance(tid, str):
                            continue
                        out.append(ev(Kind.activity_failed if _is_failure(b) else Kind.activity_end, event_id=tid))
                    item = _task_created(obj.get("toolUseResult"))
                    if item:
                        out.append(ev(Kind.todo_update, todos=[item]))
                    return out
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
            if message.get("model") == "<synthetic>":
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
            turn.answer_id = None
            stopped = subtype == 'turn_duration' or (obj.get('preventedContinuation') is False and obj.get('hasOutput') is False
                       and obj.get('hookErrors') == [] and obj.get('hookAdditionalContext') == []
                       and not obj.get('stopReason'))
            if not stopped or turn.pending():
                return [ev(Kind.thinking)]
            turn.completed_answer_id = answer
            return [ev(Kind.final_answer), ev(Kind.task_end)]
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
