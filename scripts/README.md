# Deferred source entry points

The demo/evaluation wrappers below require authorized environment activation.
Native builder regressions exercise their underlying APIs; no independent
campaign or actual human session is implied. Invoke from the product root:

```
python -m scripts.demo --input fixtures/builder/simple-shipment.json --out illustration.json
python -m scripts.eval --out unrun-report
python -m scripts.eval --development-input retained-dev.json --out dev-report
```

The default eval path writes explicit not_run templates. Optional development
input contains data_origin (builder_non_independent or public_development),
slice=dev, observations, arm_outputs and optional tolerance_cents. Its reference
values and candidate outputs must be actual retained externally supplied records;
this tool neither authors nor authenticates them. See evaluation/README.md for
the schema and source-only metric APIs. Scoring a builder example proves no
independence. Every development result remains diagnostic; H-in/H-out stay
unrun and independent prerequisites pending. No confirmatory dispatch exists.

The report writer retains Markdown, all-section JSONL and full strict JSON in a
new directory. It preserves invalid-arm errors and unmeasured fields. Artifact
read/write and process-level wrapper joins need their own execution evidence;
the underlying small API controls do not qualify a full campaign.

`journey_round2.py` is the bounded native process runner authorized separately by
ROUND2-JOURNEY-r1. Invoke with INT's Python 3.12.13, `--source-revision` equal to
the externally checked exact merged Git commit and `--artifacts` naming a new
directory outside source/OneDrive. It launches only the current interpreter and
actual CLI module, with explicit environment names. It records command/exit/
raw stdout/stderr bytes and source/artifact hashes in journey.json. Output hashes
cover the exact captured bytes; strict UTF-8 decoding follows evidence retention.
Original fixtures remain
unchanged; the changed-source control is an explicitly new builder edition.
Every intent is agent_provisional; a refused draft is the expected outcome. Its
result is one builder process journey, never independent admission or a benchmark.
