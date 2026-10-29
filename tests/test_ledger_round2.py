"""Builder-owned real SQLite origin controls, never paid-call or independence evidence."""

from copy import deepcopy
import sqlite3

import pytest

from freightrec.ledger import Ledger


def event(request_id="builder-request"):
    return dict(request_id=request_id, run_id="builder-run", span_id="builder-span",
                request={"carrier": "BUILDER-CARRIER", "text": "original builder slice"},
                status="ok", elapsed_ms=3, usage=None, original_capture_cost_cents=None)


def test_ledger_restart_retry_and_origin_attribution(tmp_path):
    """what_bug_this_catches: replay across restart must preserve receipt and unknown historical cost."""
    path = tmp_path / "origin.sqlite"
    with Ledger(path) as ledger:
        first = ledger.record_mock(**event())
        nonmodel = ledger.record_nonmodel(**event("nonmodel-request"))
    with Ledger(path) as ledger:
        assert ledger.record_mock(**event()) == first
        assert ledger.connection.execute("SELECT COUNT(*) FROM origin_events").fetchone()[0] == 2
    assert first["origin"] == "mock" and nonmodel["origin"] == "nonmodel"
    assert first["current_external_cost_cents"] == 0
    assert first["original_capture_cost_cents"] is None and first["usage"] is None
    assert "request" not in first and len(first["request_hash"]) == 64


@pytest.mark.parametrize("changed", ["request", "origin", "status", "elapsed", "capture"])
def test_request_id_conflict_never_rewrites_original(tmp_path, changed):
    """what_bug_this_catches: request IDs cannot relabel origin, payload, cost or outcome on retry."""
    with Ledger(tmp_path / "conflict.sqlite") as ledger:
        first = ledger.record_mock(**event())
        altered = event()
        if changed == "request":
            altered["request"] = {"carrier": "OTHER"}
        elif changed == "status":
            altered["status"] = "failed"
        elif changed == "elapsed":
            altered["elapsed_ms"] = 4
        elif changed == "capture":
            altered["original_capture_cost_cents"] = 1
        call = ledger.record_nonmodel if changed == "origin" else ledger.record_mock
        with pytest.raises(ValueError, match="conflicts"):
            call(**altered)
        assert ledger.record_mock(**event()) == first
        assert ledger.connection.execute("SELECT COUNT(*) FROM origin_events").fetchone()[0] == 1


@pytest.mark.parametrize("statement", [
    "UPDATE origin_events SET payload='changed'",
    "DELETE FROM origin_events",
    "INSERT OR REPLACE INTO origin_events(request_id,payload,payload_hash) VALUES('builder-request','changed','changed')",
    "INSERT OR REPLACE INTO origin_events(rowid,request_id,payload,payload_hash) VALUES(1,'new-request','changed','changed')",
])
def test_sql_replacement_and_mutation_guards_preserve_receipt(tmp_path, statement):
    """what_bug_this_catches: SQLite REPLACE can delete an existing row through either request ID or rowid."""
    with Ledger(tmp_path / "immutable.sqlite") as ledger:
        ledger.record_mock(**event())
        original = ledger.connection.execute("SELECT rowid,* FROM origin_events").fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            ledger.connection.execute(statement)
        assert ledger.connection.execute("SELECT rowid,* FROM origin_events").fetchall() == original


def test_failed_insert_rolls_back_and_connection_can_record_next_request(tmp_path):
    """what_bug_this_catches: failed writes must release the transaction without losing prior events."""
    with Ledger(tmp_path / "rollback.sqlite") as ledger:
        ledger.record_mock(**event())
        ledger.connection.execute("""CREATE TRIGGER builder_reject BEFORE INSERT ON origin_events
            WHEN NEW.request_id='reject' BEGIN SELECT RAISE(ABORT,'builder rejection'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="builder rejection"):
            ledger.record_mock(**event("reject"))
        assert not ledger.connection.in_transaction
        assert ledger.record_nonmodel(**event("after-rejection"))["origin"] == "nonmodel"
        assert ledger.connection.execute("SELECT COUNT(*) FROM origin_events").fetchone()[0] == 2


@pytest.mark.parametrize("patch", [
    {"elapsed_ms": True}, {"elapsed_ms": -1}, {"usage": {"tokens": True}},
    {"usage": {"tokens": -1}}, {"original_capture_cost_cents": 1.5},
    {"request": {"value": float("nan")}}, {"current_external_cost_cents": 1},
])
def test_invalid_usage_cost_or_nonfinite_request_leaves_no_event(tmp_path, patch):
    """what_bug_this_catches: malformed or invented paid accounting must not become a durable zero-cost receipt."""
    with Ledger(tmp_path / "invalid.sqlite") as ledger:
        attempt = deepcopy(event())
        attempt.update(patch)
        with pytest.raises(ValueError):
            ledger.record_mock(**attempt)
        assert ledger.connection.execute("SELECT COUNT(*) FROM origin_events").fetchone()[0] == 0


@pytest.mark.parametrize("bad_path", ["relative.sqlite", ":memory:", "file:builder.sqlite?mode=memory",
                                     r"C:\OneDrive\builder.sqlite"])
def test_state_location_refused_before_sqlite_open(monkeypatch, bad_path):
    """what_bug_this_catches: a SQLite consumer must use shared state policy before opening any database."""
    def forbidden(*args, **kwargs):
        raise AssertionError("SQLite opened before path validation")
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    with pytest.raises(ValueError):
        Ledger(bad_path)
