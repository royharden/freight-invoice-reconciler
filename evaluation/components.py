"""Source-only connected-component and split audit for externally supplied rows.

No dataset or labels are created. Near-duplicate identities must come from an
external audited manifest; this helper does not claim to discover semantic copies.
"""

from hashlib import sha256
import json


def connected_components(observations):
    """Join shipment ↔ invoice ↔ duplicate groups in carrier namespaces.

    Explicit document_sha256 and near_duplicate_case_id also join cases even
    across carriers, preventing supplied known copies from crossing splits.
    Returns occurrence-id → deterministic component-id without mutating inputs.
    """
    parent = {}

    def find(node):
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left, right):
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    occurrence_nodes = {}
    for row in observations:
        oid, carrier, invoice = row["occurrence_id"], row["carrier"], row["invoice_id"]
        if any(not isinstance(value, str) or not value for value in (oid, carrier, invoice)):
            raise ValueError("nonempty string occurrence/carrier/invoice identities required")
        if oid in occurrence_nodes:
            raise ValueError("duplicate occurrence identity")
        occurrence = ("occurrence", oid)
        occurrence_nodes[oid] = occurrence
        union(occurrence, ("invoice", carrier, invoice))
        for name in ("shipment_id", "duplicate_group_id"):
            value = row.get(name)
            if value is not None:
                if not isinstance(value, str) or not value:
                    raise ValueError(f"invalid {name}")
                union(occurrence, (name, carrier, value))
        for name in ("document_sha256", "near_duplicate_case_id"):
            value = row.get(name)
            if value is not None:
                if not isinstance(value, str) or not value:
                    raise ValueError(f"invalid {name}")
                union(occurrence, (name, value))
    groups = {}
    for node in parent:
        groups.setdefault(find(node), []).append(node)
    digest = {root: sha256(json.dumps(sorted(nodes), separators=(",", ":"), allow_nan=False).encode()).hexdigest()
              for root, nodes in groups.items()}
    return {oid: digest[find(node)] for oid, node in occurrence_nodes.items()}


def inspect_splits(observations):
    components = connected_components(observations)
    groups = {}
    for row in observations:
        if not isinstance(row.get("split"), str) or not row["split"]:
            raise ValueError("explicit split required on every row")
        groups.setdefault(components[row["occurrence_id"]], set()).add(row["split"])
    leakage = {component: sorted(splits) for component, splits in groups.items() if len(splits) > 1}
    return {"status": "fail" if leakage else "structural_pass", "leaking_components": leakage,
            "components": components,
            "limitation": "Completeness/authenticity of duplicate/document manifests needs independent review."}
