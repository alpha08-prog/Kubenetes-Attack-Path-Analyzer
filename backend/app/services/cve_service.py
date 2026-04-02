"""
cve_service.py — CVE Feed Service
Fetches and caches CVE data from the NVD API.
Free, no API key required.

NVD API: https://services.nvd.nist.gov/rest/json/cves/2.0
Rate limit: 5 requests per 30 seconds (unauthenticated)
We cache results for 30 minutes to stay well within limits.
"""

import time
import httpx
from app.utils.helpers import severity_label, utc_now
from app.utils.logger import get_logger

logger = get_logger(__name__)

NVD_BASE    = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_TIMEOUT = 15

# ── In-memory cache ───────────────────────────────────────────────────────────
# { cache_key: {"data": [...], "fetched_at": timestamp} }
_cache: dict = {}
CACHE_TTL = 30 * 60  # 30 minutes


# ── Known K8s CVEs (offline fallback) ─────────────────────────────────────────
KNOWN_K8S_CVES = [
    {
        "cve_id":      "CVE-2023-5528",
        "title":       "Windows node privilege escalation via Kubernetes",
        "description": "Kubernetes allows a user to launch containers that can "
                       "gain admin privileges on Windows nodes via a specially "
                       "crafted storage class.",
        "cvss_score":  8.8,
        "severity":    "high",
        "published":   "2023-11-14",
        "component":   "kubelet",
        "vector":      "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "references":  ["https://github.com/kubernetes/kubernetes/issues/121197"],
        "source":      "fallback",
    },
    {
        "cve_id":      "CVE-2023-2431",
        "title":       "Bypass of seccomp profile enforcement in Kubernetes",
        "description": "A security issue was discovered in Kubernetes where a "
                       "user that can create pods on Windows nodes may be able "
                       "to escalate to admin privileges on those nodes.",
        "cvss_score":  7.8,
        "severity":    "high",
        "published":   "2023-06-16",
        "component":   "pod security",
        "vector":      "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        "references":  ["https://github.com/kubernetes/kubernetes/issues/118690"],
        "source":      "fallback",
    },
    {
        "cve_id":      "CVE-2022-3172",
        "title":       "Aggregated API server SSRF in kube-apiserver",
        "description": "A security issue was discovered in kube-apiserver where "
                       "an aggregated API server can redirect client traffic to "
                       "any URL, bypassing authentication.",
        "cvss_score":  7.4,
        "severity":    "high",
        "published":   "2022-11-10",
        "component":   "kube-apiserver",
        "vector":      "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N",
        "references":  ["https://github.com/kubernetes/kubernetes/issues/112513"],
        "source":      "fallback",
    },
    {
        "cve_id":      "CVE-2021-25741",
        "title":       "Symlink exchange attack allowing host filesystem access",
        "description": "A user may be able to create a container with subPath "
                       "volume mounts to access files and directories outside "
                       "the volume, including on the host filesystem.",
        "cvss_score":  8.1,
        "severity":    "high",
        "published":   "2021-09-20",
        "component":   "kubelet",
        "vector":      "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
        "references":  ["https://github.com/kubernetes/kubernetes/issues/104980"],
        "source":      "fallback",
    },
    {
        "cve_id":      "CVE-2020-8559",
        "title":       "Privilege escalation from compromised node to cluster",
        "description": "The Kubernetes kube-apiserver is vulnerable to an "
                       "unvalidated redirect that could allow an attacker who "
                       "can intercept API requests to escalate privileges.",
        "cvss_score":  6.8,
        "severity":    "medium",
        "published":   "2020-07-22",
        "component":   "kube-apiserver",
        "vector":      "CVSS:3.1/AV:N/AC:H/PR:H/UI:R/S:U/C:H/I:H/A:H",
        "references":  ["https://github.com/kubernetes/kubernetes/issues/92914"],
        "source":      "fallback",
    },
    {
        "cve_id":      "CVE-2019-11247",
        "title":       "RBAC bypass for cluster-scoped custom resources",
        "description": "The Kubernetes API server allows access to custom "
                       "resources via wrong scope. A user may access cluster-"
                       "scoped resources via a namespaced role binding.",
        "cvss_score":  8.1,
        "severity":    "high",
        "published":   "2019-08-29",
        "component":   "kube-apiserver",
        "vector":      "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
        "references":  ["https://github.com/kubernetes/kubernetes/issues/80983"],
        "source":      "fallback",
    },
    {
        "cve_id":      "CVE-2018-1002105",
        "title":       "Privilege escalation via aggregated API endpoint",
        "description": "A flaw in the Kubernetes API server allows specially "
                       "crafted requests to establish a connection through "
                       "the Kubernetes API server to backend servers, then "
                       "send arbitrary requests with elevated privileges.",
        "cvss_score":  9.8,
        "severity":    "critical",
        "published":   "2018-12-05",
        "component":   "kube-apiserver",
        "vector":      "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "references":  ["https://github.com/kubernetes/kubernetes/issues/71411"],
        "source":      "fallback",
    },
]

# Keywords to search per node type
NODE_TYPE_KEYWORDS = {
    "pod":             "kubernetes pod container escape",
    "service_account": "kubernetes service account token rbac",
    "role":            "kubernetes rbac privilege escalation",
    "secret":          "kubernetes secret exposure credentials",
    "database":        "kubernetes etcd database unauthorized access",
}


# ── Main service functions ────────────────────────────────────────────────────

def get_recent_cves(
    keyword:  str   = "kubernetes",
    limit:    int   = 15,
    min_cvss: float = 0.0,
) -> dict:
    """
    Fetch recent CVEs from NVD. Cached for 30 minutes.
    Falls back to KNOWN_K8S_CVES if NVD is unreachable.
    """
    cache_key = f"recent:{keyword}:{limit}:{min_cvss}"
    cached = _get_cache(cache_key)
    if cached:
        logger.debug("CVE cache hit for key: %s", cache_key)
        return cached

    logger.info("Fetching CVEs from NVD: keyword=%s limit=%d", keyword, limit)

    try:
        cves = _fetch_from_nvd(keyword=keyword, limit=limit)
        if min_cvss > 0:
            cves = [c for c in cves if (c.get("cvss_score") or 0) >= min_cvss]

        result = {
            "source":       "nvd_live",
            "keyword":      keyword,
            "fetched_at":   utc_now(),
            "total":        len(cves),
            "cves":         cves,
        }
        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.warning("NVD fetch failed (%s) — using fallback data", e)
        fallback = [c for c in KNOWN_K8S_CVES
                    if (c.get("cvss_score") or 0) >= min_cvss][:limit]
        return {
            "source":     "offline_fallback",
            "keyword":    keyword,
            "fetched_at": utc_now(),
            "total":      len(fallback),
            "cves":       fallback,
            "warning":    "NVD API unavailable — showing cached known CVEs",
        }


def search_cves(keyword: str, limit: int = 10) -> dict:
    """Search NVD for a specific keyword."""
    return get_recent_cves(keyword=keyword, limit=limit)


def get_cve_detail(cve_id: str) -> dict | None:
    """Fetch full detail for a single CVE."""
    # Check fallback list first
    for cve in KNOWN_K8S_CVES:
        if cve["cve_id"].upper() == cve_id.upper():
            return cve

    # Try NVD live
    cache_key = f"detail:{cve_id}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        url  = f"{NVD_BASE}?cveId={cve_id.upper()}"
        data = _nvd_get(url)
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return None

        result = _parse_cve(vulns[0].get("cve", {}))
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("CVE detail fetch failed for %s: %s", cve_id, e)
        return None


def get_cves_for_node_type(node_type: str) -> dict:
    """
    Returns CVEs relevant to a specific K8s resource type.
    Called from NodeSidebar when a node is clicked.
    """
    keyword = NODE_TYPE_KEYWORDS.get(node_type, "kubernetes")
    result  = get_recent_cves(keyword=keyword, limit=8)
    result["node_type"] = node_type
    return result


def get_cve_summary() -> dict:
    """
    Aggregated stats for the dashboard header CVE card.
    """
    cache_key = "summary"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        all_cves = get_recent_cves(keyword="kubernetes", limit=50)
        cves     = all_cves.get("cves", [])
    except Exception:
        cves = KNOWN_K8S_CVES

    critical = sum(1 for c in cves if (c.get("cvss_score") or 0) >= 9.0)
    high     = sum(1 for c in cves if 7.0 <= (c.get("cvss_score") or 0) < 9.0)
    medium   = sum(1 for c in cves if 4.0 <= (c.get("cvss_score") or 0) < 7.0)

    latest = max(
        (c.get("published", "") for c in cves if c.get("published")),
        default="unknown",
    )

    components = {}
    for c in cves:
        comp = c.get("component", "unknown")
        components[comp] = components.get(comp, 0) + 1
    top_component = max(components, key=components.get) if components else "unknown"

    result = {
        "total":         len(cves),
        "critical":      critical,
        "high":          high,
        "medium":        medium,
        "latest_date":   latest,
        "top_component": top_component,
        "fetched_at":    utc_now(),
    }
    _set_cache(cache_key, result)
    return result


# ── NVD API helpers ───────────────────────────────────────────────────────────

def _fetch_from_nvd(keyword: str, limit: int) -> list:
    url  = f"{NVD_BASE}?keywordSearch={keyword}&resultsPerPage={min(limit, 50)}"
    data = _nvd_get(url)
    return [
        _parse_cve(v.get("cve", {}))
        for v in data.get("vulnerabilities", [])
    ]


def _nvd_get(url: str) -> dict:
    with httpx.Client(timeout=NVD_TIMEOUT) as client:
        resp = client.get(url, headers={"User-Agent": "AttackPathAnalyzer/1.0"})
    if resp.status_code != 200:
        raise RuntimeError(f"NVD returned HTTP {resp.status_code}")
    return resp.json()


def _parse_cve(cve: dict) -> dict:
    cve_id = cve.get("id", "unknown")

    # Description
    desc = next(
        (d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"),
        "No description available",
    )

    # CVSS score — try v3.1 → v3.0 → v2
    score  = None
    vector = None
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key, [])
        if entries:
            data   = entries[0].get("cvssData", {})
            score  = data.get("baseScore")
            vector = data.get("vectorString")
            break

    # References
    refs = [r.get("url", "") for r in cve.get("references", [])[:3]]

    # Infer affected component from description
    component = _infer_component(desc)

    return {
        "cve_id":      cve_id,
        "title":       _make_title(cve_id, desc),
        "description": desc[:300] + ("..." if len(desc) > 300 else ""),
        "cvss_score":  score,
        "severity":    severity_label(score or 0.0),
        "published":   cve.get("published", "")[:10],
        "modified":    cve.get("lastModified", "")[:10],
        "component":   component,
        "vector":      vector,
        "references":  refs,
        "source":      "nvd_live",
    }


def _make_title(cve_id: str, desc: str) -> str:
    """Extract a short title from the description."""
    first_sentence = desc.split(".")[0]
    if len(first_sentence) <= 80:
        return first_sentence
    return first_sentence[:77] + "..."


def _infer_component(desc: str) -> str:
    """Guess the affected component from CVE description text."""
    desc_lower = desc.lower()
    components = {
        "kube-apiserver":   ["kube-apiserver", "api server", "apiserver"],
        "kubelet":          ["kubelet"],
        "etcd":             ["etcd"],
        "kubectl":          ["kubectl"],
        "ingress":          ["ingress"],
        "rbac":             ["rbac", "role-based", "rolebinding"],
        "pod security":     ["seccomp", "pod security", "psp"],
        "container runtime":["containerd", "docker", "cri-o", "runc"],
        "network policy":   ["network policy", "cni"],
        "secrets":          ["secret", "credential"],
    }
    for component, keywords in components.items():
        if any(kw in desc_lower for kw in keywords):
            return component
    return "kubernetes"


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _get_cache(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL:
        return entry["data"]
    return None


def _set_cache(key: str, data: dict) -> None:
    _cache[key] = {"data": data, "ts": time.time()}