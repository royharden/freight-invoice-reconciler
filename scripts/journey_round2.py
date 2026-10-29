"""One keyless builder process journey; no human or benchmark evidence."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return path


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


class Journey:
    def __init__(self, artifacts, revision):
        self.out = Path(artifacts).resolve()
        require(not self.out.is_relative_to(ROOT), "artifacts must be outside source checkout")
        require(not any("onedrive" in part.casefold() for part in self.out.parts),
                "artifacts must be outside OneDrive")
        self.out.mkdir(parents=True, exist_ok=False)
        (self.out / "tmp").mkdir()
        # Explicit noncredential allowlist. Never inherit or enumerate the
        # parent's environment or inspect account/provider variables.
        self.env = {
            "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8", "TEMP": str(self.out / "tmp"),
            "TMP": str(self.out / "tmp"),
        }
        if os.name == "nt":
            self.env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        self.report = {"status": "running", "data_origin": "builder_non_independent",
                       "source_revision": revision, "interpreter": sys.executable,
                       "python_version": sys.version, "runner_sha256": sha(Path(__file__)),
                       "source_sha256": {str(p.relative_to(ROOT)): sha(p)
                                         for p in sorted((ROOT / "src").rglob("*.py"))},
                       "environment_names": sorted(self.env), "steps": [],
                       "actor_kind": "agent_provisional", "human_session": "not_measured",
                       "independent_admission": "pending", "external_spend_usd": 0,
                       "placeholders": []}
        self.save()

    def save(self):
        (self.out / "journey.json").write_text(
            json.dumps(self.report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8", newline="\n")

    def process(self, name, arguments, expected=0, *, preflight=False):
        command = [sys.executable] + (arguments if preflight else ["-m", "freightrec.cli", *arguments])
        prefix = f"{len(self.report['steps']) + 1:02d}-{name}"
        stdout_path, stderr_path = self.out / (prefix + ".stdout.txt"), self.out / (prefix + ".stderr.txt")
        started = time.perf_counter()
        try:
            result = subprocess.run(command, cwd=ROOT, env=self.env, capture_output=True,
                                    text=False, timeout=60, check=False)
            code, stdout_bytes, stderr_bytes = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as exc:
            code, stdout_bytes, stderr_bytes = None, exc.stdout or b"", exc.stderr or b""
        # Retain and hash exact captured bytes before exit validation or decoding.
        stdout_path.write_bytes(stdout_bytes)
        stderr_path.write_bytes(stderr_bytes)
        step = {"name": name, "command": command, "cwd": str(ROOT),
                "expected_exit": expected, "actual_exit": code,
                "elapsed_seconds": time.perf_counter() - started,
                "stdout": stdout_path.name, "stdout_sha256": sha(stdout_path),
                "stderr": stderr_path.name, "stderr_sha256": sha(stderr_path)}
        self.report["steps"].append(step)
        self.save()
        print(f"{prefix}: exit={code}, expected={expected}", flush=True)
        require(code == expected, f"{name}: unexpected process exit; see retained stdout/stderr")
        return stdout_bytes.decode("utf-8", errors="strict"), stderr_bytes.decode("utf-8", errors="strict")

    def cli(self, name, command, source, *, state=None, expected=0, **options):
        target = self.out / (name + (".html" if command == "report" else ".json"))
        args = [command, "--builder-only", "--input", str(source), "--out", str(target)]
        if state is not None:
            args += ["--state", str(state)]
        for key, value in options.items():
            args += ["--" + key.replace("_", "-"), str(value)]
        stdout, stderr = self.process(name, args, expected)
        return target, stdout, stderr

    def run(self):
        stdout, _ = self.process("source-preflight", ["-c",
            "import sys,json,freightrec; print(json.dumps({'executable':sys.executable,"
            "'source':freightrec.__file__,'version':list(sys.version_info[:3])}))"], preflight=True)
        proof = json.loads(stdout)
        require(Path(proof["source"]).resolve() == ROOT / "src/freightrec/__init__.py",
                "unexpected imported product checkout")
        require(Path(proof["executable"]).resolve() == Path(sys.executable).resolve(),
                "unexpected child interpreter")
        require(proof["version"] == [3, 12, 13], "journey requires INT's Python 3.12.13")
        stdout, _ = self.process("status", ["status"])
        require(json.loads(stdout)["A4"] == "not_run_guardrail", "A4 status changed")
        stdout, _ = self.process("live-refusal", ["reconcile", "--live", "--input",
            str(self.out / "absent-input.json"), "--out", str(self.out / "live-output.json")], 2)
        require(json.loads(stdout)["status"] == "live_not_enabled", "live refusal changed")
        require(not (self.out / "live-output.json").exists(), "live refusal wrote output")

        original = ROOT / "fixtures/builder/simple-shipment.json"
        source = self.out / "original-bundle.json"
        source.write_bytes(original.read_bytes())
        self.report["fixture_sha256"] = {str(original.relative_to(ROOT)): sha(original)}
        state = self.out / "review-state.sqlite"
        output, _, _ = self.cli("original-findings", "reconcile", source, state=state)
        findings = json.loads(output.read_text(encoding="utf-8"))["findings"]
        require(len(findings) == 3 and all(f["disputed_cents"] > 0 and not f["missing_facts"]
                                          for f in findings), "builder fixture did not reconcile")
        finding = next(f for f in findings if f["occurrence"]["line_id"] == "BUILDER-LH")
        report, _, _ = self.cli("review-report", "report", source, state=state)
        require("DRAFT, NOT SENT" in report.read_text(encoding="utf-8"), "inert report missing")
        output, _, _ = self.cli("prepare-review", "prepare-review", source, state=state,
                               finding_id=finding["finding_id"])
        binding = json.loads(output.read_text(encoding="utf-8"))
        intent = dict(binding, request_id="journey-provisional-dispute", action="dispute",
                      actor_id="builder-process-journey", actor_kind="agent_provisional",
                      approved_cents=finding["disputed_cents"])
        event = write_json(self.out / "provisional-review-intent.json", intent)
        self.cli("provisional-review", "review", source, state=state,
                 finding_id=finding["finding_id"], event=event)
        output, _, stderr = self.cli("refused-draft", "draft", source, state=state, expected=2,
                                    finding_id=finding["finding_id"])
        refusal = json.loads(stderr)
        require(refusal["status"] == "refused" and
                refusal["reason"] == "current matching human dispute required" and not output.exists(),
                "provisional dispute authorized a draft")
        output, _, _ = self.cli("prepare-before-source-change", "prepare-review", source,
                               state=state, finding_id=finding["finding_id"])
        stale = dict(json.loads(output.read_text(encoding="utf-8")), request_id="journey-stale-source",
                     action="escalate", actor_id="builder-process-journey", actor_kind="agent_provisional")
        stale_event = write_json(self.out / "stale-review-intent.json", stale)
        changed = json.loads(source.read_text(encoding="utf-8"))
        invoice = json.loads(changed["invoices"][0])
        invoice["lines"][0]["billed_cents"] += 100
        invoice["total_cents"] += 100
        # This is an explicitly authored new original builder source edition,
        # not reconstructed PDF facts or a replacement behind an old pointer.
        changed["invoices"] = [json.dumps(invoice, ensure_ascii=False) + "\n"]
        changed_source = write_json(self.out / "changed-original-bundle.json", changed)
        output, _, stderr = self.cli("stale-source-review", "review", changed_source, state=state,
                                    expected=2, finding_id=finding["finding_id"], event=stale_event)
        require("stale finding" in json.loads(stderr)["reason"] and not output.exists(),
                "changed original source did not invalidate review intent")

        unknown_original = ROOT / "fixtures/builder/unknown-reference.json"
        unknown = json.loads(unknown_original.read_text(encoding="utf-8"))
        simple = json.loads(source.read_text(encoding="utf-8"))
        # Keep every original inner document byte-for-byte. Supply the original
        # candidate shipment/rates so lack of a target cannot explain denial.
        for key in ("contracts", "shipments", "fuel_index"):
            unknown[key] = deepcopy(simple[key])
        unknown_source = write_json(self.out / "unknown-reference-bundle.json", unknown)
        self.report["fixture_sha256"][str(unknown_original.relative_to(ROOT))] = sha(unknown_original)
        link_state = self.out / "link-state.sqlite"
        output, _, _ = self.cli("unknown-before", "reconcile", unknown_source, state=link_state)
        row = json.loads(output.read_text(encoding="utf-8"))["findings"][0]
        require(row["expected_cents"] is None, "unknown reference auto-linked")
        output, _, _ = self.cli("prepare-link", "prepare-link", unknown_source, state=link_state,
                               occurrence_id=row["occurrence_id"])
        link_binding = json.loads(output.read_text(encoding="utf-8"))["binding"]
        target_id = json.loads(simple["shipments"][0])["shipment_id"]
        intent = dict(link_binding, request_id="journey-provisional-link", action="link",
                      target_shipment_id=target_id, actor_id="builder-process-journey",
                      actor_kind="agent_provisional")
        event = write_json(self.out / "provisional-link-intent.json", intent)
        self.cli("provisional-link", "link", unknown_source, state=link_state,
                 occurrence_id=row["occurrence_id"], event=event)
        output, _, _ = self.cli("unknown-after-provisional", "reconcile", unknown_source, state=link_state)
        require(json.loads(output.read_text(encoding="utf-8"))["findings"][0]["expected_cents"] is None,
                "provisional link resolved a target")
        output, _, _ = self.cli("prepare-unlink", "prepare-link", unknown_source, state=link_state,
                               occurrence_id=row["occurrence_id"])
        intent = dict(json.loads(output.read_text(encoding="utf-8"))["binding"],
                      request_id="journey-provisional-unlink", action="unlink",
                      actor_id="builder-process-journey", actor_kind="agent_provisional")
        event = write_json(self.out / "unlink-intent.json", intent)
        self.cli("unlink", "link", unknown_source, state=link_state,
                 occurrence_id=row["occurrence_id"], event=event)
        output, _, _ = self.cli("unknown-after-unlink", "reconcile", unknown_source, state=link_state)
        require(json.loads(output.read_text(encoding="utf-8"))["findings"][0]["expected_cents"] is None,
                "unlink authorized a target")
        output, _, stderr = self.cli("exact-link-priority", "prepare-link", source, state=link_state,
                                    expected=2, occurrence_id=finding["occurrence_id"])
        require("exact automatic link has priority" in json.loads(stderr)["reason"] and not output.exists(),
                "manual ruling could override exact automatic linkage")
        require(all(json.loads(p.read_text(encoding="utf-8"))["actor_kind"] == "agent_provisional"
                    for p in (event, stale_event, self.out / "provisional-review-intent.json",
                              self.out / "provisional-link-intent.json")), "actor attribution changed")

    def finish(self, failure=None):
        self.report.update(status="failed" if failure else "passed", failure=failure,
                           commands_run=len(self.report["steps"]),
                           expected_refusals=sum(s["expected_exit"] == 2 for s in self.report["steps"]))
        self.report["artifact_sha256"] = {str(p.relative_to(self.out)): sha(p)
            for p in sorted(self.out.rglob("*")) if p.is_file() and p.name != "journey.json"}
        self.save()
        print(json.dumps({"status": self.report["status"], "commands": self.report["commands_run"],
                          "artifact_root": str(self.out)}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, help="NEW directory outside OneDrive/source")
    parser.add_argument("--source-revision", required=True, help="externally verified merged Git commit")
    args = parser.parse_args(argv)
    require(re.fullmatch(r"[0-9a-f]{40}", args.source_revision), "exact source commit required")
    journey = Journey(args.artifacts, args.source_revision)
    try:
        journey.run()
    except Exception as exc:
        journey.finish(f"{type(exc).__name__}: {exc}")
        return 1
    journey.finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
