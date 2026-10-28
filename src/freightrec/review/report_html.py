"""Self-contained escaped review report; input never becomes executable markup."""
from html import escape
from .log import canonical


def report_html(findings):
    body = "".join("<pre>" + escape(canonical(finding), quote=True) + "</pre>" for finding in findings)
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            '<title>Freight review — DRAFT, NOT SENT</title><h1>DRAFT, NOT SENT</h1>'
            '<p>Minutes not measured. Findings require current human approval for draft export.</p>'
            + body + '</html>\n')
