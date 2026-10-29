"""Future local diagnostic report writer; never a confirmatory dispatcher.

Run as python -m scripts.eval from the product repository after authorization.
No runtime execution has occurred during Dirty construction.
"""

import argparse
import json
from pathlib import Path

from evaluation.report import development_report, jsonl, markdown, not_run_report, report_json
from evaluation.run_eval import run_development


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite JSON number")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="new output directory; existing paths refuse")
    parser.add_argument("--development-input", help="retained builder/public-development observations and arm outputs")
    args = parser.parse_args(argv)
    report = not_run_report()
    if args.development_input:
        path = Path(args.development_input)
        if path.stat().st_size > 20_000_000:
            raise ValueError("development JSON exceeds 20 MB")
        artifact = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                              parse_constant=_constant)
        allowed = {"data_origin", "slice", "observations", "arm_outputs", "tolerance_cents"}
        if (not isinstance(artifact, dict) or set(artifact) - allowed or
                artifact.get("slice") != "dev" or artifact.get("data_origin") not in
                {"builder_non_independent", "public_development"}):
            raise ValueError("only explicitly labeled development artifacts accepted")
        run = run_development(artifact["observations"], artifact["arm_outputs"],
                              tolerance_cents=artifact.get("tolerance_cents", 0))
        report = development_report(run)
        report["input_origin"] = artifact["data_origin"]
    # Render completely before writing; invalid/nonfinite artifacts leave no
    # falsely successful partial result directory.
    outputs = {"results.md": markdown(report), "results.jsonl": jsonl(report),
               "report.json": report_json(report)}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    for name, content in outputs.items():
        with (out / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
