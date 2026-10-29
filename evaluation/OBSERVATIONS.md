# Shared diagnostic observation edition

This adapter is a builder tool with focused native regression controls for capture,
baseline conversion and scoring. No independent corpus or campaign has run; the
adapter supplies no independent reference, authenticated human evidence or admission.

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
into original JSON. The v1 adapter does not run product extraction, linking or pricing. The explicit
v2 adapter rehydrates originals through the canonical guarded source helper;
it does not rerun linking or A2 pricing.
Source dictionaries are copied without rewriting provenance. Original source
proofs remain necessary when a caller later replays product input.

### Explicit original-bundle v2

`freeze_recording` remains the JSON-only v1 API. Valid PDF descriptors and
PDF-bound invoices refuse with `unsupported_source:` at capture and every
loading consumer, including manually rehashed snapshots. Malformed descriptors,
including `field_values: {}` or extra markers, fail canonical descriptor
validation first. Existing valid JSON v1 recordings retain their format.

Use `freeze_original_bundle_recording(original_bundle, documents, findings,
links, strata, *, engine_version, policy_version, source_resolver,
tolerance_cents=0, near_duplicate_ids=None)` to opt into
`freightrec-observation-v2-originals`. The bundle uses the same strict codec as
CLI input. It retains exact original JSON strings and PDF base64, including their
original bytes and SHA; only the outer snapshot container is canonicalized.
Parsed PDF facts never become replacement original JSON.
The v2 original envelope permits only the four source collections, optional
`tolerance_cents`, and optional `data_origin`. When present, `data_origin` must
be exactly the string `builder_non_independent`; nested metadata, other values
and extra root fields refuse at capture and every loading consumer, even after
rehashing. The adapter rejects contaminated originals without stripping fields
or rewriting the original payload. An absent optional marker stays absent.

Capture rehydrates the complete bundle into the supplied current source resolver
and compares every bound document, typed field, source/page/quote pointer and
parser/normalizer edition with the supplied captured documents. The resolver
must be the actual current SourceResolver. The entire capture refuses on a
mismatch; no successful subset is retained. Findings remain the actual supplied
A2 attempts, including malformed attempts, rather than newly computed answers.

Every v2 `load`, diagnostic, scoring and product-input call uses centralized
strict validation: exact root fields/version, current engine/policy,
original-bundle schema, captured tolerance and runtime edition. Replay freshly
hydrates the originals through the canonical guarded parser and compares complete
source bindings and recomputed observation derivations. A rehashed edit alone
cannot bypass original-source validation. Worker unavailability or timeout
refuses without fallback; current parser limits and the default five seconds
remain unchanged.

The runtime edition records Python/platform, local parser dependency versions and
source-file hashes for the product and observation implementation. Changed
dependencies, profiles or source editions require a new capture; replay never
silently reclassifies the edition. This strict edition may refuse across
platforms. It is a reproducibility commitment, not historical execution or
author authentication. An external owner must retain the expected capture hash.
Replacing both a fully consistent recording and its trusted hash creates a new
recording; the unkeyed hash cannot authenticate a human or adjudicate truth.

V2 `product_input` returns only a fresh copy of the exact original mixed bundle,
with no recorded rows, findings, reference labels or manufactured link authority.
Original payload strings/base64 remain unchanged. Each arm uses the same frozen
occurrence/link/fact/unit/deadband observations; only external exact-key scoring
joins references. V1 product replay retains its existing bound-document behavior
and still requires the original resolver.

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

`product_input(snapshot)` returns bound documents for v1 and exact original
bundle payloads for v2, with no reference labels or manufactured link authority.
Product replay retains the actual persisted link store outside this adapter;
v1 additionally requires its original resolver.

Only `scoring_observations(snapshot, references)` joins external reference cents
by the exact frozen occurrence key set. Explicit null means unanswerable;
missing reference keys refuse rather than become zero or shrink a denominator.
Source documents reject reference/truth fields before freezing. The reference
join never mutates the snapshot or the product payload. Callers may pass its
returned observations plus diagnostic_outputs' arm mapping to run_development;
no caller is given permission to run it by this document. All admission, hidden
slices, oracle/custody/audits and human-session gates remain pending.

Focused builder regressions exercise original-source capture and fact replay,
exact-link capture, detached replay mutation isolation, source mutation refusal,
reference-join keyset checks and reference-label exclusion from the frozen payload.
They also exercise missing A2 output and mismatched/missing/duplicate/mistyped
allocation-deadband invalidation without row loss, plus A0/A1 conversion and small
diagnostic scoring. These calculations establish no corpus benchmark score,
improvement or human evidence.

Broader adapter-specific canonical ID stability, manual/unresolved link vectors,
extra/duplicate A2 output cases, forged snapshot rejection, reserved source-field
exclusion, billed detention conversions, A1 latest-contract/index expected-value
vectors and comprehensive denominator parity remain deferred. Graph/copy
completeness, independent references, the full evaluation campaign and admission
remain pending.

The v2 builder controls capture the existing native PDF fixture, preserve its
raw SHA/profile/exact quotes, replay the original mixed bundle and compare shared
arms. They cover all consumers, rehashed source/derivation/schema/identity and
runtime mutations, descriptor-extra bypasses, worker refusal, detached copies,
reference exclusion, malformed A2 whole-arm invalidation and v1 compatibility.
They establish source representation/replay only, with no independent dataset,
performance claim or admission.
