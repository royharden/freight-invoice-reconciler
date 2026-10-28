# Evaluation protocol — construction copy

Copied verbatim from promoted PLAN-M13-v1.md sections 7–8; no dev freeze or campaign has occurred. Promoted source lineage SHA256 eb1650fbd5c9dbc8427212bb5efe5fa805b81f8e1c45c70a3e5762a24f9dd229. Attribution: Claude 0855 and Codex 0854, merged by chooser 0901. A future actual dev freeze must bind exact candidate/protocol/sizing hashes. All runtime and independent evidence remains pending.

## 7. Sample allocation and freeze policy

Credit: Claude's analytic rule and private H-dev; Codex's independent public development sampler and precision simulation; bounded integration by chooser 0901. All sizes are design allocations, not measured adequacy.

- Pilot: 80 components, disjoint from dev. Private H-dev: 40 components, disjoint from every public/hidden set, J/O-only.
- Public dev: 240 components, 160 from B/G and 80 independently authored by H. Publish dev source bytes/labels and tune only here. Retain original pilot bytes unchanged.
- H-in: at least 160 components, sized below, confirmatory under this merge (stronger than Codex's descriptive-only choice).
- H-out: choose 300, 400, 600 or 800 components, with independently authored sources. It is confirmatory, separately reported; no pooling rescue.

Preregister `n_req(x)=ceil((1.96*stdev(x)/(0.25*abs(mean(x))))^2)` for per-component values. A zero mean returns infinity. At admission compute `g_in=n_req(A1 pilot C2)` and `g_out=n_req(A1 private H-dev C2)`; infinity fails admission. Record exact input hashes and mixture. At dev freeze compute paired `d=C2_A2-C2_A1` on public dev and independently on H's public subset. If either mean is >=0, stop before generating hidden inputs: report negative dev result; no confirmatory campaign. Let `q` be the larger n_req from these two negative-mean vectors.

Set H-in required N to max(160,g_in,q), round up to an integer and cap at 400. Any required N>400 is labeled **precision-limited before generation**, with the uncapped value retained. The cap never relaxes the realized pass rule.

For H-out, retain the analytic lower target max(300,g_out,q). On H's 80 public dev components, simulate paired stratified bootstrap precision at N in [300,400,600,800] using 1,000 simulations with a preregistered seed and the final ratio-of-sums estimands. Choose the first N meeting the analytic target and median predicted MO-rate-delta half-width <=0.02 against BOTH A0 and A1. When nonzero FD deltas vary, also require predicted FD-rate-delta half-width <=0.0005 against both. If all A2 dev FD=0, zero bootstrap width supplies **no FD sizing evidence**: size on MO only and predeclare the observed-zero reporting branch. Degenerate nonzero FD cannot qualify a width criterion.

If no N qualifies, choose 800 and label precision-limited, retaining every simulated width and unfulfilled analytic target. If Claude's analytic requirement exceeds 400, retain that earlier precision warning even if the larger allocation is used. These warnings are design limitations, never proof of adequate power. No final outcome may influence N, margins, strata, seeds or mixture. Realized intervals decide claims.

Freeze source revision, spec, oracle, schemas, extraction/link thresholds, all baselines, size selections, hidden seed commitments, confidence method, supported arms, stop policy and budget **before H/J create hidden inputs**. A hash and identity receipt covers each. No code changes after exposure. Only the custodian opens/releases inputs for one candidate campaign. Instruction-level custody and shared invented vocabulary remain limitations even when all receipts exist.

## 8. Preregistered evaluation

Copy sections 7â€“8 into docs/EVAL-PROTOCOL.md with attribution and hash at dev freeze; do not silently edit. This merge deliberately uses the intersection of source gates. Failure is a reportable negative result, not permission to weaken a comparison.

### Arms and observation parity

- **A0**, non-model arithmetic/duplicate-only: all duplicate occurrences after canonical first receive full-billed proposals; invoice line-sum minus stated total is assigned to the deterministic last/designated line only if uniquely assignable, nonnegative and within billed amount, otherwise abstain. Everything else clears. Freeze this policy in P1; no post-outcome repair.
- **A1**, non-model flat rate: newest contract, lane's first band without minimum; latest fuel table percentage times its own computed linehaul; billed detention units times latest rate with no free-time/authorization/cap semantics; newest liftgate amount without authorization. Explicitly define billed detention units and hourly/increment conversion in schema/vectors. Missing fields abstain. Never improve or degrade baselines after freeze.
- **A2**, product template extraction plus deterministic engine, the only headline candidate.
- **A2s**, identical engine on structured source truth, extraction diagnostic only, never headline substitution.
- **A3**, model selection among verified code-generated field/span candidates plus same engine: `not_run`, no transport in MVP. Mock responses demonstrate conformance only, never model quality.
- **A4**, single-prompt model judge: `not_run_guardrail` / disabled by ruling. Status only; no verdict dispatcher. A new explicit Roy exception is required before implementation, in addition to any later live permissions.
- **REF/O agreement**, reference amounts/coverage and adjudication agreement, never a self-scored model-quality row. **G-agreement** on H-in only; H-out truth null.

All A0/A1/A2 monetary comparisons consume the **same frozen extraction and link observations**. Extraction-arm comparisons are separate diagnostics. Invalid observation handling and missing occurrences cannot selectively shrink denominators. Every request contains only the matching carrier's source slice; ambiguous linkage refuses a request. Candidate model pointers must resolve against original sources and schemas, with code computing all amounts/verdicts.

A0's duplicate proposal takes priority on a line: if the designated residual line is already fully disputed as a duplicate, record residual assignment as abstained instead of adding a second proposal. A nonpositive residual proposes zero. This deterministic overlap rule is frozen with the baseline; it prevents a duplicate-plus-total-error combination from generating an above-billed output by accident.

### Dollar decomposition and invalid output

For every adjudicable occurrence, billed B, independently adjudicated reference R, deadband tol: `o=(B-R) if B-R>tol else 0`. Proposed d is code's full eligible overage, supported full-billed unsupported amount outside deadband, or zero for justified/undercharge/abstention. Compute `correct_proposed=min(d,o)`, `FD=max(d-o,0)`, `MO=max(o-d,0)` without netting across occurrences/invoices/undercharges. Quantified abstention misses the entire overage. Never describe correct_proposed as actual recovery.

Negative, noninteger, above-billed, malformed or missing-occurrence output invalidates that arm for confirmatory scoring. Retain attempted output/error; never clip, silently repair, drop rows or award a passing valid-subset score. A descriptive subset diagnostic must identify exclusions. Unknown-reference cases are separate: report unknown abstention accuracy, coverage and all proposed dollars as unsupported exposure. Unknowns cannot authorize drafts. Zero denominators are N/A, not zero error.

Scorer control vectors include a $1 proposal on $100 overage, all-abstain, abstention on the most expensive 10%, above-billed, negative, noninteger, malformed and missing-occurrence outputs. Compare the first three to a complete **correct** dispute arm: none can score better by avoiding known overages. The others invalidate the arm. This avoids promising that an incorrect aggressive arm always beats abstention. Include zero-denominator, degenerate-bootstrap and known-unauthorized/deadband tests.

### Metrics, confidence and pass gates

Report both raw FD/MO dollars and rates: FD/adjudicable-billed is the guard rate; MO/oracle-overcharge is the missed rate; also FD/oracle-overcharge as in Claude. `C2=sum(MO)+2*sum(FD)` with both components displayed, and lambda=1/2/5 sensitivity without selecting a weight afterward. Statistical resampling may use floating point; money generation/calculation never does.

Use paired connected-component bootstrap, 10,000 fixed-seed draws, whole components with replacement within fixed mixture strata; rates are ratio-of-sums, never mean per-line rates. Publish 95% intervals and paired deltas. A fully identical bootstrap distribution is degenerate: report observed value and the explicit inferential limitation rather than a fabricated interval. No rule-of-three incidence estimate times a 95th-percentile dollar exposure is a conservative population-dollar bound; future rare-harm inference needs a separate bounded-support preregistration.

**Each of H-in and H-out must satisfy ALL gates:**

1. Upper 95% bound <0 for paired C2 per-component deltas A2-A0 and A2-A1.
2. Upper 95% bound <0 for paired MO-rate deltas against both baselines. No oracle-overcharge denominator, overlapping thresholds or degenerate required nonzero improvement establishes a pass.
3. FD guard versus each baseline: for nondegenerate FD-rate deltas, upper 95% bound <=0.001 of adjudicable billed. This is a fixed engineering allowance of $1/$1,000 under the synthetic mixture, not an industry risk budget. Always display absolute FD dollars and both rate denominators.
4. If A2 FD is exactly zero and the comparison is degenerate, report **FD=0 observed on this corpus; noninferiority inference not testable**. An otherwise passing finite-corpus MO/C2 claim may state zero observed FD; never claim rare-harm noninferiority, zero future disputes or production safety. Degenerate nonzero FD is indeterminate.
5. No wrongly cleared occurrence in the injection category; no injection-caused verdict flip; no monetary proposal on any unanswerable case; valid arm output throughout.
6. Independent reference, custody, all disagreements, 20 agreed-line audits per slice, human adjudication spot-check and full failure ledger are complete. Any unresolved discrepancy blocks confirmatory scoring rather than disappearing from coverage.

Both slices pass => bounded synthetic claim on both. Either fails => overall preregistered combined claim not established; show each observed outcome and all gates. No successful H-in-only headline if H-out fails. Precision-limited failure is indeterminate when intervals cannot decide; distinguish it from a harmful observed result. An individual passing slice may be discussed descriptively with the failed joint hypothesis visible, never as a replacement preregistered success.

Also report line precision/recall, false-cleared lines/invoices, escalation/coverage by stratum, accuracy on non-escalated lines, per-field quote/value accuracy and pointer resolution, extraction errors, unsupported exposure, per-trap results, injection flips, G/O/E patterns, agreed-line audit outcomes, mutant kills, actual wall time and cost by origin. Prevalence and lambda sensitivity must not silently change the primary mixture/weight.

### Result artifacts and stop conditions

Generate results/results.md and results.jsonl from retained run artifacts; README imports generated numbers. Blocks: dev (`not a claim`), H-in and H-out. Main columns:

`arm | origin/status | components/occurrences | adjudicable billed $ | oracle overcharge $ | C2 [CI] | correct proposed $ | FD $ [both rates,CI] | MO $ [rate,CI] | P/R | bad clears | abstention/unknown exposure | raw-quote/value/pointer accuracy | cost/origin | wall time | review minutes`.

Second table: deltas versus A0/A1, C2 and MO thresholds, FD margins/degeneracy and every gate's pass/fail/indeterminate reason. Follow with trap, C1/C5, G/O/E, agreement-audit, mutants, sizing and failure tables. Empty/unrun cells say not_run/not_measured, never zero. Mock/non-model external calls/cost are zero with origin; missing live price/usage is unknown, not zero. Current-run replay cost and any original capture cost are separate.

Real reviewer count, session logs, elapsed review minutes and evidence-items-opened/actions are distinct. Review time is optional release evidence, not an execution/package gate. Without observed human sessions report `minutes not measured`; no synthetic timing or implied labor-dollar rate.

Stop on failed admission, unresolved spec/source pointers, invalid oracle/candidate outputs, hidden-set leakage, candidate changes after exposure, lost approval binding or any outbound effect path. Carrier mismatch/ambiguous facts abstain, not guessed. No improvement on dev stops before hidden generation. One campaign only at the recorded revision; infrastructure-only rerun on exactly the same frozen revision is logged with all attempts. Identical-result verification cannot tune the candidate. A changed candidate requires new preregistration/new held-out data, with the prior failed record preserved. Label code-change exposure contaminated. Held-out label errata retain original scores and add descriptive corrected scores. Budget exhaustion gives partial/not measured, never a completed model cell.

Named failure registry retains the union of source lists, with case IDs and every failed attempt: RATE_DATE/F2, INDEX_WEEK/F3, FUEL_BASE/F4, MIN_MASK/BAND_EDGE/F13, FREE_TIME/INCREMENT/DST_ELAPSED/F5, AUTH_CAP including unauthorized liftgate/F6 and cap allocation/F8, DUP_ALLOC/F7, LINK_AMBIGUOUS/F9, MISSING_FACT/F14, SPAN_INVALID/EXTRACTION_INVALID/F10, INJECTION/F11, STALE_REVIEW, ORACLE_DISAGREEMENT/F12, agreed-line audit failure/F15, invalid arm output/F16, wrongly cleared/F1 and PROVIDER_UNMEASURED. Include suspicious clean false alarms, unknown monetary proposals and error/status counts. After final scoring, synthetic source details and adjudication logs may be prepared for authorized publication; this plan does not publish them.
