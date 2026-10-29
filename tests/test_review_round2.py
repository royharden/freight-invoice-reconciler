"""Builder regressions only: human labels exercise attribution branches, not people.

what_bug_this_catches notes name the invariant each adversarial journey protects.
Run with a NEW pytest basetemp outside source/OneDrive; no live effects.
"""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from freightrec.dispute.draft import export_draft
from freightrec.review.log import DecisionLog, ReviewError
from freightrec.review.report_html import report_html
from freightrec.sources.registry import SourceResolver


@pytest.fixture
def log(tmp_path):
    return DecisionLog(tmp_path / "builder-review.db")


def finding(**changes):
    value = {"finding_id": "builder-finding", "occurrence_id": "builder-occurrence",
             "dependency_hash": "builder-original-A", "billed_cents": 1200,
             "expected_cents": 1000, "disputed_cents": 200, "verdict": "overcharge",
             "clause_id": "builder-clause", "missing_facts": [], "evidence_pointers": []}
    return dict(value, **changes)


def decision(log, value, request="builder-money", previous=None, **changes):
    binding = log.register_finding(value)
    event = dict(request_id=request, finding_id=value["finding_id"],
                 dependency_hash=value["dependency_hash"], **binding,
                 previous_event_id=previous, action="dispute", actor_id="builder-attribution-vector",
                 actor_kind="human", approved_cents=value["disputed_cents"])
    return dict(event, **changes)


def context(**changes):
    return dict({"context_id": "builder-context", "occurrence_id": "builder-occurrence",
                 "carrier": "INVENTED", "reference": "TYPO", "dependency_hash": "original-A"},
                **changes)


def link_intent(log, value, request="builder-link", previous=None, **changes):
    binding = log.register_link_context(value)
    event = dict(request_id=request, context_id=value["context_id"], **binding,
                 previous_event_id=previous, action="link", target_shipment_id="builder-shipment",
                 actor_id="builder-attribution-vector", actor_kind="human")
    return dict(event, **changes)


def test_money_restart_exact_replay_and_conflict(log):
    """what_bug_this_catches: retries duplicate events or silently change intent."""
    event = decision(log, finding())
    receipt = log.append(event)
    reopened = DecisionLog(log.path)
    assert reopened.append(event) == receipt == reopened.latest("builder-finding")
    with pytest.raises(ReviewError, match="conflicting intent"):
        reopened.append(dict(event, note="different intent"))


def test_constructor_validates_before_any_sqlite_open(tmp_path, monkeypatch):
    """what_bug_this_catches: a SQLite file is created before policy refusal."""
    calls = []

    def refuse(path):
        calls.append(path)
        raise ValueError("builder policy refusal")

    def unexpected_open(*args, **kwargs):
        pytest.fail("SQLite opened before state validation")

    monkeypatch.setattr("freightrec.state_policy.validate_state_path", refuse)
    monkeypatch.setattr("sqlite3.connect", unexpected_open)
    candidate = tmp_path / "should-not-exist.db"
    with pytest.raises(ValueError, match="builder policy refusal"):
        DecisionLog(candidate)
    assert calls == [candidate] and not candidate.exists()


@pytest.mark.parametrize("amount", [None, True, 200.0, -1, 0])
def test_approval_requires_strict_positive_proposed_cents(log, amount):
    """what_bug_this_catches: unknown/bool/float/zero proposals gain approval."""
    event = decision(log, finding(disputed_cents=amount))
    with pytest.raises(ReviewError):
        log.append(event)
    assert log.latest("builder-finding") is None


def test_money_change_revert_never_revives_approval(log):
    """what_bug_this_catches: hash-only A-B-A revives old monetary approval."""
    original = finding()
    event = decision(log, original)
    receipt = log.append(event)
    log.register_finding(finding(dependency_hash="changed-source"))
    rebound = log.register_finding(original)
    assert rebound["finding_revision"] > event["finding_revision"]
    assert log.append(event) == receipt  # history replay is not renewed authority
    with pytest.raises(ReviewError, match="current matching"):
        with log.authorize_export(original, receipt):
            pytest.fail("stale approval entered export")
    with pytest.raises(ReviewError, match="stale finding"):
        log.append(dict(event, request_id="new-request"))


@pytest.mark.parametrize("field,value", [("approved_cents", 200.0), ("event_id", True),
                                         ("finding_revision", 1.0)])
def test_export_rejects_numeric_receipt_substitution(log, field, value):
    """what_bug_this_catches: Python equality treats int/float/bool as exact receipts."""
    item = finding()
    receipt = log.append(decision(log, item))
    with pytest.raises(ReviewError, match="exact latest"):
        with log.authorize_export(item, dict(receipt, **{field: value})):
            pytest.fail("modified receipt accepted")


@pytest.mark.parametrize("kind", ["money", "link"])
def test_concurrent_cas_has_one_winner(log, kind):
    """what_bug_this_catches: two concurrent intents both spend the same CAS token."""
    if kind == "money":
        event, append = decision(log, finding()), log.append
    else:
        event, append = link_intent(log, context()), log.append_link
    barrier = Barrier(2)

    def submit(index):
        barrier.wait(timeout=10)
        try:
            return append(dict(event, request_id=f"builder-race-{index}"))
        except ReviewError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sum(result is not None for result in results) == 1


def test_sql_abort_rolls_back_and_connection_recovers(log):
    """what_bug_this_catches: failed commit leaves a receipt or held writer lock."""
    event = decision(log, finding(), request="builder-abort")
    with sqlite3.connect(log.path, isolation_level=None) as db:
        db.execute("""CREATE TRIGGER builder_abort AFTER INSERT ON decisions
            WHEN NEW.request_id='builder-abort' BEGIN SELECT RAISE(ABORT,'builder rollback'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="builder rollback"):
        log.append(event)
    assert DecisionLog(log.path).latest("builder-finding") is None
    assert log.append(dict(event, request_id="builder-recovered"))["event_id"] == 1


@pytest.mark.parametrize("table", ["findings", "decisions", "link_contexts", "link_rulings"])
@pytest.mark.parametrize("operation", ["update", "delete", "replace"])
def test_direct_sql_append_only_guards(log, table, operation):
    """what_bug_this_catches: REPLACE deletes history with recursive triggers OFF."""
    log.append(decision(log, finding()))
    log.append_link(link_intent(log, context()))
    with sqlite3.connect(log.path, isolation_level=None) as db:
        db.execute("PRAGMA recursive_triggers=OFF")
        before = db.execute(f"SELECT * FROM {table}").fetchall()
        sql = {"update": f"UPDATE {table} SET {'finding_id' if table in ('findings', 'decisions') else 'context_id'}='changed'",
               "delete": f"DELETE FROM {table}",
               "replace": f"INSERT OR REPLACE INTO {table} SELECT * FROM {table} LIMIT 1"}[operation]
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(sql)
        assert db.execute(f"SELECT * FROM {table}").fetchall() == before


@pytest.mark.parametrize("table", ["decisions", "link_rulings"])
def test_replace_by_request_id_without_primary_key_collision(log, table):
    """what_bug_this_catches: request unique-key replacement bypasses PK guard."""
    log.append(decision(log, finding()))
    log.append_link(link_intent(log, context()))
    with sqlite3.connect(log.path, isolation_level=None) as db:
        db.execute("PRAGMA recursive_triggers=OFF")
        columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
        row = list(db.execute(f"SELECT * FROM {table}").fetchone())
        row[0] += 100
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in row)})", row)
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1


def test_link_replay_unlink_provisional_and_stale_cas(log):
    """what_bug_this_catches: a revoked/provisional latest ruling leaks old target."""
    item = context()
    event = link_intent(log, item)
    first = log.append_link(event)
    assert DecisionLog(log.path).resolve_link(item) == "builder-shipment"
    assert log.append_link(event) == first
    with pytest.raises(ReviewError, match="conflicting intent"):
        log.append_link(dict(event, target_shipment_id="other"))
    unlink = dict(event, request_id="builder-unlink", action="unlink", previous_event_id=first["event_id"])
    unlink.pop("target_shipment_id")
    revoked = log.append_link(unlink)
    assert log.resolve_link(item) is None
    with pytest.raises(ReviewError, match="stale or conflicting"):
        log.append_link(dict(event, request_id="builder-stale"))
    log.append_link(dict(event, request_id="builder-provisional", actor_kind="agent_provisional",
                         previous_event_id=revoked["event_id"]))
    assert log.resolve_link(item) is None
    assert log.latest("builder-finding") is None  # linking creates no money authority


@pytest.mark.parametrize("transition", ["changed", "empty", "disappeared"])
def test_link_refresh_change_or_absence_and_reappearance(log, transition):
    """what_bug_this_catches: complete refresh loses change/exact/absent transitions."""
    a = context()
    event = link_intent(log, a)
    receipt = log.append_link(event)
    if transition == "changed":
        log.refresh_link_contexts([context(reference="NOWEXACT", dependency_hash="original-B")])
    elif transition == "empty":
        log.refresh_link_contexts([])
    else:
        log.refresh_link_contexts([context(context_id="other-valid-occurrence")])
    assert log.resolve_link(a) is None
    rebound = log.refresh_link_contexts([a])[a["context_id"]]
    assert rebound["context_revision"] > event["context_revision"]
    assert log.append_link(event) == receipt
    assert DecisionLog(log.path).resolve_link(a) is None
    with pytest.raises(ReviewError, match="stale or absent"):
        log.append_link(dict(event, request_id="builder-stale-revert"))


def test_invalid_complete_refresh_never_partially_applies(log):
    """what_bug_this_catches: malformed batch partially retires or registers contexts."""
    a = context()
    binding = log.refresh_link_contexts([a])
    for invalid in ([a, a], [context(dependency_hash="B"), {}], None):
        with pytest.raises(ReviewError):
            log.refresh_link_contexts(invalid)
        assert log.register_link_context(a) == binding[a["context_id"]]
    for invalid in ({}, None, dict(a, reference=None)):
        with pytest.raises(ReviewError):
            log.resolve_link(invalid)
    assert log.resolve_link(context(context_id="unregistered")) is None


@pytest.fixture
def draft_case(log):
    resolver = SourceResolver()
    quote = 'Invoice 12.00 <script>fetch("https://evil.invalid")</script> café'
    source = resolver.register_text(quote.encode("utf-8"))
    pointer = resolver.pointer(source, 0, 0, len(quote))
    value = finding(evidence_pointers=[pointer.to_dict()])
    receipt = log.append(decision(log, value))
    return value, receipt, resolver, pointer


def test_draft_escaped_inert_exact_retry_and_existing_artifact_refusal(log, draft_case, tmp_path, monkeypatch):
    """what_bug_this_catches: untrusted quotes execute or retry overwrites a draft."""
    item, receipt, resolver, _ = draft_case
    def deny_network(*args, **kwargs):
        pytest.fail("inert export attempted a socket")
    monkeypatch.setattr("socket.socket", deny_network)
    monkeypatch.setattr("socket.create_connection", deny_network)
    path = export_draft(item, receipt, resolver, tmp_path / "drafts", decision_log=log)
    original = path.read_bytes()
    html = original.decode("utf-8")
    assert "DRAFT, NOT SENT" in html and "minutes not measured" in html
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "<script" not in report_html([item])
    assert 'src="' not in html and 'href="' not in html
    assert export_draft(item, receipt, resolver, path.parent, decision_log=log) == path
    assert path.read_bytes() == original
    path.write_text("builder preexisting altered artifact", encoding="utf-8")
    with pytest.raises(ReviewError, match="existing draft content mismatch"):
        export_draft(item, receipt, resolver, path.parent, decision_log=log)
    assert path.read_text(encoding="utf-8") == "builder preexisting altered artifact"


@pytest.mark.parametrize("mutation", ["amount", "pointer", "provisional", "missing", "no-log"])
def test_draft_refuses_mutations_and_unapproved_actions(log, draft_case, tmp_path, mutation):
    """what_bug_this_catches: modified money/source or provisional intent reaches disk."""
    item, receipt, resolver, pointer = draft_case
    if mutation == "amount":
        item = dict(item, billed_cents=1201)
    elif mutation == "pointer":
        item = dict(item, evidence_pointers=[replace(pointer, quote_sha256="0" * 64).to_dict()])
        receipt = log.append(decision(log, item, request="builder-bad-pointer", previous=receipt["event_id"]))
    elif mutation == "provisional":
        receipt = log.append(decision(log, item, request="builder-script", previous=receipt["event_id"],
                                      actor_kind="agent_provisional"))
    elif mutation == "missing":
        item = dict(item, missing_facts=["builder-unknown"])
        receipt = log.append(decision(log, item, request="builder-missing", previous=receipt["event_id"]))
    with pytest.raises(ValueError):
        export_draft(item, receipt, resolver, tmp_path / "refused",
                     decision_log=None if mutation == "no-log" else log)
    assert not (tmp_path / "refused").exists()


def test_review_draft_source_has_no_outbound_effect_imports():
    """what_bug_this_catches: adding a dispatcher/provider import to export closure."""
    package = Path(__file__).resolve().parents[1] / "src" / "freightrec"
    allowed = {"contextlib", "datetime", "hashlib", "json", "sqlite3", "html", "pathlib"}
    for folder in ("review", "dispute"):
        for path in (package / folder).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    assert {alias.name for alias in node.names} <= allowed
                elif isinstance(node, ast.ImportFrom):
                    assert node.level > 0 or node.module in allowed
