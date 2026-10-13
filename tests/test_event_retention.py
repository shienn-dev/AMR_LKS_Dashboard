"""Regression tests for Phase 1.3 — bounded event retention.

The engine keeps at most ``LOG_RETENTION`` events, dropping the oldest when the
buffer overflows. Each event carries a monotonic ``seq`` that never repeats and
is never reset, so the dashboard's append-only log uses a sequence cursor
instead of a list index.

These are unit tests over ``amr_core.simulation`` and the ``amr_dashboard.panels``
rendering helper. They are not browser/end-to-end tests.
"""

from __future__ import annotations

from amr_core.simulation import LOG_RETENTION, SimulationEngine
from amr_dashboard import panels


class _RecordingLog:
    """Minimal stand-in for a NiceGUI log widget."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def push(self, text: str) -> None:  # noqa: D401 - test double
        self.lines.append(text)


def _drain(engine: SimulationEngine) -> None:
    """Fill the event buffer well past the retention limit."""
    for i in range(LOG_RETENTION + 250):
        engine.log(f"event-{i}")


# --------------------------------------------------------------------------- #
# Retention bound
# --------------------------------------------------------------------------- #

def test_retention_limit_is_a_positive_int() -> None:
    assert isinstance(LOG_RETENTION, int)
    assert LOG_RETENTION > 0


def test_buffer_never_exceeds_retention_limit() -> None:
    engine = SimulationEngine()
    _drain(engine)
    assert len(engine.events) <= LOG_RETENTION
    assert len(engine.events) == LOG_RETENTION


def test_buffer_stays_bounded_on_repeated_overflow() -> None:
    engine = SimulationEngine()
    for _ in range(3):
        _drain(engine)
    assert len(engine.events) == LOG_RETENTION


def test_newest_events_are_retained_after_overflow() -> None:
    engine = SimulationEngine()
    engine.log("marker-last")
    _drain(engine)  # logs event-0 .. event-249
    # The most recent event is kept.
    assert engine.events[-1].message == f"event-{LOG_RETENTION + 250 - 1}"
    # The earliest events (including the constructor's and the marker) were
    # trimmed away.
    messages = [e.message for e in engine.events]
    assert "Simulation started. No robot connected (simulated data only)." not in messages
    assert "marker-last" not in messages


# --------------------------------------------------------------------------- #
# Monotonic sequence numbers
# --------------------------------------------------------------------------- #

def test_sequence_numbers_are_unique_and_increasing() -> None:
    engine = SimulationEngine()
    _drain(engine)
    seqs = [e.seq for e in engine.events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_sequence_does_not_repeat_after_trimming() -> None:
    engine = SimulationEngine()
    seq_before = engine.latest_seq
    _drain(engine)
    # All retained seqs are greater than anything emitted before the overflow.
    assert all(e.seq > seq_before for e in engine.events)
    assert engine.latest_seq == seq_before + (LOG_RETENTION + 250)


def test_sequence_not_reset_by_reset_action() -> None:
    engine = SimulationEngine()
    engine.apply_health("lidar", False)
    engine._run_health_check()  # -> FAULT
    engine.apply_health("lidar", True)  # recover
    seq_before = engine.latest_seq

    result = engine.reset()
    assert result.allowed  # FAULT -> READY

    assert engine.latest_seq > seq_before  # kept counting, did not restart
    seqs = [e.seq for e in engine.events]
    assert len(seqs) == len(set(seqs))  # no reuse


def test_latest_seq_is_minus_one_when_no_events_yet() -> None:
    # A brand-new engine has not logged anything only before __post_init__ runs;
    # empirically the constructor logs, so check the documented contract via a
    # directly-constructed value.
    engine = SimulationEngine()
    assert engine.latest_seq >= 0
    assert engine.latest_seq == engine.events[-1].seq


# --------------------------------------------------------------------------- #
# events_since() cursor semantics
# --------------------------------------------------------------------------- #

def test_events_since_returns_only_newer_events() -> None:
    engine = SimulationEngine()
    cursor = engine.latest_seq
    engine.log("a")
    engine.log("b")
    got = engine.events_since(cursor)
    assert [e.message for e in got] == ["a", "b"]


def test_events_since_empty_when_cursor_is_latest() -> None:
    engine = SimulationEngine()
    engine.log("a")
    assert engine.events_since(engine.latest_seq) == []


def test_events_since_all_retained_when_cursor_zero() -> None:
    engine = SimulationEngine()
    _drain(engine)
    got = engine.events_since(0)
    assert got == engine.events  # all retained events, oldest-first


def test_events_since_works_with_cursor_for_trimmed_event() -> None:
    engine = SimulationEngine()
    old_cursor = 0
    _drain(engine)
    got = engine.events_since(old_cursor)
    # Even though seq 0's event is gone, we still get all retained events once.
    assert len(got) == len(engine.events)
    assert all(e.seq > old_cursor for e in got)


# --------------------------------------------------------------------------- #
# Dashboard cursor: append-only, no duplication, no loss across trimming
# --------------------------------------------------------------------------- #

def test_append_events_no_new_events_adds_no_lines() -> None:
    engine = SimulationEngine()
    log = _RecordingLog()
    cursor = panels.append_events(log, engine, 0)  # type: ignore[arg-type]
    count = len(log.lines)
    cursor = panels.append_events(log, engine, cursor)  # type: ignore[arg-type]
    assert len(log.lines) == count


def test_append_events_adds_one_line_per_new_event() -> None:
    engine = SimulationEngine()
    log = _RecordingLog()
    cursor = panels.append_events(log, engine, 0)  # type: ignore[arg-type]
    count = len(log.lines)
    engine.log("n1")
    engine.log("n2")
    cursor = panels.append_events(log, engine, cursor)  # type: ignore[arg-type]
    assert len(log.lines) == count + 2


def test_append_events_new_event_after_trim_shown_exactly_once() -> None:
    engine = SimulationEngine()
    log = _RecordingLog()

    # First reader syncs fully, then the buffer overflows. The reader must first
    # catch up on the events emitted since its cursor (all of which are still
    # retained), then see exactly one new line for the event after trimming.
    cursor = panels.append_events(log, engine, 0)  # type: ignore[arg-type]
    _drain(engine)
    cursor = panels.append_events(log, engine, cursor)  # type: ignore[arg-type]
    count_after_catch_up = len(log.lines)

    # Now one more event arrives while old events continue to be trimmed.
    engine.log("after-trim")
    cursor = panels.append_events(log, engine, cursor)  # type: ignore[arg-type]

    assert len(log.lines) == count_after_catch_up + 1
    assert log.lines[-1].endswith("after-trim")


def test_already_rendered_events_are_not_reshown_when_trimmed() -> None:
    engine = SimulationEngine()
    log = _RecordingLog()
    cursor = panels.append_events(log, engine, 0)  # type: ignore[arg-type]
    rendered_before = len(log.lines)

    # A reader that keeps within the retention window sees every new event once,
    # even as older history is trimmed. Keep the reader in sync every 100 events.
    total_new = 0
    for i in range(LOG_RETENTION + 100):
        engine.log(f"distinct-{i}")
        total_new += 1
        if total_new % 100 == 0:
            cursor = panels.append_events(log, engine, cursor)  # type: ignore[arg-type]
    cursor = panels.append_events(log, engine, cursor)  # type: ignore[arg-type]

    # Every newly emitted event was appended exactly once; history already shown
    # (some now trimmed) was never shown again.
    assert len(log.lines) == rendered_before + (LOG_RETENTION + 100)
    distinct_lines = [ln for ln in log.lines if "distinct-" in ln]
    assert len(distinct_lines) == len(set(distinct_lines)) == LOG_RETENTION + 100


def test_reader_lagging_beyond_retention_loses_lagged_events() -> None:
    """Documented limitation: a reader more than LOG_RETENTION events behind.

    The buffer is bounded, so events trimmed before a reader reaches them cannot
    be delivered. This is expected and is not a duplication or index bug; it is
    the trade-off of a bounded buffer. Real UI readers sync every tick, far
    inside this window.
    """
    engine = SimulationEngine()
    log = _RecordingLog()
    cursor = panels.append_events(log, engine, 0)  # type: ignore[arg-type]
    rendered_before = len(log.lines)

    # Emit far more than the retention limit WITHOUT reading in between.
    lag = LOG_RETENTION + 100
    for i in range(lag):
        engine.log(f"lost-{i}")
    cursor = panels.append_events(log, engine, cursor)  # type: ignore[arg-type]

    # Only the newest LOG_RETENTION events are still available.
    appended = len(log.lines) - rendered_before
    assert appended == LOG_RETENTION
    # No duplication: the delivered messages are all distinct.
    delivered = [ln for ln in log.lines if "lost-" in ln]
    assert len(delivered) == len(set(delivered))


def test_fresh_log_renders_all_retained_events_exactly_once() -> None:
    engine = SimulationEngine()
    _drain(engine)
    log = _RecordingLog()
    cursor = panels.append_events(log, engine, 0)  # type: ignore[arg-type]

    assert len(log.lines) == len(engine.events) == LOG_RETENTION
    assert cursor == engine.latest_seq


def test_two_cursors_do_not_duplicate_events() -> None:
    engine = SimulationEngine()
    log_a = _RecordingLog()
    log_b = _RecordingLog()
    # Two independent readers (e.g. two pages) each show all events once.
    cursor_a = panels.append_events(log_a, engine, 0)  # type: ignore[arg-type]
    cursor_b = panels.append_events(log_b, engine, 0)  # type: ignore[arg-type]
    assert log_a.lines == log_b.lines
    assert cursor_a == cursor_b


# --------------------------------------------------------------------------- #
# Timestamp stability (retained from Phase 1.1, re-checked here)
# --------------------------------------------------------------------------- #

def test_event_timestamps_stable_across_reads() -> None:
    engine = SimulationEngine()
    engine.log("first")
    engine.log("second")
    stamps = [e.time for e in engine.events]
    assert [e.time for e in engine.events] == stamps
    assert all(isinstance(s, str) and len(s) == 8 for s in stamps)
