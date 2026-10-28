# Bounded invoice ingestion and exact evidence

Construction source only: no parser, PDF dependency or runtime behavior has been
executed or qualified. This adapter accepts one explicit invoice layout. Other
layouts, scanned PDFs, OCR, continuation pages and unknown descriptions refuse.

`freightrec.ingest.extract(document_slice)` accepts a dictionary with
`template_id="freightrec-invoice-v1"`, explicit `media_type="text/plain"` or
`"application/pdf"`, and `raw_bytes: bytes`. Native text can alternatively supply
`text: str`, encoded as UTF-8 without newline changes. Pass `resolver: SourceResolver`
to share source custody with reconciliation/drafts; otherwise retain the returned
`resolver`. The remaining result fields (`fields`, `pointers`, `invoice`, status and
reason) are JSON-compatible; the resolver itself is an in-process object, not a
wire field. A refused result always has `invoice=None`, even when some fields were
parsed. Do not construct an accepted invoice from those partial fields.

The exact native page grammar is shown below. This is explanatory builder content,
not independent evaluation data. Header order and separators are fixed. Each charge
line has six cells; the amount is USD dollars with exactly two decimals. At least
one charge line is required. Currency and charge units must be explicit.

```text
FREIGHTREC INVOICE V1
Carrier: <carrier namespace>
Invoice: <stable invoice ID>
Issued: <YYYY-MM-DDTHH:MM:SS+HH:MM or Z>
Currency: USD
Total: <nonnegative dollars.cents>
Lines:
<line ID>|<shipment reference>|<charge description>|<stop sequence>|USD|<dollars.cents>
```

Every line ID must be unique within the invoice. Line amounts must sum exactly to
the stated total. No commas, negative money, fractional cents, binary floats,
missing currency, empty IDs, naive dates, silent default fields or ignored lines
are accepted. The exact frozen charge vocabulary is case-insensitive `LH`,
`LINEHAUL`, `FS`, `FUEL`, `DETENTION`, `LIFTGATE`; descriptions outside it refuse.
This is deterministic normalization, with no fuzzy threshold or LLM inference.
LH and FS require stop sequence zero; DETENTION and LIFTGATE require a positive
delivery-stop sequence. A mismatch refuses the invoice.
Each field retains its exact raw quote, typed value, normalizer ID, method and
source pointer. Normalization never edits the archived page. A pointer always
addresses the raw value span; no normalized-text-to-raw alignment is guessed.

The invoice result has `carrier`, `invoice_id`, `invoice_issue_ts`, `currency`,
`total_cents`, `source_sha256`, `evidence_pointers`, `field_values`, and `lines`. Each line has
`line_id`, `shipment_ref`, `code`, `stop_seq`, `currency`, `billed_cents` and
`evidence_pointers`. All money in this result is nonnegative integer cents.
Linking and entitlement computation remain separate consumer responsibilities.

`freightrec.sources.verify_document(document, resolver) -> list[dict]` must run
before consuming invoice, shipment, contract or fuel facts. It raises `ValueError`
on missing or inconsistent bindings. Invoice `field_values` is a root-only map
whose canonical dotted paths exactly equal every nonmetadata scalar leaf, including
`invoice_id`, `invoice_issue_ts`, `total_cents` and all `lines.<index>.<field>`.
Each quote must equal the resolved source span; its named deterministic normalizer
must produce both the supplied typed value and the underlying document value with
exact Python/JSON types (boolean never equals integer). Extra and omitted bindings,
ambiguous keys, empty containers in leaf mode, floats and unknown normalizers refuse.
Shared normalizers live in `sources.normalize`; importing sources never imports PDF
ingestion or an optional parser.

For original structured sources, call `resolver.register_document(raw_bytes)` on
the actual UTF-8 JSON bytes for one contract, shipment, invoice or fuel-publication
object. It returns a document with a `$document` FieldValue binding the complete
archived native-JSON page. `verify_document` reparses that exact quote and checks
the entire document payload recursively with exact types, covering nested lists,
empty containers, null authorization states, decimal strings, dates and timestamps.
Duplicate JSON keys, floats (including NaN/Infinity), excessive nesting, numeric or
dotted object keys and reserved provenance names in source JSON refuse. Register
each object separately; array roots are not accepted. This is original structured
source custody, not PDF extraction, source truth or an independent adjudication.
Do not serialize guessed PDF facts and represent them as original structured evidence.

Only `evidence_pointers`, `field_values` and `source_sha256` are provenance metadata.
The last two are root-only; SHA must match bound source pointers. Declared evidence
pointers at any level must exactly match verified fact pointers. Nested field maps,
arbitrary metadata dictionaries and extra resolved but unbound evidence refuse.
In native-JSON mode the one complete-document pointer is evidence for all its facts;
consumers may reuse it for line/stop evidence. Normalizers bind values rather than
decide rate applicability; domain validation remains the pricing engine's job.

`SourceResolver.register_text(raw_bytes)` archives exact UTF-8 text, including
CR/LF. `register_pages(raw_bytes, pages, parser_profile)` archives exact extraction
text for a parser edition. `pointer(source_sha256,page_index,start,end,profile)`
uses zero-based page indexes and half-open Unicode **codepoint** offsets, not byte
or UTF-16 offsets. `SpanPointer.to_dict()` emits source SHA-256, parser profile,
page-text SHA-256, page index, start/end and quote SHA-256. `resolve(pointer)`
rechecks original bytes, page edition, bounds and quote hash and either returns
the exact quote or raises `ValueError`. A changed parser edition for identical
source/profile is refused. `snapshot()` returns sorted edition hashes for
dependency closure. No PDF coordinates or tamperproof storage are claimed.

Defaults bound original input to 8 MB, 100 archived pages and 200,000 codepoints
per page; v1 invoice extraction accepts one page and at most 1,000 charge lines.
The optional `pdfplumber` adapter validates the header, refuses encryption/malformed
content, bounds pages/output size and checks elapsed time between page operations.
Its profile includes the actual installed parser version. It has no OCR, document
script, fetch, shell or rendering path. No dependency is installed by this source.

Deferred validation: install/pin/qualify the optional PDF parser under later
authorization; verify native/PDF Unicode spans, newline changes, deterministic
normalization round trips, sums/dates/units, malformed/encrypted/oversize files,
unknown layouts/descriptions and changed bytes/editions. The elapsed check is
cooperative and cannot interrupt a parser blocked within a page; hard CPU/memory
isolation for untrusted PDF processing remains a later runtime activation item.
The adapter supports one native-text page only and fails closed if the underlying
PDFMiner encryption-state compatibility seam or parser version is unavailable.
Parser/version compatibility, encryption behavior and time/memory limits have not
been exercised; no dependency or license has been installed or adopted. Runtime
validation of tampered values, types, quotes, missing leaves and structured payload
mutations is deferred under the current static-only authorization.

## JSON and CSV record/field evidence

`resolver.register_json_records(raw_bytes, key_field)` accepts an original UTF-8
JSON array of uniform flat scalar records. `register_csv_records(raw_bytes,
key_field, normalizers)` accepts strict comma/double-quote CSV with unique explicit
identifier headers and one named normalizer for every column. Both return a list
of complete bound record dictionaries accepted by `verify_document`. Nested JSON
objects continue to use `register_document`; records are not flattened by guessing.

`RecordFieldPointer` extends the existing span with record format, zero-based
record index, unique string record key, key field, field name and conversion ID.
The resolver rechecks the exact field association in its immutable source edition,
not just a matching substring. Spans retain original JSON scalar token or CSV cell
lexemes, including quoting/escapes and original line endings. JSON scalar decoding
uses `json-scalar-v1`; CSV uses `csv-cell:<normalizer>`. Conversion, source edition,
record/key/field and quote are all bound. Downgrading a table pointer to a bare
span, mixing records, omitting original fields or changing conversions refuses.

Limits are 1,000 records, 100 fields and 4,000 codepoints per cell, in addition to
the registry byte/page bounds. Duplicate JSON keys/CSV headers, nonunique or empty
record keys, floats, mismatched schemas, unsupported nested records and ambiguous
syntax refuse. Empty CSV lexemes refuse; explicit `null` with `null-v1` represents
unknown when that column's declared schema permits it. A flat record is not an
invoice-assembly rule or an independent truth source. Whole-document JSON evidence
remains compatible with the existing CLI. Runtime parser/Unicode/escape/changed
source/record/normalizer and refusal vectors are deferred.

## Linking, batch allocation and findings

`freightrec.link.link_shipment(carrier, reference, shipments)` uses ASCII uppercase
and removes only ASCII spaces, hyphens and underscores. Other punctuation and
Unicode identifiers refuse linkage. Match only inside that normalized carrier
namespace, using shipment `reference` or, when absent, `shipment_id`. A unique
reference and unique namespaced stable shipment ID are both required. No fuzzy
match or link ruling is inferred. Carrier normalization is applied to copies at
the pricing seam; original spellings remain source-bound in the input closure.

`freightrec.reconcile.reconcile_batch(contracts, shipments, invoices, fuel_index,
sources=resolver, tolerance_cents=0, link_resolver=None)` calls DL1's actual `price_contracts` facade.
It does not resolve contract versions itself. Inputs follow `docs/DOMAIN.md` and
the invoice shape above; structured originals use `register_document`. The complete
supplied batch defines duplicate scope. Callers must supply all relevant invoices;
an omitted invoice cannot be discovered locally. Missing or invalid provenance
produces `cannot_determine`, null expectation/proposal and explicit missing facts.
A malformed occurrence conservatively blocks allocation for its linked shipment.

Each valid occurrence sorts by carrier, stable shipment ID, charge code, stop,
UTC invoice issue time, invoice ID and line ID. The first gets the entitlement;
later occurrences in that charge/stop group get known zero only after the engine
establishes entitlement. Duplicate invoice/line identity is ambiguous and never
silently deduplicated. Every input line produces a finding, including malformed
line objects. An invoice with no lines produces one missing-line diagnostic.

Money is strict nonnegative integer cents. Invoice currency and every line's own
currency must explicitly equal `USD`; missing or other line currencies produce
`cannot_determine` with null expectation/proposal before pricing. The root currency
does not supply a default for a line. Tolerance is exactly 0, 50 or 100.
Eligible overage is the full billed-minus-expected amount when above the deadband;
tolerance is never subtracted. Undercharges propose zero and never offset another
line. Known zero entitlement is `unsupported`, with zero proposal inside deadband.
Unknown facts cannot establish zero entitlement, duplicate money or approved dollars.

The dependency hash binds all supplied facts, source snapshots, the binding-closure
schema revision, policy version, linking behavior and DL1 `ENGINE_VERSION`; semantic
revision tokens must be bumped when their respective behavior changes. Documents
are verified before hashing. Each document joins its semantic payload to its sorted
verified source pointers and certificate identities: exact source span, normalizer
and extraction method. Leaf certificates stay attached to their typed fact and
semantic path while invoice lines are canonicalized, so matching line/certificate
permutations do not retain incidental dotted indexes. Outer collections and pointer
lists are also canonicalized. Reassigning an equal quote to another archived source,
changing a conversion or removing a certificate changes the dependency; failed
bindings carry a distinct invalid state and their supplied certificates. Whole native
JSON bindings retain their complete source pointer, so changed original JSON bytes
or source line order change the hash. Native invoice bindings still follow source
line order; shuffling an extracted document requires the matching field certificates,
not editing its values alone. Finding IDs follow namespaced invoice/line identity;
changed facts keep the ID but invalidate its dependency hash and review binding.

`evidence_pointers` includes complete verified invoice, line, shipment, contract,
fuel and clause evidence. Whole native JSON pointers cover every contained clause.
Findings retain clause ID, arithmetic/allocation trace, missing facts and an owner
to ask. Consumers refresh original inputs and reconciliation before human review
or inert draft export; stored findings cannot observe upstream changes themselves.

Deferred joined checks: canonical input permutations, duplicate invoice/line/PRO
collisions, typo and cross-carrier refusal, contract gap/overlap, missing evidence,
typed-value/source mutation, engine/policy revision invalidation, cap ordering,
duplicate plus undercharge, tolerance boundaries and DL3 stale-approval/draft joins.
No parser, pricing, reconciliation or draft behavior has been executed here.

## Source-bound link contexts and local rulings

Every uniquely identified source-valid billed occurrence with a normalizable
carrier/reference exposes `link_context`, including successful exact links. Invalid
source bindings, ambiguous occurrence identity, invalid reference or invalid billed
money give no actionable context. The context contains exactly `context_id`,
`occurrence_id`, normalized `carrier`/`reference`, and `dependency_hash`. Its ID is
stable per occurrence. Its dependency binds the full verified original input batch,
all candidates, namespaces, source/conversion certificates, policy and engine before
any manual links, callbacks or final findings. Baseline and resolved findings retain
the same original context; the final result is never fed into its own hash.

An optional trusted local CODE callback `link_resolver(context)->shipment_id|None`
is called only after exact automatic linking fails. It never overrides a successful
exact link and never accepts a raw caller ruling dictionary or verified flag. A
target must be a unique original source-valid supplied shipment in the same carrier
namespace. Missing, duplicate, cross-carrier and invalid-source targets refuse;
callback refusal leaves the occurrence unknown. Final finding dependencies bind the
canonical actually applied context-to-target set in addition to the original hash.
Link approval alone authorizes no disputed dollars or draft. This callback is a local
code seam; it is not human authentication and does not itself establish a human act.

DL4 first reconciles original sources without rulings, refreshes ALL current link
contexts through DL3 (including exact links), then reconciles the same retained
originals with the persisted-human-link resolver. Only final findings enter monetary
review. The store/CLI must also retire formerly current contexts absent from the new
valid set, including invalid/removed occurrences, so source disappearance and return
cannot revive old rulings. That shared store/CLI absence API is INT-owned; DL2 emits
no fabricated contexts for invalid sources. Deferred checks include exact-link
priority, baseline/resolved context equality, callback rejection, cross-carrier and
duplicate targets, A-B-A/absence staleness, source-policy-engine changes, unlink and
provisional denial, and subsequent monetary review/draft separation.
