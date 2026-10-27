"""No transport: export escaped local draft HTML after current approval checks."""
from html import escape
from pathlib import Path

from ..review.log import ReviewError, canonical, cents, digest, text


def export_draft(finding, decision, source_resolver, out_dir, *, decision_log=None):
    """A DecisionLog is mandatory: a caller-supplied dict cannot prove currency."""
    if decision_log is None:
        raise ReviewError("decision_log required for current persisted approval")
    with decision_log.authorize_export(finding, decision) as persisted_decision:
        billed = cents(finding.get("billed_cents"), "billed_cents")
        expected = cents(finding.get("expected_cents"), "expected_cents")
        disputed = cents(finding.get("disputed_cents"), "disputed_cents")
        approved = cents(persisted_decision.get("approved_cents"), "approved_cents")
        text(finding.get("occurrence_id"), "occurrence_id")
        text(finding.get("clause_id"), "clause_id")
        if (finding.get("verdict") not in {"overcharge", "unsupported"} or
                disputed <= 0 or disputed != billed - expected or
                disputed != approved or finding.get("missing_facts") or
                (finding.get("verdict") == "unsupported" and expected != 0)):
            raise ReviewError("invalid or changed dispute amount/facts")
        pointers = finding.get("evidence_pointers")
        if not isinstance(pointers, list) or not pointers:
            raise ReviewError("verified evidence pointers required")
        quotes = []
        for pointer in pointers:
            quote = source_resolver.resolve(pointer)
            if not isinstance(quote, str) or not quote:
                raise ReviewError("source pointer did not resolve to exact text")
            quotes.append({"pointer": pointer, "quote": quote})
        payload = {"label": "DRAFT, NOT SENT", "finding": finding, "decision": persisted_decision,
                   "evidence": quotes, "review_time": "minutes not measured"}
        rendered = ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
                    '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
                    'base-uri &#39;none&#39;; form-action &#39;none&#39;">'
                    "<title>DRAFT, NOT SENT</title><h1>DRAFT, NOT SENT</h1>"
                    "<p>Local draft only. Minutes not measured. Actor IDs are local attribution.</p><pre>"
                    + escape(canonical(payload), quote=True) + "</pre></html>\n")
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        path = target / ("draft-" + digest(payload) + ".html")
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(rendered)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != rendered:
                raise ReviewError("existing draft content mismatch") from None
        return path
