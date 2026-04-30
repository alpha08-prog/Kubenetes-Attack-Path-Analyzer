"""
routes_attack.py — Attack Path Endpoints
POST /api/attack/path      → shortest path between two nodes (Dijkstra)
POST /api/attack/all-paths → all simple paths between two nodes
GET  /api/attack/auto      → auto-detect and run best source→target pair
"""

from fastapi import APIRouter, HTTPException
from app.models.node import AttackPathRequest
from app.services.attack_service import (
    get_attack_path,
    get_all_attack_paths,
    get_auto_attack_path,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/path")
def attack_path(body: AttackPathRequest):
    """
    Find the shortest (easiest) attack path from source to target.
    Edge weights are based on CVE/misconfiguration risk scores.

    Body: { "source": "pod:default:web-server", "target": "database:default:billing-db" }
    """
    try:
        result = get_attack_path(body.source, body.target)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/all-paths")
def all_attack_paths(body: AttackPathRequest, max_paths: int = 5):
    """
    Returns all simple paths from source to target (up to max_paths).
    Shows judges that attackers have multiple routes to the same target.
    """
    try:
        result = get_all_attack_paths(body.source, body.target, max_paths=max_paths)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/auto")
def auto_attack_path():
    """
    Auto-detects the best entry point and sensitive target,
    then runs Dijkstra between them.
    Used by DemoMode.jsx — one click, no node selection needed.
    """
    try:
        result = get_auto_attack_path()
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))