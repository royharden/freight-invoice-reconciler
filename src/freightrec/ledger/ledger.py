"""Append-only origin attribution. This ledger cannot fund or dispatch calls."""

import hashlib
import json
import sqlite3
from pathlib import Path


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path, isolation_level=None)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA recursive_triggers=ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS origin_events (
                request_id TEXT PRIMARY KEY, payload TEXT NOT NULL, payload_hash TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS immutable_origin_insert
              BEFORE INSERT ON origin_events
              WHEN EXISTS (SELECT 1 FROM origin_events WHERE request_id=NEW.request_id)
              BEGIN SELECT RAISE(ABORT,'append only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_origin_rowid_insert
              BEFORE INSERT ON origin_events
              WHEN EXISTS (SELECT 1 FROM origin_events WHERE rowid=NEW.rowid)
              BEGIN SELECT RAISE(ABORT,'append only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_origin_update
              BEFORE UPDATE ON origin_events BEGIN SELECT RAISE(ABORT,'append only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_origin_delete
              BEFORE DELETE ON origin_events BEGIN SELECT RAISE(ABORT,'append only'); END;
        """)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def record_nonmodel(self, **event) -> dict:
        return self._record("nonmodel", event)

    def record_mock(self, **event) -> dict:
        return self._record("mock", event)

    def _record(self, origin: str, event: dict) -> dict:
        allowed = {"request_id", "run_id", "span_id", "request", "status", "elapsed_ms", "usage",
                   "original_capture_cost_cents"}
        if set(event) - allowed:
            raise ValueError("unsupported ledger fields")
        for key in ("request_id", "run_id", "span_id", "status"):
            if not isinstance(event.get(key), str) or not event[key].strip():
                raise ValueError(f"missing {key}")
        elapsed = event.get("elapsed_ms")
        if elapsed is not None and (type(elapsed) is not int or elapsed < 0):
            raise ValueError("elapsed_ms must be nonnegative integer or null")
        usage = event.get("usage")
        if usage is not None and (not isinstance(usage, dict) or any(
                type(n) is not int or n < 0 for n in usage.values())):
            raise ValueError("usage must be nonnegative counts or null")
        capture = event.get("original_capture_cost_cents")
        if capture is not None and (type(capture) is not int or capture < 0):
            raise ValueError("unknown capture cost is null")
        request = event.get("request")
        if not isinstance(request, dict):
            raise ValueError("request payload required for hash binding")
        payload = {key: event[key] for key in ("request_id", "run_id", "span_id", "status")}
        payload.update(origin=origin, request_hash=hashlib.sha256(_canonical(request).encode()).hexdigest(),
                       elapsed_ms=elapsed, usage=usage, current_external_cost_cents=0,
                       original_capture_cost_cents=capture)
        encoded = _canonical(payload)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            existing = self.connection.execute(
                "SELECT payload, payload_hash FROM origin_events WHERE request_id=?", (event["request_id"],)
            ).fetchone()
            if existing:
                if existing[1] != digest:
                    raise ValueError("request_id conflicts with previous origin event")
                self.connection.commit()
                return json.loads(existing[0])
            self.connection.execute("INSERT INTO origin_events VALUES (?,?,?)",
                                    (event["request_id"], encoded, digest))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise
        return payload
