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
produces no benchmark score. Outputs use exclusive creation to preserve prior
artifacts. Without --builder-only, commands refuse pending admission.

Prepare a review intent using the original bundle and persistent local state:

```
freightrec prepare-review --builder-only --input bundle.json --state C:\local-state\freightrec.sqlite --finding-id FINDING_ID --out binding.json
freightrec review --builder-only --input bundle.json --state C:\local-state\freightrec.sqlite --finding-id FINDING_ID --event intent.json --out receipt.json
```

`prepare-review` freshly reconciles the original input, registers the current
findings, then writes finding_id, dependency_hash, finding_hash,
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
hydrates original source documents, reconciles current inputs, registers
current findings, retrieves the latest
persisted decision and calls export_draft with DecisionLog currency checking.
The resolver is the same instance that archived the current original documents;
it is never rebuilt from a finding or a submitted receipt.
A current matching human dispute and verified original evidence are required.
Every file is inert DRAFT, NOT SENT. No command sends it anywhere.

Evaluation source lives outside the wheel in evaluation/. No CLI command
creates held-out inputs, grants admission or dispatches models. Independent
inputs, runtime seams and result reproducibility remain deferred.
