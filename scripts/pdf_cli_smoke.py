"""One actual native-PDF CLI report process, with retained byte/pointer evidence."""

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


class FindingBlocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.current = []
        self.findings = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.active, self.current = True, []

    def handle_data(self, data):
        if self.active:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "pre" and self.active:
            self.findings.append(json.loads("".join(self.current)))
            self.active = False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_revision):
        raise ValueError("exact execution candidate required")
    out = Path(args.artifacts).resolve()
    if out.is_relative_to(ROOT) or any("onedrive" in part.casefold() for part in out.parts):
        raise ValueError("new artifact root must be outside source and OneDrive")
    out.mkdir(parents=True, exist_ok=False)
    (out / "tmp").mkdir()
    source = out / "original-pdf-bundle.json"
    source.write_bytes((ROOT / "fixtures/builder/native-pdf-bundle.json").read_bytes())
    report = out / "findings-report.html"
    env = {"PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "TEMP": str(out / "tmp"), "TMP": str(out / "tmp")}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    command = [sys.executable, "-B", "-m", "freightrec.cli", "report", "--builder-only",
               "--input", str(source), "--out", str(report)]
    receipt = {"status": "running", "data_origin": "builder_non_independent",
               "source_revision": args.source_revision, "command": command, "cwd": str(ROOT),
               "python_version": sys.version, "environment_names": sorted(env),
               "cli_process_count": 1, "actor": "none", "human_session": "not_measured",
               "external_spend_usd": 0, "placeholders": [], "runner_sha256": digest(Path(__file__)),
               "source_sha256": {str(p.relative_to(ROOT)): digest(p)
                                  for p in sorted((ROOT / "src").rglob("*.py"))}}
    try:
        try:
            child = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=30, check=False)
            code, stdout, stderr = child.returncode, child.stdout, child.stderr
        except subprocess.TimeoutExpired as exc:
            code, stdout, stderr = None, exc.stdout or b"", exc.stderr or b""
        (out / "cli.stdout.bin").write_bytes(stdout)
        (out / "cli.stderr.bin").write_bytes(stderr)
        receipt.update(actual_exit=code, stdout_sha256=digest(out / "cli.stdout.bin"),
                       stderr_sha256=digest(out / "cli.stderr.bin"), stderr_bytes=len(stderr))
        if code != 0:
            raise ValueError("PDF CLI process refused or timed out; retained raw output")
        # Replay the SAME original descriptor through the canonical guarded
        # hydration only to resolve reported pointers, never as rebuilt JSON.
        from freightrec import bundles as codec
        if Path(codec.__file__).resolve() != ROOT / "src/freightrec/bundles.py":
            raise ValueError("unexpected original-bundle codec checkout")
        bundle = json.loads(source.read_text(encoding="utf-8"))
        raw_pdf = codec.decode_pdf_descriptor(bundle["invoices"][0])
        raw_sha = sha256(raw_pdf).hexdigest()
        resolver, documents = codec.hydrate_original_bundle(bundle)
        blocks = FindingBlocks()
        blocks.feed(report.read_text(encoding="utf-8"))
        if len(blocks.findings) != 3 or any(f["missing_facts"] for f in blocks.findings):
            raise ValueError("PDF report findings incomplete")
        count, profiles = 0, set()
        for finding in blocks.findings:
            pointers = [p for p in finding["evidence_pointers"] if p["source_sha256"] == raw_sha]
            if not pointers:
                raise ValueError("finding lost original PDF evidence")
            for pointer in finding["evidence_pointers"]:
                if not resolver.resolve(pointer):
                    raise ValueError("empty or unresolved evidence quote")
            for pointer in pointers:
                if not pointer["parser_profile"].endswith("-isolated-v2"):
                    raise ValueError("unexpected PDF parser edition")
                profiles.add(pointer["parser_profile"])
                count += 1
        if documents["invoices"][0]["source_sha256"] != raw_sha:
            raise ValueError("source archive lost raw PDF hash")
        receipt.update(status="passed", findings=len(blocks.findings), raw_pdf_sha256=raw_sha,
                       resolved_pdf_pointer_occurrences=count, parser_profiles=sorted(profiles),
                       hydration_source=str(Path(codec.__file__).resolve()))
    except Exception as exc:
        receipt.update(status="failed", failure=f"{type(exc).__name__}: {exc}")
    receipt["artifact_sha256"] = {p.name: digest(p) for p in sorted(out.iterdir()) if p.is_file()}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n",
                                      encoding="utf-8", newline="\n")
    print(json.dumps({"status": receipt["status"], "artifact_root": str(out)}))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
