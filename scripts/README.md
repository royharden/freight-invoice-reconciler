# Deferred source entry points

No script has run in Dirty construction. After separately authorized environment
activation, invoke from the product root:

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
read/write, metric/interval computations and import seams remain unexecuted.
