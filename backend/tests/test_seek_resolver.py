import pytest

def resolve_seek_time(item: dict) -> float | None:
    """
    Python mirror of frontend resolveSeekTime resolver.
    Resolves the exact playback seek timestamp in seconds for an action item or decision.
    Returns None if no timestamp or source segment exists, and never raises an exception.
    """
    if not isinstance(item, dict):
        return None

    # 1. Direct start_time_sec
    sec = item.get("start_time_sec")
    if sec is not None:
        try:
            return float(sec)
        except (ValueError, TypeError):
            pass

    # 2. Fallback start_time
    st = item.get("start_time")
    if st is not None:
        try:
            return float(st)
        except (ValueError, TypeError):
            pass

    # 3. Source segment ID lookup
    seg_id = item.get("source_segment_id")
    transcripts = item.get("transcripts")
    if seg_id is not None and isinstance(transcripts, list):
        for seg in transcripts:
            if isinstance(seg, dict) and seg.get("id") == seg_id:
                t_val = seg.get("start_time") or seg.get("start")
                if t_val is not None:
                    try:
                        return float(t_val)
                    except (ValueError, TypeError):
                        pass

    return None


def test_resolve_seek_time_direct_start_time_sec():
    item = {"title": "Submit PR", "start_time_sec": 42.5}
    assert resolve_seek_time(item) == 42.5


def test_resolve_seek_time_fallback_start_time():
    item = {"title": "Update Docs", "start_time": 18.0}
    assert resolve_seek_time(item) == 18.0


def test_resolve_seek_time_source_segment_id():
    transcripts = [
        {"id": 1, "speaker": "Alice", "start_time": 5.0, "text": "Intro"},
        {"id": 2, "speaker": "Bob", "start_time": 25.4, "text": "We decided to migrate DB"},
    ]
    item = {"decision_text": "Migrate DB", "source_segment_id": 2, "transcripts": transcripts}
    assert resolve_seek_time(item) == 25.4


def test_resolve_seek_time_no_timestamp_does_not_throw():
    # Item with no timestamp or segment should return None safely and not throw
    item = {"title": "Unscheduled Task", "assignee": "Sarah"}
    assert resolve_seek_time(item) is None

    empty_item = {}
    assert resolve_seek_time(empty_item) is None

    none_item = None
    assert resolve_seek_time(none_item) is None


def test_resolve_seek_time_invalid_types_do_not_throw():
    corrupt_item = {"start_time_sec": "not_a_number", "source_segment_id": 99, "transcripts": []}
    assert resolve_seek_time(corrupt_item) is None

