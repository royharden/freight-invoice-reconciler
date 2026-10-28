"""Local keyless CLI. Construction commands do not establish admission."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def _read(path):
    path = Path(path)
    if path.stat().st_size > 20_000_000:
        raise ValueError("JSON input exceeds 20 MB limit")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object,
                      parse_constant=_invalid_constant)


def _write(path, value):
    # Exclusive creation preserves previous artifacts and evidence.
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def _hydrate(bundle):
    """Archive original JSON bytes and retain their bound values together."""
    from .sources.registry import SourceResolver
    collections = ("contracts", "shipments", "invoices", "fuel_index")
    if not isinstance(bundle, dict) or set(bundle) - {
            "data_origin", "tolerance_cents", *collections}:
        raise ValueError("unsupported construction bundle fields")
    for name in collections:
        originals = bundle.get(name)
        if not isinstance(originals, list) or any(not isinstance(raw, str) for raw in originals):
            raise ValueError(f"{name} must be a list of original JSON strings")
    resolver = SourceResolver()
    documents = {}
    for name in collections:
        # Encode original string contents directly. Never serialize parsed or
        # metadata-bound values and present that reconstruction as original.
        documents[name] = [resolver.register_document(raw.encode("utf-8"))
                           for raw in bundle[name]]
    return resolver, documents


def _reconcile(documents, resolver, tolerance_cents=0):
    from .reconcile.reconcile import reconcile_batch
    return reconcile_batch(documents["contracts"], documents["shipments"], documents["invoices"],
                           documents["fuel_index"], sources=resolver,
                           tolerance_cents=tolerance_cents)


def _builder(bundle):
    if not isinstance(bundle, dict) or bundle.get("data_origin") != "builder_non_independent":
        raise ValueError("construction input must be labeled builder_non_independent")


def _find(findings, finding_id):
    matches = [f for f in findings if f.get("finding_id") == finding_id]
    if len(matches) != 1:
        raise ValueError("finding_id must resolve uniquely")
    return matches[0]


def main(argv=None):
    # Refuse before file reading, environment lookup or facade imports, even
    # when --live appears after a subcommand or malformed arguments.
    args_list = list(sys.argv[1:] if argv is None else argv)
    if any(item == "--live" or item.startswith("--live=") for item in args_list):
        print(json.dumps({"status": "live_not_enabled", "origin": "disabled"}))
        return 2
    parser = argparse.ArgumentParser(prog="freightrec")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show admission and model status without effects")
    for name in ("reconcile", "demo", "report", "prepare-review", "review", "draft"):
        command = sub.add_parser(name)
        command.add_argument("--input", required=True, help="frozen builder JSON bundle")
        command.add_argument("--builder-only", action="store_true")
        command.add_argument("--out", required=True)
        if name in ("prepare-review", "review", "draft"):
            command.add_argument("--state", required=True, help="SQLite path outside repo/OneDrive")
            command.add_argument("--finding-id", required=True)
        if name == "review":
            command.add_argument("--event", required=True, help="explicit full CAS intent JSON")
    args = parser.parse_args(args_list)
    if args.command == "status":
        print(json.dumps({"construction": "runtime_unverified", "admission": "pending_needs_Roy",
                          "A3": "not_run", "A4": "not_run_guardrail",
                          "benchmark": "not_run", "review_minutes": "not_measured"}))
        return 0
    if not args.builder_only:
        print(json.dumps({"status": "admission_pending", "reason": "independent prerequisites not accepted"}))
        return 2
    try:
        bundle = _read(args.input)
        _builder(bundle)
        resolver, documents = _hydrate(bundle)
        findings = _reconcile(documents, resolver, bundle.get("tolerance_cents", 0))
        if args.command in ("reconcile", "demo"):
            _write(args.out, {"data_origin": "builder_non_independent", "runtime_acceptance": False,
                              "benchmark_status": "not_run", "findings": findings})
        elif args.command == "report":
            from .review.report_html import report_html
            with Path(args.out).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(report_html(findings))
        else:
            from .review.log import DecisionLog
            state = Path(args.state).resolve()
            # Refuse obvious synced/repo paths, avoiding SQLite/WAL in OneDrive.
            if any(part.lower() in {"onedrive", "src", ".git"} or
                   part.lower().startswith("onedrive-") for part in state.parts):
                raise ValueError("state must be outside OneDrive and repository")
            for anchor in (Path.cwd().resolve(), Path(__file__).resolve().parents[2]):
                if (anchor / "pyproject.toml").exists() and state.is_relative_to(anchor):
                    raise ValueError("state must be outside repository")
            if any((parent / ".git").exists() or (parent / "pyproject.toml").exists()
                   for parent in state.parents):
                raise ValueError("state must be outside repository")
            log = DecisionLog(state)
            finding = _find(findings, args.finding_id)
            bindings = {item["finding_id"]: log.register_finding(item) for item in findings}
            if args.command == "prepare-review":
                previous = log.latest(args.finding_id)
                _write(args.out, {"finding_id": args.finding_id,
                                  "dependency_hash": finding["dependency_hash"],
                                  **bindings[args.finding_id],
                                  "previous_event_id": previous["event_id"] if previous else None})
            elif args.command == "review":
                event = _read(args.event)
                if not isinstance(event, dict):
                    raise ValueError("review intent must be a JSON object")
                if event.get("finding_id") != args.finding_id:
                    raise ValueError("intent/finding mismatch")
                # Preserve the caller's complete binding. A stale intent must
                # fail CAS, never be rebound to this command's fresh finding.
                _write(args.out, log.append(event))
            else:
                from .dispute.draft import export_draft
                decision = log.latest(args.finding_id)
                path = export_draft(finding, decision, resolver, args.out, decision_log=log)
                print(str(path))
    except (ValueError, KeyError, TypeError, OSError, ImportError, sqlite3.Error) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
