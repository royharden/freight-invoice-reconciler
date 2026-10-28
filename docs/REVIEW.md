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

## Source-bound manual links

Link history is separate from finding/monetary history. DecisionLog exposes
register_link_context(context), latest_link(context_id), append_link(intent),
resolve_link(context). The bounded link_context object has exactly context_id,
occurrence_id, carrier, reference, dependency_hash. All are nonempty text except
reference, which may be an explicitly supplied empty string. No missing field,
default context, null reference or extra field is accepted. Namespace normalization
and original evidence validation belong to reconciliation; storage never guesses.

register_link_context returns {context_hash,context_revision}. An unchanged latest
context keeps its revision; change-and-revert creates a new revision. Link intents
require request_id, context_id, context_hash, context_revision, previous_event_id
(null or latest link event ID), action (link|unlink), actor_id, actor_kind. Optional
note is text. Link requires nonempty target_shipment_id; unlink must omit it.
Unknown fields refuse. CAS, exact canonical replay, conflicting request refusal,
and update/delete/replacement protections mirror the monetary store on independent
link_contexts/link_rulings tables. Request and event IDs are local to link history.
Historical exact replay returns its original receipt and never restores authority.

resolve_link only returns the latest HUMAN link target for the exact currently
registered context/hash/revision. Missing, retired, changed, unlinked or provisional
rulings return no target. Malformed contexts refuse. A later provisional event also
blocks an earlier human link. Local actor kind is attribution only, not proof of
human identity. Link records never authorize a dispute or draft; DL2 must uniquely
validate a returned target against current original shipments in the same carrier
namespace, preserve exact auto-link priority, and bind any applied target to final
finding dependency. Legacy action=link monetary-history events are retained but
are not consulted for resolution.

### Complete refresh and disappearance

The four single-context methods cannot observe that a context disappeared or lost
provenance. The CLI must additionally use refresh_link_contexts(contexts), passing
the COMPLETE list of actionable baseline contexts from the current original batch,
including exact auto-linked occurrences. This atomic helper registers present
contexts, appends null-snapshot tombstone revisions for absent contexts, and returns
{context_id: {context_hash,context_revision}}. Empty list explicitly retires all;
malformed/duplicate lists refuse before writing. Use one state database per active
input workspace/batch scope. A subset is not a complete refresh. If baseline input
validation refuses entirely, the caller must retire the set with an explicit empty
refresh before refusing the command; it must never resolve links on that input.
Returning after an absent/invalid-source interval requires a fresh human ruling.

CLI order: hydrate original sources; reconcile without manual links; complete
refresh; reconcile with log.resolve_link; register FINAL findings only. Preparing
link emits context binding plus latest_link event CAS; submitting intent preserves
all caller tokens. No baseline/final alternating monetary registrations. This
additional batch seam is necessary to prevent absent-to-present approval revival.
Caller source refresh is still required; storage cannot see unreported changes.

Deferred link validation: schema migration/restart, direct replacement/update/delete
refusal, exact retries and conflicting requests, A-B-A/absence/reappearance, explicit
unlink and later provisional denial, concurrent CAS/refresh/resolve, full joined
CLI callback/namespace/auto-link behavior and source/target mutation invalidation.
Only source construction/static review is authorized; no human session observed.
