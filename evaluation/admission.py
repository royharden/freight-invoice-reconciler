"""Structural checks on externally supplied admission records, never builder GO.

No world, oracle, gold, independent human evidence or custody data is created here.
Authenticity, independence and scientific adequacy require actual H/O/J/human
review; a well-shaped JSON object does not establish any of them.
"""

REQUIRED_EVIDENCE = (
    "provenance_rights_human_review", "roy_license_disposition", "independent_roles",
    "oracle_allowed_inputs", "world_independent_review", "schema_answer_field_isolation",
    "spec_ambiguities_closed", "spec_freeze", "human_worked_audit_36",
    "oracle_worked_vectors", "oracle_mutants", "pilot_disagreements_adjudicated",
    "pilot_20_agreement_audits", "pilot_80_disjoint_components", "trap_coverage_18",
    "frozen_a0_a1", "baseline_nontriviality", "finite_analytic_sizing",
    "sizing_policy_freeze", "source_lineage", "custody_commitments",
)


def inspect_external_admission(evidence):
    """Returns missing/invalid items and ALWAYS leaves the release gate pending."""
    problems = []
    if not isinstance(evidence, dict):
        return {"status": "pending", "go": False, "problems": ["external evidence mapping absent"]}
    for name in REQUIRED_EVIDENCE:
        record = evidence.get(name)
        if not isinstance(record, dict):
            problems.append(f"{name}: missing")
            continue
        digest = record.get("sha256")
        if (record.get("status") != "pass" or not isinstance(digest, str) or len(digest) != 64 or
                any(char not in "0123456789abcdef" for char in digest) or
                not record.get("issuer_session") or not record.get("artifact")):
            problems.append(f"{name}: missing passing disposition or exact provenance")
    roles = evidence.get("role_sessions")
    if not isinstance(roles, dict) or set(roles) != {"B", "H", "O", "J"}:
        problems.append("four actual B/H/O/J session identities required")
    elif any(not isinstance(value, str) or not value for value in roles.values()) or len(set(roles.values())) != 4:
        problems.append("B/H/O/J must be four distinct actual sessions")
    return {"status": "pending" if problems else "structurally_complete_requires_external_J_review",
            "go": False, "problems": problems,
            "reason": "Builder tooling cannot authenticate receipts or grant independent admission.",
            "required_next": "Actual J and human disposition, with Roy's prerequisite decisions."}
