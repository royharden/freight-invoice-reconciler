"""Source-bound local link rulings, independent of monetary finding history."""
from contextlib import closing
from datetime import datetime, timezone
import json

from .log import ReviewError, canonical, digest, text


def _context(value):
    keys = {"context_id", "occurrence_id", "carrier", "reference", "dependency_hash"}
    if type(value) is not dict or set(value) != keys:
        raise ReviewError("complete exact link_context required")
    for key in keys - {"reference"}:
        text(value[key], key)
    if not isinstance(value["reference"], str):
        raise ReviewError("reference must be explicit text, possibly empty")
    return json.loads(canonical(value))


class LinkLog:
    """Uses the parent's connection policy; no monetary approvals are consulted."""

    def __init__(self, store):
        self.store = store
        with closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS link_contexts (
                    revision INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id TEXT NOT NULL, snapshot TEXT, context_hash TEXT);
                CREATE TABLE IF NOT EXISTS link_rulings (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE, context_id TEXT NOT NULL,
                    intent TEXT NOT NULL, receipt TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS link_context_history
                    ON link_contexts(context_id,revision);
                CREATE INDEX IF NOT EXISTS link_ruling_history
                    ON link_rulings(context_id,event_id);
                CREATE TRIGGER IF NOT EXISTS link_contexts_no_replace BEFORE INSERT ON link_contexts
                    WHEN EXISTS(SELECT 1 FROM link_contexts WHERE revision=NEW.revision)
                    BEGIN SELECT RAISE(ABORT,'append-only link contexts'); END;
                CREATE TRIGGER IF NOT EXISTS link_rulings_no_replace BEFORE INSERT ON link_rulings
                    WHEN EXISTS(SELECT 1 FROM link_rulings
                                WHERE event_id=NEW.event_id OR request_id=NEW.request_id)
                    BEGIN SELECT RAISE(ABORT,'append-only link rulings'); END;
                CREATE TRIGGER IF NOT EXISTS link_contexts_no_update BEFORE UPDATE ON link_contexts
                    BEGIN SELECT RAISE(ABORT,'append-only link contexts'); END;
                CREATE TRIGGER IF NOT EXISTS link_contexts_no_delete BEFORE DELETE ON link_contexts
                    BEGIN SELECT RAISE(ABORT,'append-only link contexts'); END;
                CREATE TRIGGER IF NOT EXISTS link_rulings_no_update BEFORE UPDATE ON link_rulings
                    BEGIN SELECT RAISE(ABORT,'append-only link rulings'); END;
                CREATE TRIGGER IF NOT EXISTS link_rulings_no_delete BEFORE DELETE ON link_rulings
                    BEGIN SELECT RAISE(ABORT,'append-only link rulings'); END;
            """)

    @staticmethod
    def _current(db, context_id):
        return db.execute("SELECT * FROM link_contexts WHERE context_id=? ORDER BY revision DESC LIMIT 1",
                          (context_id,)).fetchone()

    @staticmethod
    def _latest(db, context_id):
        row = db.execute("SELECT receipt FROM link_rulings WHERE context_id=? ORDER BY event_id DESC LIMIT 1",
                         (context_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _register(self, db, context):
        context_id = context["context_id"]
        snapshot = canonical(context)
        context_hash = digest(context)
        current = self._current(db, context_id)
        if current is not None and current["snapshot"] == snapshot:
            revision = current["revision"]
        else:
            revision = db.execute(
                "INSERT INTO link_contexts(context_id,snapshot,context_hash) VALUES(?,?,?)",
                (context_id, snapshot, context_hash)).lastrowid
        return {"context_hash": context_hash, "context_revision": revision}

    def register(self, context):
        context = _context(context)
        with self.store._transaction() as db:
            return self._register(db, context)

    def refresh(self, contexts):
        """Refresh the complete current batch, including retiring absent contexts.

        Use one state database per active input workspace. An empty complete batch
        retires every current context; no missing/default context can authorize.
        """
        if type(contexts) is not list:
            raise ReviewError("complete link context list required")
        validated = [_context(context) for context in contexts]
        ids = [context["context_id"] for context in validated]
        if len(ids) != len(set(ids)):
            raise ReviewError("duplicate link context_id")
        with self.store._transaction() as db:
            current = db.execute("""SELECT c.context_id,c.snapshot FROM link_contexts c
                WHERE c.revision=(SELECT MAX(h.revision) FROM link_contexts h
                                  WHERE h.context_id=c.context_id)""").fetchall()
            active = set(ids)
            for row in current:
                if row["context_id"] not in active and row["snapshot"] is not None:
                    db.execute("INSERT INTO link_contexts(context_id,snapshot,context_hash) VALUES(?,NULL,NULL)",
                               (row["context_id"],))
            return {context["context_id"]: self._register(db, context) for context in validated}

    def latest(self, context_id):
        text(context_id, "context_id")
        with self.store._transaction() as db:
            return self._latest(db, context_id)

    def append(self, intent):
        required = {"request_id", "context_id", "context_hash", "context_revision",
                    "previous_event_id", "action", "actor_id", "actor_kind"}
        optional = {"note", "target_shipment_id"}
        if type(intent) is not dict or not required <= set(intent) or set(intent) - required - optional:
            raise ReviewError("complete exact link intent required")
        encoded = canonical(intent)
        intent = json.loads(encoded)
        for key in ("request_id", "context_id", "context_hash", "actor_id"):
            text(intent[key], key)
        if type(intent["context_revision"]) is not int or intent["context_revision"] <= 0:
            raise ReviewError("positive integer context_revision required")
        previous = intent["previous_event_id"]
        if previous is not None and (type(previous) is not int or previous <= 0):
            raise ReviewError("previous_event_id must be null or positive integer")
        if intent["actor_kind"] not in ("human", "agent_provisional"):
            raise ReviewError("explicit actor_kind required")
        if intent["action"] not in ("link", "unlink"):
            raise ReviewError("link or unlink required")
        if not isinstance(intent.get("note", ""), str):
            raise ReviewError("note must be text")
        if intent["action"] == "link":
            text(intent.get("target_shipment_id"), "target_shipment_id")
        elif "target_shipment_id" in intent:
            raise ReviewError("unlink cannot supply target_shipment_id")
        with self.store._transaction() as db:
            replay = db.execute("SELECT intent,receipt FROM link_rulings WHERE request_id=?",
                                (intent["request_id"],)).fetchone()
            if replay:
                if replay["intent"] != encoded:
                    raise ReviewError("link request_id reused with conflicting intent")
                return json.loads(replay["receipt"])
            current = self._current(db, intent["context_id"])
            if (current is None or current["snapshot"] is None or
                    current["context_hash"] != intent["context_hash"] or
                    current["revision"] != intent["context_revision"]):
                raise ReviewError("stale or absent link context")
            latest = self._latest(db, intent["context_id"])
            if previous != (latest["event_id"] if latest else None):
                raise ReviewError("stale or conflicting link ruling")
            event_id = db.execute("SELECT COALESCE(MAX(event_id),0)+1 FROM link_rulings").fetchone()[0]
            receipt = dict(intent, event_id=event_id, created_at=datetime.now(timezone.utc).isoformat())
            db.execute("INSERT INTO link_rulings(event_id,request_id,context_id,intent,receipt) VALUES(?,?,?,?,?)",
                       (event_id, intent["request_id"], intent["context_id"], encoded, canonical(receipt)))
            return receipt

    def resolve(self, context):
        context = _context(context)
        with self.store._transaction() as db:
            current = self._current(db, context["context_id"])
            if current is None or current["snapshot"] != canonical(context):
                return None
            latest = self._latest(db, context["context_id"])
            if (latest is None or latest["action"] != "link" or
                    latest["actor_kind"] != "human" or
                    latest["context_hash"] != current["context_hash"] or
                    latest["context_revision"] != current["revision"]):
                return None
            return text(latest["target_shipment_id"], "target_shipment_id")
