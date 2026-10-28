# Local review and inert drafts

Construction source only; runtime, SQLite behavior and isolation have not run.

`DecisionLog(path)` uses SQLite WAL at a caller-selected local state path outside
OneDrive/repositories. `register_finding(finding)` appends a full canonical snapshot
when it differs from the latest snapshot and returns
`{"finding_hash": <SHA-256>, "finding_revision": <positive integer>}`. An unchanged
latest snapshot retains its revision; a change followed by a return to identical
earlier content gets a new immutable revision. Reconcile and register the current finding before every
review/export operation. Dependency hashes must cover source bytes/page text,
shipment facts, contract, fuel, engine/policy and link ruling. These dependencies
are produced by reconciliation, not inferred by the review store. Re-registering
changed content invalidates an old approval even if a producer reused its dependency
hash or later returns to an identical earlier snapshot.

`append(event)` requires request_id, finding_id, dependency_hash, finding_hash,
finding_revision (both returned by register_finding), previous_event_id (None for first intent), action,
actor_id, actor_kind. Actions: accept/dispute/escalate/link. Link also requires
link_target; the caller must rerun linking/reconciliation and register its resulting
closure before further approval. Dispute requires approved_cents equal to the
positive proposed disputed_cents; both values must be strict integer cents, with
booleans and floats refused. Other actions cannot approve money. Note is
optional text. Unknown fields refuse. Event timestamps are assigned by the store.

`latest(finding_id)` returns the latest receipt or None. Exact request replay returns
the original receipt, including after invalidation, and never reauthorizes an old
approval. Reusing a request ID with a changed intent refuses. New intents require
the latest previous-event ID plus matching dependency hash, snapshot hash and
registration revision. Receipts persist that revision, so an old intent cannot
apply after an A-to-B-to-A registration sequence. A writer transaction serializes
CAS and rollback. Events and finding snapshots reject SQL UPDATE/DELETE via
triggers. BEFORE INSERT guards also reject an existing finding revision, decision
event ID or decision request ID, including INSERT OR REPLACE with recursive
triggers disabled. These guards preserve existing rows rather than relying on
REPLACE to fire DELETE triggers. The constructor closes its setup connection even
if schema setup fails. Direct database owners can alter schema/files; this is
not tamperproof storage. Actor IDs/kinds are local assertions, not authentication.
The CLI must use agent_provisional for scripts; actual human classification requires
an actual person. No human sessions/time evidence has been produced.

`export_draft(finding, decision, source_resolver, out_dir, *, decision_log=log)`
requires the actual log; omission fails closed. It rereads current persisted state,
requires the exact latest human dispute receipt bound to the current immutable
registration revision (as well as its hashes), and holds the SQLite writer lock
through source validation and export. Receipt equality compares canonical JSON,
so Python's bool/int/float equality cannot substitute a differently typed receipt.
Approval cents are checked strictly again, and the rendered decision is the
persisted receipt returned under that lock. The CLI owns refreshing dependencies first;
the review module cannot detect unregistered upstream mutations. Export requires
known integer money, positive billed-minus-expected dispute exactly matching the
approval, eligible verdict, no missing facts and nonempty verified evidence. Each
pointer is resolved with `source_resolver.resolve(pointer) -> exact str` or refusal;
DL2 owns byte/span/quote/normalization validation and must include all required
monetary and clause evidence. Failures occur before artifact creation. Output is
deterministic content-addressed escaped HTML, exclusively created, with exact-content
retry checks. It has no scripts, remote assets or sending capability and is labeled
`DRAFT, NOT SENT`. `review.report_html.report_html(findings) -> str` provides an
escaped review listing, explicitly reporting minutes not measured.

Pre-revision receipts remain readable but cannot authorize export or be resubmitted
unchanged through the revision-bearing append contract. Callers must obtain a
current registration and append a new revision-bearing intent with a new request
ID to approve again. Revision-bearing exact retries keep returning their original
receipt, even after later registrations; export independently checks currency.

Deferred activation: SQLite trigger/restart/replay/rollback and concurrent CAS;
INSERT OR REPLACE preservation with recursive triggers disabled; A-to-B-to-A stale
intent and approval refusal, including reopening an existing log;
current dependency refresh across all mutation classes; real human versus scripted
review; stale and modified-number/pointer export refusal, including bool/float
receipt and proposed/approved-cents tampering; exact resolver integration;
HTML injection and socket-denied export; filesystem concurrent export behavior and
caller directory trust. No runtime or product acceptance is claimed.
