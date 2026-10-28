# Builder illustration

unknown-reference.json is an original, deliberately incomplete source bundle for
showing missing-reference handling; the round-two CLI checks do not qualify it.
simple-shipment.json uses DL1's published domain schema and DL2's invoice shape.
Both have invented names and explicit builder_non_independent labels. No golden
output, oracle amount or score is included. These are not pilot/dev/held-out or
independent evaluation data. Native CLI regressions now exercise the simple
shipment sources; no result from them is an independent benchmark or human audit.

Each contracts/shipments/invoices/fuel_index entry is the exact original JSON
document as a string. The CLI encodes that original string directly as UTF-8 for
SourceResolver.register_document and retains the resolver through reconciliation,
review and export. It never rebuilds original evidence from derived dictionaries.
The unknown example has no shipment/contract facts and cannot authorize a draft.
