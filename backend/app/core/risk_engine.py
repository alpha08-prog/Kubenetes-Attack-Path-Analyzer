"""
risk_engine.py — Risk Scoring Engine
Enriches graph nodes and edges with real CVE severity scores
from the NVD (National Vulnerability Database) API.
Falls back to heuristic scoring when NVD is unavailable.

NVD API is free, no auth needed:
https://services.nvd.nist.gov/rest/json/cves/2.0
"""

import httpx
from app.utils.helpers import risk_to_weight, severity_label
from app.utils.logger import get_logger

logger = get_logger(__name__)

NVD_API_BASE  = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_TIMEOUT   = 10   # seconds — skip enrichment if NVD is slow


# ─── Known Kubernetes CVEs ────────────────────────────────────────────────────
# Hardcoded fallback scores for the most common K8s CVEs.
# These are used when NVD API is unavailable (demo day safety net).

KNOWN_K8S_CVES: dict[str, float] = {
    "CVE-2018-1002105": 9.8,   # k8s API server privilege escalation
    "CVE-2019-11247":   8.1,   # RBAC cluster-scoped resources bypass
    "CVE-2019-11249":   6.5,   # kubectl cp symlink attack
    "CVE-2019-9946":    7.5,   # CNI portmap privilege escalation
    "CVE-2020-8558":    8.8,   # node localhost bypass via network
    "CVE-2020-8559":    6.8,   # privilege escalation via redirect
    "CVE-2021-25741":   8.1,   # symlink exchange attack
    "CVE-2022-3172":    7.4,   # aggregated API server SSRF
    "CVE-2023-2431":    7.8,   # seccomp bypass via hostProcess
    "CVE-2023-5528":    8.8,   # Windows node privilege escalation
}


# ─── Main enrichment entry point ──────────────────────────────────────────────

def enrich_graph_risks(nodes: list, edges: list) -> tuple[list, list]:
    """
    Enrich node and edge risk scores using CVE data.
    Called by graph_builder.py after parse_cluster_data().

    Steps:
    1. Apply heuristic base scores (already set by parser.py)
    2. Check node metadata for known CVEs and upgrade risk if higher
    3. Recompute edge weights from final risk scores

    Returns updated (nodes, edges) lists.
    """
    enriched_nodes = [_enrich_node(n) for n in nodes]
    enriched_edges = [_recompute_edge_weight(e) for e in edges]

    high_risk = [n for n in enriched_nodes if n["risk"] >= 7.0]
    logger.info(
        "Risk enrichment complete — %d/%d nodes are high risk (>=7.0)",
        len(high_risk), len(enriched_nodes),
    )
    return enriched_nodes, enriched_edges


def _enrich_node(node: dict) -> dict:
    """
    Check if a node's metadata contains known CVE IDs.
    If a CVE score is higher than the heuristic score, upgrade it.
    """
    cves = node.get("metadata", {}).get("cves", [])
    if not cves:
        return node

    max_cve_score = 0.0
    for cve_id in cves:
        score = KNOWN_K8S_CVES.get(cve_id)
        if score is not None:
            max_cve_score = max(max_cve_score, score)
        else:
            # Try NVD live lookup for unknown CVEs
            score = _fetch_cvss_score(cve_id)
            if score is not None:
                max_cve_score = max(max_cve_score, score)

    if max_cve_score > node["risk"]:
        logger.info(
            "CVE upgrade: %s risk %s → %s (CVE score)",
            node["label"], node["risk"], max_cve_score,
        )
        node = {**node, "risk": max_cve_score}

    return node


def _recompute_edge_weight(edge: dict) -> dict:
    """Recompute Dijkstra weight from final risk score."""
    return {**edge, "weight": risk_to_weight(edge["risk"])}


# ─── NVD API lookup ───────────────────────────────────────────────────────────

def _fetch_cvss_score(cve_id: str) -> float | None:
    """
    Fetch CVSS v3.1 base score for a CVE from NVD.
    Returns None on any failure — never blocks the graph build.

    NVD API is free, no API key required.
    Rate limit: 5 requests per 30s without key, 50 with key.
    """
    try:
        url = f"{NVD_API_BASE}?cveId={cve_id}"
        with httpx.Client(timeout=NVD_TIMEOUT) as client:
            response = client.get(url)

        if response.status_code != 200:
            return None

        data = response.json()
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return None

        cve_data = vulns[0].get("cve", {})
        metrics  = cve_data.get("metrics", {})

        # Try CVSS v3.1 first, then v3.0, then v2
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(key, [])
            if entries:
                score = entries[0].get("cvssData", {}).get("baseScore")
                if score is not None:
                    logger.debug("NVD: %s → CVSS %.1f", cve_id, score)
                    return float(score)

        return None

    except Exception as e:
        logger.debug("NVD lookup failed for %s: %s", cve_id, e)
        return None


# ─── Bulk CVE lookup ──────────────────────────────────────────────────────────

def fetch_kubernetes_cves(keyword: str = "kubernetes", max_results: int = 20) -> list:
    """
    Fetch recent Kubernetes CVEs from NVD for display in the dashboard.
    Used by the optional CVE feed panel — not required for core function.

    Returns list of { cve_id, description, cvss_score, severity, published }
    """
    try:
        url = f"{NVD_API_BASE}?keywordSearch={keyword}&resultsPerPage={max_results}"
        with httpx.Client(timeout=NVD_TIMEOUT) as client:
            response = client.get(url)

        if response.status_code != 200:
            logger.warning("NVD bulk fetch failed: HTTP %d", response.status_code)
            return []

        results = []
        for vuln in response.json().get("vulnerabilities", []):
            cve      = vuln.get("cve", {})
            cve_id   = cve.get("id", "unknown")
            desc     = next(
                (d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"),
                "No description available",
            )
            metrics  = cve.get("metrics", {})
            score    = None
            for key in ("cvssMetricV31", "cvssMetricV30"):
                entries = metrics.get(key, [])
                if entries:
                    score = entries[0].get("cvssData", {}).get("baseScore")
                    break

            results.append({
                "cve_id":      cve_id,
                "description": desc[:200] + "..." if len(desc) > 200 else desc,
                "cvss_score":  score,
                "severity":    severity_label(score or 0.0),
                "published":   cve.get("published", ""),
            })

        logger.info("Fetched %d CVEs from NVD for keyword '%s'", len(results), keyword)
        return results

    except Exception as e:
        logger.error("NVD bulk fetch error: %s", e)
        return []


# ─── Heuristic scorer (offline fallback) ─────────────────────────────────────

def heuristic_edge_risk(relation: str, source_type: str, target_type: str) -> float:
    """
    Assign a risk score to an edge purely from its relation type
    and the types of nodes it connects.
    Used when no CVE data is available — ensures every edge has a weight.

    Higher score = attacker finds this edge easier/more valuable.
    """
    base = {
        ("pod",             "service_account"): 5.0,
        ("service_account", "role"):            6.0,
        ("role",            "secret"):          7.5,
        ("role",            "database"):        8.5,
        ("secret",          "database"):        9.0,
        ("user",            "role"):            6.5,
        ("service_account", "secret"):          7.0,
        ("pod",             "secret"):          7.0,
        ("pod",             "database"):        8.0,
    }.get((source_type, target_type), 4.0)

    # Boost for high-privilege relations
    if relation in ("cluster-admin", "admin"):
        base = min(base + 2.0, 10.0)
    elif relation == "bound-to" and target_type == "role":
        base = min(base + 0.5, 10.0)

    return round(base, 1)