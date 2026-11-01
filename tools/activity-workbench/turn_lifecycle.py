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
