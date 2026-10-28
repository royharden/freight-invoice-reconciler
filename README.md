# Freight invoice reconciliation and dispute workbench

Private, local-only workbench with scoped native regression validation. Independent admission, human audit and evaluation remain pending. No benchmark or savings claim.

The source implements deterministic linehaul, fuel, detention and liftgate calculations; exact carrier-scoped linking and duplicate allocation; original-source evidence checks; append-only review decisions; and inert dispute drafts requiring current human approval. Monetary calculations use integer cents and Decimal rates. Missing evidence produces an explicit unknown outcome.

The merged PDF-capable CLI passed **375 builder-owned native regression tests** on Python 3.12.13 at revision `5d831a5`. Its guarded parser revision `b7166da` passed 329 natively and 324 on offline Linux, with five Windows-only skips. The CLI accepts exact original native PDF bytes and retains their quote/hash evidence; its first real PDF report produced three findings with 69 verified pointer occurrences. One 18-process structured-input journey passed on each platform; no human-approved draft was produced. Versioned frozen PDF observation recording is being completed; JSON recording remains compatible. These checks establish selected builder behavior, not independent accuracy or production readiness. See [validation evidence and limits](validation/ROUND2-REPORT.md).

See [CLI documentation](docs/CLI.md) for builder-only commands, [domain schema](docs/DOMAIN.md) for source shapes, and [limitations](docs/LIMITATIONS.md) for remaining checks. Commands require an explicit builder-only mode while admission is pending. No command sends a dispute, dispatches a live model, or establishes human participation. Drafts are labeled **DRAFT, NOT SENT**.

All evaluation results, review minutes and realized savings are unmeasured. The independent authors, custodian and human auditor have not been appointed. A3 and Jev remain not_run; A4 remains not_run_guardrail. No license or public release is approved.

Authoritative plan: ../planning/promoted/PLAN-M13-v1.md. Run: ../agentops/runs/M13-DIRTY-20261027.
