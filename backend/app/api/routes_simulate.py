"""
routes_simulate.py — Simulation Endpoints
POST /api/simulate/remove  → remove a node, show before/after impact
GET  /api/simulate/auto    → auto-run simulation on top critical node
"""

from fastapi import APIRouter, HTTPException
from app.models.node import SimulateRequest
from app.services.simulator_service import simulate_removal, get_top_removal_candidates
from app.core.graph_builder import get_graph, find_entry_points, find_sensitive_targets
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/remove")
def simulate_node_removal(body: SimulateRequest):
    """
    Remove node_id from the graph and measure impact:
    - How many attack paths are broken?
    - Does the shortest path still exist? At what new cost?
    - How many privilege escalation cycles are broken?
    - AI narration of what this means operationally.

    Used by the 'Simulate removal' button in CriticalNodeTable.jsx
    and SimulationDelta.jsx.

    Body: {
        "node_id": "service_account:default:backend-sa",
        "source":  "pod:default:web-server",
        "target":  "database:default:billing-db"
    }
    """
    try:
        result = simulate_removal(body.node_id, body.source, body.target)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/auto")
def auto_simulate():
    """
    Auto-detect the top critical node and simulate its removal
    between the auto-detected source and target.
    Used by DemoMode.jsx to run the full demo in one click.
    """
    try:
        G = get_graph()
        entries = find_entry_points(G)
        targets = find_sensitive_targets(G)

        if not entries or not targets:
            raise HTTPException(
                status_code=404,
                detail="Could not auto-detect entry points or targets"
            )

        source = sorted(entries, key=lambda n: G.nodes[n].get("risk", 0), reverse=True)[0]
        target = sorted(targets, key=lambda n: G.nodes[n].get("risk", 0), reverse=True)[0]

        candidates = get_top_removal_candidates(source, target, top_n=1)
        if not candidates:
            raise HTTPException(
                status_code=404,
                detail="No removal candidates found for this path"
            )

        top_node = candidates[0]["node_id"]
        result = simulate_removal(top_node, source, target)
        result["auto_detected"] = True
        return result

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))