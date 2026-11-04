"""Observed reply boundaries, independent of tool outcomes or task acceptance."""
MARKERS = ('turn_started', 'turn_ended', 'turn_cancelled')


def turn_marker(row):
    if row.get('kind') in MARKERS:
        return row['kind']
    if row.get('turn_marker') in MARKERS:
        return row['turn_marker']
    # Existing Claude history already retained this structural field. Reading
    # old records needs no migration and must not re-ingest or alter history.
    if row.get('kind') == 'message_observed' and row.get('source_kind') == 'assistant' and row.get('reported_stop_reason') in ('end_turn', 'stop_sequence'):
        if not any(b.get('kind') == 'tool_requested' for b in row.get('blocks', []) if isinstance(b, dict)):
            return 'turn_ended'
    return None


def waiting_request(operations, start, closed, unlinked_receipts=()):
    """Only explicit, still-unanswered requests with unambiguous identity."""
    question_tools = {'askuserquestion', 'ask_user_question', 'request_user_input', 'request_user_input_async'}
    for op in reversed(operations):
        request = op['request']
        if request['sequence'] <= max(start, closed) or op['status'] in ('succeeded', 'failed', 'cancelled', 'conflict', 'unresolved'):
            continue
        if any(r.get('call_id') == request.get('call_id') and r['sequence'] >= request['sequence'] for r in unlinked_receipts):
            continue
        latest = max([request] + op['receipts'], key=lambda r: r['sequence'])
        if latest.get('reported_await_user_response') is True:
            return latest
        tool = request.get('tool_name', '').rsplit('.', 1)[-1].lower()
        # The tool's name is structural metadata, not message-text inference.
        # Any receipt ends this question wait, even when its outcome is unknown.
        if op['status'] == 'no_receipt' and tool in question_tools:
            return request
    return None
