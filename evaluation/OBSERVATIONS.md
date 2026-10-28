# Shared diagnostic observation edition

Construction source only. None of the conversion, baseline, product replay or
scoring paths described here has run. This adapter is a builder tool; it supplies
no independent reference, authenticated human evidence or campaign admission.

`evaluation.observations.freeze_recording(documents, findings, links, strata,
*, engine_version, policy_version, source_resolver, tolerance_cents=0,
near_duplicate_ids=None)` creates one immutable
`FrozenObservations(canonical_json, sha256)` edition. `documents` has exactly
contracts, shipments, invoices and fuel_index: the same bound original-source
documents actually supplied to A2 after verification. `findings` is the actual
retained A2 result, including failed or malformed output. Engine and policy
strings are the actual captured revisions, not invented freeze receipts.
The actual A2 tolerance (0, 50 or 100 cents) is frozen too; consumers cannot
silently select a different baseline deadband from that recorded edition.
Each retained A2 finding must have exactly one allocation trace whose
deadband_cents is a strict integer equal to that captured tolerance. A missing,
duplicate, mistyped or mismatched deadband remains an invalid A2 attempt for
whole-arm scoring; it never changes A2, drops an occurrence or replaces the
captured tolerance. Only an otherwise valid cannot_determine finding with null
disputed_cents converts to abstain.

The producer must retain original bytes, parser editions and the original source
resolver. Before conversion, the adapter calls the product's public
verify_document on every document with that resolver. A source-binding failure
refuses the complete capture, never a successful subset. This shared check is
observation parity, not independent evidence or a truth judgment.
The adapter does not authenticate source authors or turn inferred PDF facts
into original JSON. It does not run product extraction, linking or pricing.
Source dictionaries are copied without rewriting provenance. Original source
proofs remain necessary when a caller later replays product input.

Every original invoice line must have unambiguous carrier/invoice/line identity
and strict nonnegative integer billed cents. The canonical occurrence ID uses
DL2's normalized carrier namespace and SHA-256 of `{identity, ordinal:0}`.
Ambiguous duplicate identities or malformed source lines refuse the entire
recording; there is no successful subset or silently dropped denominator.

`links` covers that exact occurrence universe. Each item is
`{status: exact|resolved|unresolved, shipment_id: string|null}`. It records the
actual shared upstream outcome, including a persisted human ruling where
applicable. It is not permission to link a shipment. The adapter checks exact
links against source references, requires a unique same-carrier target, and
never converts a fuzzy candidate to an exact link. A2's retained occurrence,
billed amount and link trace must agree with the shared capture; disagreement
makes A2's attempted output invalid. Missing/extra/duplicate A2 outputs are
retained for full-arm invalidation rather than filled with successful outputs.
Unresolved records have an explicit null target and all arms retain the row.

`strata` also covers every occurrence. Connected components join supplied
shipment, invoice, duplicate group and exact source-document identities. Optional
near_duplicate_ids adds only externally supplied case-copy identities; it is
not a semantic similarity detector or proof that a manifest is complete. One
component crossing mixture labels refuses the recording. Graph/copy completeness
and all scientific independence claims require later external review.

The common flattened rows retain actual total_cents, currency, timestamps,
charge/stop IDs, weight and link outcome. Currency is not defaulted. Detention
uses only explicit billed_detention_units (decimal string),
billed_detention_unit (hour, minute or increment) and, for increments,
billed_increment_minutes (decimal string). Missing or invalid units remain
unknown and make A1 abstain. No units are inferred from elapsed stop time,
billed dollars or expected/reference amounts.

`diagnostic_outputs(snapshot)` derives A0 and A1 from that
same edition and returns the retained A2 attempt unchanged apart from the
explicit finding-to-proposal wire conversion. It returns snapshot_sha256 with
the arm mapping and captured tolerance_cents. Baseline policy stays deliberately limited: A0 arithmetic and
duplicates; A1 newest lane contract, first listed band without minimum, latest
fuel publication's bracket percentage on its own linehaul, billed detention
units without free-time/authorization/cap, and newest liftgate amount. The
actual top-level lane contract and fuel-index wire shapes replace the earlier
unqualified lanes/percentage adapter. No outcomes have informed this change.

`product_input(snapshot)` returns only the original-source documents, with no
reference labels or manufactured link authority. A replay still requires the
original resolver and actual persisted link store outside this adapter.

Only `scoring_observations(snapshot, references)` joins external reference cents
by the exact frozen occurrence key set. Explicit null means unanswerable;
missing reference keys refuse rather than become zero or shrink a denominator.
Source documents reject reference/truth fields before freezing. The reference
join never mutates the snapshot or the product payload. Callers may pass its
returned observations plus diagnostic_outputs' arm mapping to run_development;
no caller is given permission to run it by this document. All admission, hidden
slices, oracle/custody/audits and human-session gates remain pending.

Deferred checks: actual source-capture/replay parity, canonical ID/component
stability, exact/manual/unresolved same-carrier outcomes, missing/extra/duplicate
candidate invalidation, snapshot mutation rejection, source-reference exclusion,
tolerance and allocation trace parity including missing/duplicate/mistyped traces,
billed detention conversions, actual-domain A1 latest-contract/index adapter,
and full-denominator/reference-join controls. No conversion or score has run.
