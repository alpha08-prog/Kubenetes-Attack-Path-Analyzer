"""
prompt_templates.py - Groq prompt templates for report and simulation narration.
"""


NARRATOR_SYSTEM_PROMPT = """You are a senior Kubernetes security architect briefing C-level executives on cluster risks.

Your job: Translate raw attack graph data into a compelling security narrative that shows:
1. WHAT the risk is (clear, dramatic, no jargon)
2. WHY it matters (business impact, not technical detail)
3. HOW to fix it (specific, 1-3 action items per finding)

Your output must be a valid JSON array. No preamble, no markdown, only JSON.

Each finding must follow this schema:
{
  "id": "finding_001",
  "severity": "critical" | "high" | "medium" | "low",
  "category": "attack_path" | "blast_radius" | "privilege_escalation" | "critical_node",
  "title": "Human-readable risk headline (under 10 words)",
  "description": "2-3 sentences: What is the risk? Why does it matter? Use business language, not technical jargon.",
  "kill_chain": "Node-A → relation → Node-B → relation → Node-C (actual node names, if applicable, else null)",
  "affected_nodes": ["node-id-1", "node-id-2"],
  "recommendation": "Specific fix: Name the exact resource and the action (e.g., 'Remove admin role from web-sa')",
  "effort": "low" | "medium" | "high"
}

TONE RULES:
- Be dramatic: "Attackers can reach your billing database in 2 hops" not "Path exists with 2 edges"
- Focus on business impact: "Customer data exposure" not "Overly permissive RBAC"
- Every finding = one specific, not-optional action item
- Sort by severity first, then by blast radius size (bigger = worse)
- No hedging: say "will" not "could", "is" not "may be"
- Output ONLY the JSON array."""


def build_narrator_prompt(
    attack_path: dict | None,
    blast_radius: dict | None,
    cycles: dict | None,
    critical_nodes: dict | None,
    cluster_name: str = "nokia-telecom-cluster",
) -> str:
    """
    Build a narrative-focused prompt for Groq that emphasizes business impact and urgency.
    """
    sections = [
        f"Cluster: {cluster_name}",
        "Your job: Summarize the security risks in language a CEO would understand.",
        "",
    ]

    # EXECUTIVE SUMMARY
    risk_count = 0
    if attack_path and attack_path.get("found"):
        risk_count += 1
    if blast_radius and blast_radius.get("total_reachable", 0) > 10:
        risk_count += 1
    if cycles and cycles.get("cycle_count", 0) > 0:
        risk_count += 1

    sections.append(f"EXECUTIVE SUMMARY: {risk_count} critical security gaps found")
    sections.append("")

    # ATTACK PATHS - EMPHASIZE EASE OF EXPLOITATION
    if attack_path and attack_path.get("found"):
        hop_count = attack_path.get("hop_count", 0)
        source = attack_path.get('source_label', attack_path.get('source', 'unknown'))
        target = attack_path.get('target_label', attack_path.get('target', 'unknown'))

        urgency = "IMMEDIATE THREAT" if hop_count <= 2 else "HIGH RISK" if hop_count <= 3 else "MODERATE RISK"
        sections += [
            f"## RISK 1: Direct Attack Path ({urgency})",
            f"Attackers can reach '{target}' from '{source}' in just {hop_count} hop{'s' if hop_count != 1 else ''}.",
            f"This is {'extremely short and very dangerous' if hop_count <= 2 else 'concerning' if hop_count <= 3 else 'worth addressing'}.",
            "Attack sequence:",
        ]
        for i, hop in enumerate(attack_path.get("hops", []), 1):
            sections.append(
                f"  {i}. {hop['from_label']} --{hop['relation']}→ {hop['to_label']} (Risk: {hop['edge_risk']:.1f}/10)"
            )
        sections.append("")

    # BLAST RADIUS - EMPHASIZE SCALE OF DAMAGE
    if blast_radius and blast_radius.get("total_reachable", 0) > 0:
        total = blast_radius.get('total_reachable', 0)
        source = blast_radius.get('source_label', blast_radius.get('source', 'unknown'))
        sections += [
            f"## RISK 2: Blast Radius (Scale of Damage)",
            f"If '{source}' is compromised, attackers can reach {total} additional resources.",
            f"This is {'a massive blast radius - total cluster at risk' if total > 30 else 'a significant blast radius' if total > 10 else 'a limited blast radius'}.",
            "Resources at risk by distance:",
        ]
        for hop_num, nodes in sorted(blast_radius.get("zones", {}).items()):
            names = [n["label"] for n in nodes][:5]  # Top 5 per hop
            sections.append(f"  Hop {hop_num}: {', '.join(names)}" + (" ..." if len(nodes) > 5 else ""))
        sections.append("")

    # PRIVILEGE ESCALATION - EMPHASIZE UNFIXABILITY
    if cycles and cycles.get("cycle_count", 0) > 0:
        sections += [
            f"## RISK 3: Privilege Escalation Cycles",
            f"Found {cycles['cycle_count']} privilege loops - attackers can gain unlimited permissions.",
            "This is the most dangerous class of vulnerability (impossible to contain once exploited).",
            "Escalation routes:",
        ]
        for cycle in cycles.get("cycles", [])[:3]:  # Top 3 cycles
            sections.append(f"  • {cycle['chain']} (severity: {cycle['severity']})")
        sections.append("")

    # CRITICAL NODES - EMPHASIZE SINGLE POINTS OF FAILURE
    if critical_nodes and critical_nodes.get("nodes"):
        top_node = critical_nodes["nodes"][0] if critical_nodes["nodes"] else None
        if top_node:
            sections += [
                f"## CRITICAL CONTROL POINTS",
                f"The cluster has {len(critical_nodes['nodes'])} critical choke points.",
                f"Most critical: '{top_node['label']}' - removing it would break {top_node.get('combined_score', 0):.1f} attack paths.",
                "Other critical nodes:",
            ]
            for node in critical_nodes["nodes"][1:4]:
                sections.append(f"  • {node['label']} ({node['type']})")
        sections.append("")

    sections += [
        "## TASK",
        "Generate a JSON array of security findings that a CEO would understand.",
        "Each finding should answer: (1) What is the risk? (2) Why does it matter? (3) How do we fix it?",
        "Be dramatic, be specific, and be actionable. Sort by severity.",
    ]
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
