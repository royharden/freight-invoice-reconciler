# Freight invoice reconciliation and dispute workbench

Private, local-only workbench with scoped native regression validation. Independent admission, human audit and evaluation remain pending. No benchmark or savings claim.

The source implements deterministic linehaul, fuel, detention and liftgate calculations; exact carrier-scoped linking and duplicate allocation; original-source evidence checks; append-only review decisions; and inert dispute drafts requiring current human approval. Monetary calculations use integer cents and Decimal rates. Missing evidence produces an explicit unknown outcome.

The merged source at `ae415e1` passed **559 native Windows tests** and **554 offline Linux tests**, with five Windows-only skips. Explicit v2 frozen observations preserve exact original PDF/JSON recording and replay; legacy v1 JSON remains compatible and refuses PDF. A fresh offline wheel installed outside the checkout produced three findings with 69 verified original-PDF evidence-pointer occurrences. One earlier 18-process structured-input journey passed on each platform. These builder checks establish selected behavior; independent accuracy, human participation and production readiness remain pending. See [validation evidence and limits](validation/ROUND2-REPORT.md).

See [CLI documentation](docs/CLI.md) for builder-only commands, [domain schema](docs/DOMAIN.md) for source shapes, and [limitations](docs/LIMITATIONS.md) for remaining checks. Commands require an explicit builder-only mode while admission is pending. No command sends a dispute, dispatches a live model, or establishes human participation. Drafts are labeled **DRAFT, NOT SENT**.

All evaluation results, review minutes and realized savings are unmeasured. The independent authors, custodian and human auditor have not been appointed. A3 and Jev remain not_run; A4 remains not_run_guardrail. No license or public release is approved.

Authoritative plan: ../planning/promoted/PLAN-M13-v1.md. Run: ../agentops/runs/M13-DIRTY-20261027.
