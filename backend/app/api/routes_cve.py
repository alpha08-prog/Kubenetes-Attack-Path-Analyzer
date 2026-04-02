"""
routes_cve.py — CVE Live Feed Endpoints
GET /api/cves/             → recent Kubernetes CVEs from NVD
GET /api/cves/search       → search CVEs by keyword
GET /api/cves/{cve_id}     → single CVE detail
GET /api/cves/node/{id}    → CVEs relevant to a specific node type
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.cve_service import (
    get_recent_cves,
    search_cves,
    get_cve_detail,
    get_cves_for_node_type,
    get_cve_summary,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
def recent_cves(
    keyword:  str = Query(default="kubernetes", description="Search keyword"),
    limit:    int = Query(default=15, ge=1, le=50),
    min_cvss: float = Query(default=0.0, ge=0.0, le=10.0, description="Minimum CVSS score filter"),
):
    """
    Fetch recent CVEs from NVD matching the keyword.
    Defaults to kubernetes — shown in the live CVE feed panel.
    Results are cached for 30 minutes to avoid hammering NVD.
    """
    try:
        result = get_recent_cves(keyword=keyword, limit=limit, min_cvss=min_cvss)
        return result
    except Exception as e:
        logger.error("CVE feed failed: %s", e)
        raise HTTPException(status_code=503, detail=f"NVD API unavailable: {str(e)}")


@router.get("/summary")
def cve_summary():
    """
    Returns aggregated CVE stats for the dashboard header card:
    critical count, high count, latest CVE date, most affected component.
    """
    try:
        return get_cve_summary()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/search")
def search(
    q:     str   = Query(..., description="Search term e.g. 'rbac', 'etcd', 'ingress'"),
    limit: int   = Query(default=10, ge=1, le=50),
):
    """
    Search NVD for CVEs matching a specific keyword.
    Used by the search bar in the CVE feed panel.
    """
    try:
        return search_cves(keyword=q, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/node/{node_type}")
def cves_for_node(node_type: str):
    """
    Returns CVEs relevant to a specific node type.
    Called when a user clicks a node in the graph — sidebar
    shows CVEs relevant to that resource type.

    node_type: pod | service_account | role | secret | database
    """
    try:
        return get_cves_for_node_type(node_type)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{cve_id}")
def cve_detail(cve_id: str):
    """
    Full detail for a single CVE.
    Called when user clicks a CVE in the feed panel.

    cve_id: e.g. CVE-2023-5528
    """
    try:
        result = get_cve_detail(cve_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"CVE '{cve_id}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))