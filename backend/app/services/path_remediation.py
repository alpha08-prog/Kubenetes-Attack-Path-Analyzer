"""
path_remediation.py — Actionable, path-specific remediation lines (rubric 2.3).
"""

from __future__ import annotations

from typing import Any


def generate_path_remediation_lines(hops: list[dict[str, Any]]) -> list[str]:
    """
    Produce specific remediation strings from hop dicts (relation, labels, types, cve).
    Dedupes while preserving order.
    """
    remediations: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        if line not in seen:
            seen.add(line)
            remediations.append(line)

    for hop in hops:
        relation = (hop.get("relation") or "").lower()
        from_label = hop.get("from_label") or hop.get("from") or ""
        to_label = hop.get("to_label") or hop.get("to") or ""
        from_type = (hop.get("from_type") or "").lower()
        to_type = (hop.get("to_type") or "").lower()
        cve = hop.get("cve")

        if cve:
            add(f"Patch {cve} on {from_label}: upgrade container image immediately.")

        if relation == "bound-to" and to_type in ("role", "cluster_role"):
            add(f"Remove RoleBinding: revoke '{to_label}' from identity tied to '{from_label}'.")

        if relation in ("can-read", "can-exec", "can-exec-on"):
            add(f"Restrict RBAC: remove '{relation}' on '{to_label}' for '{from_label}'.")

        if relation == "falls-back-to" and to_type == "service_account":
            add(
                f"Disable default ServiceAccount automount on workload '{from_label}' "
                "(automountServiceAccountToken: false)."
            )

        if relation == "grants-access-to" and to_type in ("database", "namespace"):
            add(f"Rotate credentials in '{from_label}' and restrict secret read access.")

        if relation == "admin-grant":
            add(f"Break privilege cycle: revoke admin-grant from '{from_label}' to '{to_label}'.")

        if relation == "impersonates":
            add(f"Remove impersonation: prevent '{from_label}' from using '{to_label}'.")

        if relation == "uses" and to_type == "service_account":
            add(
                f"Tighten workload identity: run '{from_label}' with a dedicated least-privilege "
                f"ServiceAccount instead of overusing '{to_label}'."
            )

        if relation == "shares-service-account":
            add(
                f"Isolate co-located pods: split '{from_label}' and '{to_label}' onto separate "
                "ServiceAccounts to block lateral movement."
            )

        if relation in ("reads", "mounts"):
            add(f"Limit data access: block '{relation}' from '{from_label}' to '{to_label}' where not required.")

        if relation in ("routes-to", "calls", "reaches"):
            add(f"Reduce exposure: restrict '{relation}' from '{from_label}' to '{to_label}' (network policy / ingress).")

        if relation == "exposes-endpoint":
            add(f"Remove or firewall sensitive endpoint exposure from '{from_label}' to '{to_label}'.")

        if relation == "deployed-in":
            add(f"Relocate or harden '{from_label}': avoid sensitive '{to_label}' placement.")

    if not remediations:
        add("Apply least-privilege RBAC: audit the full path and remove unnecessary bindings.")

    return remediations


def generate_cycle_remediation_lines(
    cycle_node_ids: list[str],
    G: Any,
) -> list[str]:
    """Remediation for a directed cycle (e.g. mutual admin-grant between services)."""
    lines: list[str] = []
    n = len(cycle_node_ids)
    for i in range(n):
        a = cycle_node_ids[i]
        b = cycle_node_ids[(i + 1) % n]
        if not G.has_edge(a, b):
            continue
        rel = (G[a][b].get("relation") or "").lower()
        la = G.nodes[a].get("label", a)
        lb = G.nodes[b].get("label", b)
        if rel == "admin-grant":
            lines.append(f"Break cycle: revoke admin-grant from '{la}' to '{lb}'.")
    if not lines:
        labs = [G.nodes[x].get("label", x) for x in cycle_node_ids]
        lines.append(
            f"Break cycle among {', '.join(labs)}: remove the weakest mutual permission edge.",
        )
    return lines
