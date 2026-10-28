# Builder illustration

unknown-reference.json is an original, deliberately incomplete source bundle for
showing missing-reference handling; the round-two CLI checks do not qualify it.
simple-shipment.json uses DL1's published domain schema and DL2's invoice shape.
Both have invented names and explicit builder_non_independent labels. No golden
output, oracle amount or score is included. These are not pilot/dev/held-out or
independent evaluation data. Native CLI regressions now exercise the simple
shipment sources; no result from them is an independent benchmark or human audit.

For the original JSON examples, each collection entry is the exact original JSON
document as a string. The CLI encodes that original string directly as UTF-8 for
SourceResolver.register_document and retains the resolver through reconciliation,
review and export. It never rebuilds original evidence from derived dictionaries.
The unknown example has no shipment/contract facts and cannot authorize a draft.

native-invoice-v1.pdf is an additional ORIGINAL builder-native PDF authored by
M13-DL4 (0992_Codex_gpt-61-sol_N20M13DL4 / app0004), using the original stdlib
writer in scripts/make_builder_pdf.py and explicitly invented TEXT there. No
external PDF, account, download, library generation dependency or gold answer is
included. The PDF is961bytes; raw SHA256 is
34d575ccb33b2efe1ed046baed4ffffaeb5c1ffb082e81c9895180f4c2a4c198.

native-pdf-bundle.json contains that exact PDF in a strict base64 descriptor;
contract/shipment/fuel source strings are retained unchanged from the original
builder example. No prior fixture was altered. The generator is deterministic
and refuses to replace a different existing edition. This is one parser/journey
illustration, never independent pilot/gold/heldout data or evidence of accuracy.
