"""Append-only SQLite review history with serialized CAS and exact retry."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3


class ReviewError(ValueError):
    """An intent cannot be safely applied to the current finding."""


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ReviewError("value must be finite JSON data") from exc


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ReviewError(f"{label} must be nonempty text")
    return value


def cents(value, label):
    if type(value) is not int or value < 0:
        raise ReviewError(f"{label} must be nonnegative integer cents")
    return value


class DecisionLog:
    """Caller supplies a local state path outside the repo/OneDrive.

    register_finding must be called with freshly reconciled dependency closure
    before decisions/exports. Hashes and actor IDs provide attribution, not auth.
    """

    def __init__(self, path):
        from ..state_policy import validate_state_path
        self.path = str(validate_state_path(path))
        with closing(self._connect()) as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS findings (
                    revision INTEGER PRIMARY KEY AUTOINCREMENT,
                    finding_id TEXT NOT NULL, dependency_hash TEXT NOT NULL,
                    snapshot TEXT NOT NULL, snapshot_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS decisions (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE, intent TEXT NOT NULL,
                    finding_id TEXT NOT NULL, receipt TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS finding_history ON findings(finding_id,revision);
                CREATE INDEX IF NOT EXISTS decision_history ON decisions(finding_id,event_id);
                CREATE TRIGGER IF NOT EXISTS findings_no_replace BEFORE INSERT ON findings
                    WHEN EXISTS (SELECT 1 FROM findings WHERE revision=NEW.revision)
                    BEGIN SELECT RAISE(ABORT,'append-only findings'); END;
                CREATE TRIGGER IF NOT EXISTS decisions_no_replace BEFORE INSERT ON decisions
                    WHEN EXISTS (SELECT 1 FROM decisions
                                 WHERE event_id=NEW.event_id OR request_id=NEW.request_id)
                    BEGIN SELECT RAISE(ABORT,'append-only decisions'); END;
                CREATE TRIGGER IF NOT EXISTS findings_no_update BEFORE UPDATE ON findings
                    BEGIN SELECT RAISE(ABORT,'append-only findings'); END;
                CREATE TRIGGER IF NOT EXISTS findings_no_delete BEFORE DELETE ON findings
                    BEGIN SELECT RAISE(ABORT,'append-only findings'); END;
                CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON decisions
                    BEGIN SELECT RAISE(ABORT,'append-only decisions'); END;
                CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions
                    BEGIN SELECT RAISE(ABORT,'append-only decisions'); END;
            """)
        from .link_log import LinkLog
        self._links = LinkLog(self)

    def register_link_context(self, context):
        return self._links.register(context)

    def refresh_link_contexts(self, contexts):
        return self._links.refresh(contexts)

    def latest_link(self, context_id):
        return self._links.latest(context_id)

    def append_link(self, intent):
        return self._links.append(intent)

    def resolve_link(self, context):
        return self._links.resolve(context)

    def _connect(self):
        db = sqlite3.connect(self.path, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _transaction(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _current(db, finding_id):
        row = db.execute("SELECT * FROM findings WHERE finding_id=? ORDER BY revision DESC LIMIT 1",
                         (finding_id,)).fetchone()
        if row is None:
            raise ReviewError("finding not registered")
        return row

    @staticmethod
    def _latest(db, finding_id):
        row = db.execute("SELECT receipt FROM decisions WHERE finding_id=? ORDER BY event_id DESC LIMIT 1",
                         (finding_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def register_finding(self, finding):
        if type(finding) is not dict:
            raise ReviewError("finding must be a JSON object")
        snapshot = canonical(finding)
        snapshot_hash = digest(finding)
        finding_id = text(finding.get("finding_id"), "finding_id")
        dependency = text(finding.get("dependency_hash"), "dependency_hash")
        with self._transaction() as db:
            row = db.execute("SELECT revision,snapshot_hash FROM findings WHERE finding_id=? ORDER BY revision DESC LIMIT 1",
                             (finding_id,)).fetchone()
            if row is None or row["snapshot_hash"] != snapshot_hash:
                revision = db.execute(
                    "INSERT INTO findings(finding_id,dependency_hash,snapshot,snapshot_hash) VALUES(?,?,?,?)",
                    (finding_id, dependency, snapshot, snapshot_hash)).lastrowid
            else:
                revision = row["revision"]
        return {"finding_hash": snapshot_hash, "finding_revision": revision}

    def latest(self, finding_id):
        with self._transaction() as db:
            return self._latest(db, finding_id)

    def append(self, event):
        if type(event) is not dict:
            raise ReviewError("event must be a JSON object")
        allowed = {"request_id", "finding_id", "dependency_hash", "previous_event_id", "action",
                   "actor_id", "actor_kind", "note", "approved_cents", "finding_hash",
                   "finding_revision", "link_target"}
        if set(event) - allowed:
            raise ReviewError("unknown intent fields")
        intent = canonical(event)  # exact full semantic retry, including note/actor/link
        for key in ("request_id", "finding_id", "dependency_hash", "actor_id", "finding_hash"):
            text(event.get(key), key)
        if type(event.get("finding_revision")) is not int or event["finding_revision"] <= 0:
            raise ReviewError("explicit positive finding_revision required")
        if event.get("actor_kind") not in ("human", "agent_provisional"):
            raise ReviewError("explicit actor_kind required")
        if event.get("action") not in ("accept", "dispute", "escalate", "link"):
            raise ReviewError("invalid action")
        if "previous_event_id" not in event or (event["previous_event_id"] is not None and
                (type(event["previous_event_id"]) is not int or event["previous_event_id"] <= 0)):
            raise ReviewError("explicit previous_event_id required")
        if not isinstance(event.get("note", ""), str):
            raise ReviewError("note must be text")
        if event["action"] == "link":
            text(event.get("link_target"), "link_target")
        with self._transaction() as db:
            replay = db.execute("SELECT intent,receipt FROM decisions WHERE request_id=?",
                                (event["request_id"],)).fetchone()
            if replay:
                if replay["intent"] != intent:
                    raise ReviewError("request_id reused with conflicting intent")
                return json.loads(replay["receipt"])
            current = self._current(db, event["finding_id"])
            if (current["dependency_hash"] != event["dependency_hash"] or
                    current["snapshot_hash"] != event["finding_hash"] or
                    current["revision"] != event["finding_revision"]):
                raise ReviewError("stale finding/dependencies")
            previous = self._latest(db, event["finding_id"])
            if event["previous_event_id"] != (previous["event_id"] if previous else None):
                raise ReviewError("stale or conflicting decision")
            finding = json.loads(current["snapshot"])
            if event["action"] == "dispute":
                amount = cents(event.get("approved_cents"), "approved_cents")
                proposed = cents(finding.get("disputed_cents"), "disputed_cents")
                if amount <= 0 or amount != proposed:
                    raise ReviewError("approval must match positive proposed cents")
            elif event.get("approved_cents") is not None:
                raise ReviewError("only a dispute may carry approved_cents")
            receipt = dict(event, created_at=datetime.now(timezone.utc).isoformat())
            # Row ID is allocated under BEGIN IMMEDIATE; no update is needed.
            event_id = db.execute("SELECT COALESCE(MAX(event_id),0)+1 FROM decisions").fetchone()[0]
            receipt["event_id"] = event_id
            db.execute("INSERT INTO decisions(event_id,request_id,intent,finding_id,receipt) VALUES(?,?,?,?,?)",
                       (event_id, event["request_id"], intent, event["finding_id"], canonical(receipt)))
            return receipt

    @contextmanager
    def authorize_export(self, finding, decision):
        """Hold the writer lock through draft writing to serialize invalidation."""
        if type(finding) is not dict or type(decision) is not dict:
            raise ReviewError("finding and decision must be JSON objects")
        finding_id = text(finding.get("finding_id"), "finding_id")
        decision_json = canonical(decision)
        with self._transaction() as db:
            current = self._current(db, finding_id)
            latest = self._latest(db, finding_id)
            if latest is None or canonical(latest) != decision_json:
                raise ReviewError("export requires exact latest persisted receipt")
            approved = cents(latest.get("approved_cents"), "approved_cents")
            proposed = cents(finding.get("disputed_cents"), "disputed_cents")
            if approved <= 0 or approved != proposed:
                raise ReviewError("approval must match positive proposed cents")
            if (latest["action"] != "dispute" or latest["actor_kind"] != "human" or
                    current["snapshot_hash"] != digest(finding) or
                    latest.get("finding_revision") != current["revision"] or
                    latest["finding_hash"] != current["snapshot_hash"] or
                    latest["dependency_hash"] != current["dependency_hash"]):
                raise ReviewError("current matching human dispute required")
            yield latest
