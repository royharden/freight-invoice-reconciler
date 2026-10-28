# Local construction CLI

Source only: none of these commands has been executed. Python 3.12+ is intended.
After a separately authorized installation, `freightrec status` reports pending
admission, runtime unverified, A3 not_run and A4 not_run_guardrail.
`--live` anywhere refuses before input reads or provider imports.

Construction input is a JSON object with `data_origin: builder_non_independent`,
required `contracts`, `shipments`, `invoices` and `fuel_index` arrays, and optional
`tolerance_cents` (0, 50 or 100; default 0). Every array item must be a string
containing one complete original JSON fact document. Preserve its exact
whitespace, key order, newlines and string contents when embedding it in the
outer bundle; the CLI encodes those decoded string contents directly as UTF-8.

The CLI calls `SourceResolver.register_document` on those exact bytes once per
document. It passes the resulting bound documents and that same resolver to
reconciliation, and retains the resolver for draft evidence resolution.
Original documents must contain facts only: duplicate keys, floating point
numbers, nonfinite numbers and reserved provenance metadata (`source_sha256`,
`evidence_pointers`, `field_values`) refuse. Decimal quantities use strings.
Preparsed dictionaries, metadata-bound documents and the former separate
`sources` bundle field refuse; do not serialize derived values to manufacture
original evidence. Native PDF ingest is a separate operation, and this
structured-JSON construction path does not claim PDF provenance.

Future keyless construction use:

```
freightrec reconcile --builder-only --input bundle.json --out findings.json
freightrec demo --builder-only --input bundle.json --out demonstration.json
freightrec report --builder-only --input bundle.json --out review.html
```

All three call actual reconcile_batch; demo is a labeled construction path and
produces no benchmark score. Pass the same optional --state to include persisted
human link rulings in these outputs. Without --state, they show exact automatic
links only. Outputs use exclusive creation to preserve prior artifacts. Without
--builder-only, commands refuse pending admission.

Prepare a manual link for a provenance-valid occurrence whose exact automatic
link failed (obtain occurrence_id from the findings):

```
freightrec prepare-link --builder-only --input bundle.json --state C:\local-state\freightrec.sqlite --occurrence-id OCCURRENCE_ID --out link-binding.json
freightrec link --builder-only --input bundle.json --state C:\local-state\freightrec.sqlite --occurrence-id OCCURRENCE_ID --event link-intent.json --out link-receipt.json
```

prepare-link writes the original-source context and a separate `binding` object
with context_id, context_hash, context_revision and previous_event_id. Copy only
the binding fields to the intent; add request_id, action (`link` or `unlink`),
actor_id, explicit actor_kind and optional note. `link` additionally requires
target_shipment_id. `unlink` revokes the saved ruling and carries no target.
No context token, actor flag or stale event is silently filled or repaired.
Scripted examples must use agent_provisional: they never authorize a resolved
target. A persisted human ruling is separate from monetary review and can never
authorize a dispute or draft. Actor labels still provide no authentication or
evidence that an actual human session occurred.

Every stateful command hydrates the original sources once, reconciles without
manual links, refreshes the COMPLETE current context set (including successful
exact links), then reconciles with the trusted DecisionLog.resolve_link callback
and that same resolver. Only the final monetary findings are registered. The
link store observes an empty set and tombstones omitted contexts too, so a
change to invalid/absent sources and back cannot revive an earlier human ruling.
A local state file represents one current source batch: switching batches
invalidates omitted link contexts. Do not share one state file between unrelated
simultaneous workspaces. Exact automatic links always take priority; manual links
cannot override them. Targets must be uniquely supplied, source-valid shipments
in the same carrier namespace; DL2 validates the callback result.

After append_link, the CLI repeats the same refresh with the retained original
sources and registers the final finding revisions, so link/unlink changes cannot
silently preserve an obsolete monetary approval. Failed preparation, concurrent
CAS changes and invalid-source contexts refuse instead of guessing.
An observed read, hydration, baseline or complete-context validation failure
retires the prior context set before refusal. Source edits that no command has
observed cannot be detected; there is no background monitor.

All CLI and ledger state entrypoints use the shared policy documented in
STATE.md: an ordinary local absolute path outside source checkouts and OneDrive.
Path resolution/junction/symlink behavior and database access remain unexecuted.

Prepare a review intent using the original bundle and persistent local state:

```
freightrec prepare-review --builder-only --input bundle.json --state C:\local-state\freightrec.sqlite --finding-id FINDING_ID --out binding.json
freightrec review --builder-only --input bundle.json --state C:\local-state\freightrec.sqlite --finding-id FINDING_ID --event intent.json --out receipt.json
```

`prepare-review` performs the same two-stage original-source/link refresh,
registers only the final current findings, then writes finding_id, dependency_hash, finding_hash,
finding_revision and previous_event_id (null before any decision) to --out.
It records no decision. Copy these exact binding fields into an intent and
explicitly add request_id, action, actor_id and actor_kind. A dispute also
requires approved_cents equal to the finding's positive disputed_cents.
Optional note and link_target follow the DecisionLog action contract.

`review` requires --state (local SQLite outside repo/OneDrive), --finding-id
and --event (full explicit DecisionLog CAS intent JSON), and writes the receipt
to --out. It freshly reconciles and registers current findings before submitting
the caller's unchanged intent. It never replaces a stale binding or previous
event ID with current values; prepare a new intent after reviewing changed
inputs or an intervening decision. finding_revision prevents an older approval
from reviving after a change and revert. Scripted examples must use
agent_provisional. A human label supplies local attribution only; this CLI
cannot authenticate people or prove a human session.

`draft` takes the same bundle, --state, --finding-id and --out directory. It
hydrates original source documents, refreshes all link contexts, reconciles with
current persisted human links, registers final current findings, retrieves the latest
persisted decision and calls export_draft with DecisionLog currency checking.
The resolver is the same instance that archived the current original documents;
it is never rebuilt from a finding or a submitted receipt.
A current matching human dispute and verified original evidence are required.
Every file is inert DRAFT, NOT SENT. No command sends it anywhere.

Evaluation source lives outside the wheel in evaluation/. No CLI command
creates held-out inputs, grants admission or dispatches models. Independent
inputs, runtime seams and result reproducibility remain deferred.
