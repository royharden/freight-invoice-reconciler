# Evaluation source

Builder-authored tools from promoted `PLAN-M13-v1.md` sections 7–8. These files
now have focused native builder regressions for small integer controls and original
builder-source capture. No corpus benchmark or full sizing simulation has run.
These checks establish no data independence, admission or human review evidence.

`arms.a0` and `arms.a1` implement the frozen deliberately limited policies.
`metrics.score_arm` requires one explicit output per occurrence and invalidates
the whole arm on malformed output. `bootstrap.raw_bootstrap` and
`bootstrap.paired_bootstrap` resample whole connected components with replacement
inside fixed strata and report raw C2/FD/MO dollar/rate intervals and paired deltas,
degeneracy/zero denominators without invented intervals. Component IDs and
stratum assignments must be supplied by the frozen, independently checked split;
the scorer does not infer or certify graph connectivity. `components.connected_components`
joins externally supplied shipment/invoice/duplicate links and supplied exact/near-copy
identities; `inspect_splits` flags any such component crossing splits. Completeness of
the input graph and near-copy manifest remains an independent review prerequisite.

The shared capture adapter is `observations.freeze_recording`; see
[OBSERVATIONS.md](OBSERVATIONS.md) for its exact source/link/finding contract. It
freezes the
complete source occurrence universe, canonical IDs/components, explicit recorded
link outcomes and actual A2 attempts in one hash-bound immutable JSON edition.
Every arm uses that edition; references join only in evaluation through an
exact-keyset `scoring_observations` call. `product_input` returns facts only and
does not manufacture persisted manual-link authority or original source bytes.
The current frozen observation edition is original-JSON only. Valid original-PDF
descriptors and PDF-bound invoice editions fail closed with `unsupported_source:`
at capture, load, diagnostic and replay boundaries. CLI native-PDF input remains
separate; recording never reconstructs parsed PDF facts as original JSON.
Descriptor validation uses the canonical original-bundle codec. See the PDF
capability boundary in OBSERVATIONS.md before attempting a PDF comparison.
The baseline wire adapter is documented in `arms.py`; pricing stays separate
from product charge helpers. A0 uses canonical offset timestamps,
carrier/shipment/code/stop keys, invoice IDs and stable line IDs. Its designated
residual line is lexically last `(line_id, occurrence_id)` within the invoice;
every flattened observation row must repeat the actual invoice `total_cents`
(no `invoice_total_cents` alias) and carry explicit `currency: "USD"`. Missing or
non-USD currency abstains and prevents an invoice arithmetic proposal; no currency
default is supplied. Missing/conflicting totals
make the designated arithmetic outcome abstain. An independently known full
duplicate proposal survives with a residual-abstained marker. A duplicate proposal
takes priority. A1 uses newest `(effective_from, contract_id)`, first listed lane band,
and latest fuel publication, regardless of shipment date. Detention billed units
have explicit decimal-string hours/minutes/increments, never inferred from elapsed
time. A1 requires explicit row `currency: "USD"` before pricing; missing/non-USD
currency abstains without a monetary proposal. It consumes the actual domain's
top-level lane contracts and latest index_value through the newest contract's
fuel bracket. Builder regressions exercise source capture and baseline conversion;
broader baseline policy qualification remains deferred. Recorded
resolved human links are shared upstream observations, not fuzzy automatic
links, and no adapter can authorize a product link. Supply the same frozen extraction/link
observations to every arm. No baseline
policy may change after freeze without a new preregistration.

`sizing.n_req` returns `{status, value, reason}`: finite values are integers;
infinite or unidentified requirements have `value: null` and an explicit reason.
`sizing.analytic_policy` retains those records alongside uncapped targets and caps.
It implements the preregistered analytic formula and dev stop.
`simulate_precision` is expensive, source-only nested design simulation on the 80
H-authored PUBLIC dev components; defaults are 1000 simulations and 10,000 inner
draws for each candidate N. All widths and indeterminate samples are retained.
Seeds here are proposed source constants until J records the actual pre-hidden
freeze. Its analytic target accepts a finite nonnegative number or the explicit
`h_out_analytic_requirement` record; booleans, NaN and bare infinity are rejected.
Nonfinite requirements cannot qualify a simulated size. Provenance of the public-H
subset is an external prerequisite.

`report.not_run_report` exposes unrun result cells.
`run_eval.run_development` accepts retained external outputs for diagnostics;
it retains raw intervals, paired comparisons, invalid-arm errors/attempts and
diagnostic gates. `report.development_report(run, *, sizing=None)` maps that
retained result to measured dev rows, interval/threshold/degeneracy tables and
failure records without rerunning calculations. Unmeasured ancillary diagnostics
remain `not_measured`; independent gates and both H slices remain pending.
`report.markdown`, `jsonl` and `report_json` render the report with strict JSON
numbers (`allow_nan=False`). JSONL uses `arm_result` records with a `row`, plus one
`report_section` record per other top-level field with `section` and `value`, so
gates, deltas, sizing, failure records and retained run artifacts are not dropped.
Invalid attempted NaN/infinity floats use explicit `invalid_nonfinite_float`
tagged objects in the report; the original attempt remains in the retained run.
`run_confirmatory` refuses. Admission inspection only checks external record
structure and always leaves GO pending for actual J/human/Roy dispositions.
No custody-opening, oracle, heldout generator, independent gold, scoring campaign
or provider transport is implemented. A3 is not run; A4 is status only and disabled.

Focused builder regressions exercise partial/all/selective-abstention scorer
controls, malformed/missing/negative/float/bool/above-billed attempts, strict
deadbands, component identity and split checks, whole-component stratified
resampling, ratio-of-sums denominators, degeneracy, zero denominators, seeded
repeatability, invalid-attempt JSON/JSONL retention and nonfinite analytic sizing.
These are small diagnostic calculations, not corpus benchmark scores or evidence
of improvement. Broader baseline vectors, the full 1000-by-10,000 sizing simulation
and its performance, comprehensive serialization round trips,
missing/conflicting-total A0 residual/duplicate branches, broader raw/delta interval
parity and external evalkit comparison remain deferred. Full confirmatory gates,
independent references/mutants, trap/injection/audit results, custody and real human
spot-checks remain pending; no numeric zero means unrun.
