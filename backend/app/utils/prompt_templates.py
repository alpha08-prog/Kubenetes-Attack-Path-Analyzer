"""
prompt_templates.py - Groq prompt templates for report and simulation narration.
"""


NARRATOR_SYSTEM_PROMPT = """You are a senior Kubernetes security analyst at a Nokia infrastructure team.
You analyze attack graph data from a Kubernetes cluster and generate clear, actionable security findings.

Your output must always be a valid JSON array of findings. No preamble, no markdown, no explanation outside the JSON.

Each finding must follow this exact schema:
{
  "id": "finding_001",
  "severity": "critical" | "high" | "medium" | "low",
  "category": "attack_path" | "blast_radius" | "privilege_escalation" | "critical_node",
  "title": "Short title under 10 words",
  "description": "One sentence explaining what the risk is and why it matters.",
  "kill_chain": "Node-A -> relation -> Node-B -> relation -> Node-C (if applicable, else null)",
  "affected_nodes": ["node-id-1", "node-id-2"],
  "recommendation": "One specific, actionable fix. Name the exact resource to change.",
  "effort": "low" | "medium" | "high"
}

Rules:
- Write for a Nokia security engineer, not a developer. Be direct and specific.
- Never use vague language like "consider" or "might". Say exactly what to do.
- Kill chains must name actual node labels from the data, not generic names.
- Severity follows CVSS v3: critical=9+, high=7-8.9, medium=4-6.9, low=0.1-3.9.
- Sort findings by severity descending (critical first).
- Output ONLY the JSON array. No other text."""


def build_narrator_prompt(
    attack_path: dict | None,
    blast_radius: dict | None,
    cycles: dict | None,
    critical_nodes: dict | None,
    cluster_name: str = "nokia-telecom-cluster",
) -> str:
    """
    Build the user prompt for Groq by injecting algorithm results.
    """
    sections = [
        f"Cluster: {cluster_name}",
        "Analysis timestamp: see response metadata",
        "",
    ]

    if attack_path and attack_path.get("found"):
        sections += [
            "## Shortest Attack Path (Dijkstra)",
            f"Source: {attack_path.get('source_label', attack_path.get('source'))}",
            f"Target: {attack_path.get('target_label', attack_path.get('target'))}",
            f"Hops: {attack_path.get('hop_count')}",
            f"Exploitability cost: {attack_path.get('total_cost')} (lower = easier)",
            "Hop-by-hop:",
        ]
        for hop in attack_path.get("hops", []):
            sections.append(
                f"  Step {hop['step']}: {hop['from_label']} --[{hop['relation']}]--> "
                f"{hop['to_label']} (type={hop['to_type']}, risk={hop['edge_risk']})"
            )
        sections.append("")

    if blast_radius and blast_radius.get("total_reachable", 0) > 0:
        sections += [
            "## Blast Radius (BFS)",
            f"Compromised node: {blast_radius.get('source_label', blast_radius.get('source'))}",
            f"Total reachable: {blast_radius.get('total_reachable')} nodes within {blast_radius.get('max_hops')} hops",
        ]
        for hop_num, nodes in sorted(blast_radius.get("zones", {}).items()):
            names = [n["label"] for n in nodes]
            sections.append(f"  Hop {hop_num}: {', '.join(names)}")
        sections.append("")

    if cycles and cycles.get("cycle_count", 0) > 0:
        sections += [f"## Privilege Escalation Cycles (DFS) - {cycles['cycle_count']} detected"]
        for cycle in cycles.get("cycles", []):
            sections.append(
                f"  [{cycle['severity'].upper()}] {cycle['chain']} "
                f"(length={cycle['length']}, max_risk={cycle['max_risk']})"
            )
        sections.append("")

    if critical_nodes and critical_nodes.get("nodes"):
        sections += [
            "## Critical Nodes (Betweenness Centrality)",
            "Top nodes by combined centrality + risk score:",
        ]
        for node in critical_nodes["nodes"][:5]:
            sections.append(
                f"  #{node['rank']} {node['label']} ({node['type']}) - "
                f"centrality={node['centrality_score']}, risk={node['risk']}, "
                f"combined={node['combined_score']}"
            )
        sections.append("")

    sections.append(
        "Generate a JSON array of security findings based on the above data. "
        "Be specific, name actual nodes, and give concrete remediation steps."
    )
    return "\n".join(sections)


def build_report_header(cluster_name: str, finding_count: int, timestamp: str) -> dict:
    return {
        "report_title": "Attack Path Analysis Report",
        "cluster": cluster_name,
        "generated_at": timestamp,
        "tool": "Attack Path Analyzer - Nokia Hackathon 2024",
        "total_findings": finding_count,
        "model_used": "groq",
    }


FALLBACK_FINDINGS = [
    {
        "id": "finding_fallback_001",
        "severity": "high",
        "category": "attack_path",
        "title": "Groq API unavailable - manual review required",
        "description": (
            "The AI narration service could not be reached. "
            "Raw algorithm results are available in the analysis endpoints."
        ),
        "kill_chain": None,
        "affected_nodes": [],
        "recommendation": "Check GROQ_API_KEY in .env and retry /api/report. You can also call /api/ai/health.",
        "effort": "low",
    }
]


def build_simulation_prompt(simulation_result: dict) -> str:
    node = simulation_result.get("node_label", simulation_result.get("node_removed"))
    broken = simulation_result.get("paths_broken", 0)
    before = simulation_result.get("paths_before", 0)
    impact = simulation_result.get("impact", "unknown")

    return (
        f"A security engineer is considering removing or restricting node '{node}' "
        f"from the Kubernetes cluster.\n\n"
        f"Simulation result:\n"
        f"  Attack paths before removal: {before}\n"
        f"  Attack paths after removal: {simulation_result.get('paths_after', 0)}\n"
        f"  Paths broken: {broken}\n"
        f"  Impact classification: {impact}\n\n"
        f"In 2-3 sentences, explain: (1) whether this removal is worth doing, "
        f"(2) any side effects or operational risks, "
        f"(3) the specific RBAC or network policy change to implement it safely. "
        f"Be direct and specific."
    )
