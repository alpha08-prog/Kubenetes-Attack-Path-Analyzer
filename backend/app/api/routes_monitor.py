"""
routes_monitor.py — Real-time monitoring control endpoints + SSE stream.

Endpoints:
    POST /api/monitor/start           → Start K8s Watch API listener
    POST /api/monitor/stop            → Stop watcher gracefully
    GET  /api/monitor/status          → Current monitoring status
    GET  /api/monitor/events/stream   → SSE stream of GRAPH_UPDATE events
    GET  /api/monitor/events          → Recent events from DB (REST)
"""

import asyncio
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.database import get_recent_monitoring_events
from app.services.broadcast_service import (
    broadcast_graph_update,
    connected_client_count,
    register_client,
    unregister_client,
)
from app.services.fallback_poller import get_poller
from app.services.watch_service import get_watch_status, start_watching, stop_watching
from app.utils.logger import get_logger


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_kubectl() -> str | None:
    """Find kubectl or minikube kubectl on the current OS."""
    return shutil.which("kubectl.exe") or shutil.which("kubectl")


def _find_minikube() -> str | None:
    return shutil.which("minikube.exe") or shutil.which("minikube")


def _kubectl(*args: str, input: str | None = None, timeout: int = 30) -> tuple[int, str]:
    """
    Run a kubectl command and return (returncode, combined_output).
    Tries plain kubectl first, falls back to 'minikube kubectl --'.
    Never needs bash — pure subprocess.run, works on Windows/Linux/macOS.
    """
    kubectl = _find_kubectl()
    minikube = _find_minikube()

    for cmd in filter(None, [
        ([kubectl] + list(args))   if kubectl  else None,
        ([minikube, "kubectl", "--"] + list(args)) if minikube else None,
    ]):
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            input=input,
        )
        if result.returncode == 0 or kubectl:   # prefer kubectl result even on error
            return result.returncode, result.stdout
    return 1, "kubectl/minikube not found"


# ── Vulnerable scenario manifests ─────────────────────────────────────────────
# These YAML strings are applied directly via `kubectl apply -f -`.
# They create a real 4-hop attack path + privilege escalation cycle that
# the graph engine will detect and the diff engine will alert on.

_SCENARIO_NAMESPACE = "nokia-demo"

_SCENARIO_YAMLS = [
    # 1. Namespace
    """\
apiVersion: v1
kind: Namespace
metadata:
  name: nokia-demo
  labels:
    purpose: attack-path-demo
""",
    # 2. Overprivileged ServiceAccount
    """\
apiVersion: v1
kind: ServiceAccount
metadata:
  name: backend-sa
  namespace: nokia-demo
  annotations:
    note: "Intentionally overprivileged for demo"
""",
    # 3. ClusterRole with wildcard permissions (the dangerous role)
    """\
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: vuln-admin-role
  labels:
    demo: attack-path
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
""",
    # 4. ClusterRoleBinding: backend-sa gets wildcard cluster access
    """\
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: vuln-backend-binding
  labels:
    demo: attack-path
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: vuln-admin-role
subjects:
- kind: ServiceAccount
  name: backend-sa
  namespace: nokia-demo
""",
    # 5. Secret with plaintext-style DB credentials (high-value target)
    """\
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: nokia-demo
  labels:
    sensitivity: critical
type: Opaque
data:
  host: cG9zdGdyZXMuaW50ZXJuYWw=
  password: cGFzc3dvcmQxMjM=
  username: YWRtaW4=
""",
    # 6. Web-server pod (attacker entry point) bound to overprivileged SA
    """\
apiVersion: v1
kind: Pod
metadata:
  name: web-server
  namespace: nokia-demo
  labels:
    app: web-server
    exposure: external
spec:
  serviceAccountName: backend-sa
  containers:
  - name: web
    image: nginx:latest
    ports:
    - containerPort: 80
""",
    # 7. Billing-db pod (high-value target) consuming the secret
    """\
apiVersion: v1
kind: Pod
metadata:
  name: billing-db
  namespace: nokia-demo
  labels:
    app: billing-db
    sensitivity: critical
spec:
  containers:
  - name: db
    image: postgres:13
    env:
    - name: POSTGRES_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: password
""",
]

# Resources to delete on cleanup (in reverse dependency order)
_CLEANUP_COMMANDS = [
    ["delete", "pod",                "web-server",           "-n", _SCENARIO_NAMESPACE, "--ignore-not-found"],
    ["delete", "pod",                "billing-db",           "-n", _SCENARIO_NAMESPACE, "--ignore-not-found"],
    ["delete", "secret",             "db-credentials",       "-n", _SCENARIO_NAMESPACE, "--ignore-not-found"],
    ["delete", "clusterrolebinding", "vuln-backend-binding",                             "--ignore-not-found"],
    ["delete", "clusterrole",        "vuln-admin-role",                                  "--ignore-not-found"],
    ["delete", "serviceaccount",     "backend-sa",           "-n", _SCENARIO_NAMESPACE, "--ignore-not-found"],
    ["delete", "namespace",          _SCENARIO_NAMESPACE,                                "--ignore-not-found"],
]


def _deploy_scenario_sync() -> tuple[bool, str]:
    """
    Apply all scenario YAML manifests via kubectl apply -f -.
    Returns (success, combined_output).
    Runs synchronously — call from run_in_executor.
    """
    lines: list[str] = []
    success = True

    for i, yaml_doc in enumerate(_SCENARIO_YAMLS, 1):
        rc, out = _kubectl("apply", "-f", "-", input=yaml_doc)
        lines.append(out.strip())
        if rc != 0:
            lines.append(f"[step {i} FAILED — rc={rc}]")
            success = False
            break
        lines.append(f"[step {i} OK]")

    return success, "\n".join(lines)


def _cleanup_scenario_sync() -> tuple[bool, str]:
    """Delete all scenario resources. Returns (success, combined_output)."""
    lines: list[str] = []
    success = True
    for args in _CLEANUP_COMMANDS:
        rc, out = _kubectl(*args)
        lines.append(out.strip() or f"kubectl {' '.join(args[:3])} → rc={rc}")
        if rc != 0:
            success = False   # continue even on error to clean up as much as possible
    return success, "\n".join(lines)

logger = get_logger(__name__)

router = APIRouter()


# ── Control endpoints ──────────────────────────────────────────────────────────

@router.post("/start")
async def start_monitor():
    """
    Start real-time K8s Watch API monitoring.

    Connects to the current kubectl context and begins streaming events for:
    pods, serviceaccounts, secrets, roles, clusterroles,
    rolebindings, clusterrolebindings.

    Requires MOCK_MODE=false in .env.
    """
    if settings.MOCK_MODE:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot start monitoring in MOCK_MODE. "
                "Set MOCK_MODE=false in .env and restart the server."
            ),
        )

    try:
        result = await start_watching()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("start_monitor failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stop")
async def stop_monitor():
    """Stop real-time monitoring. Also stops fallback poller if active."""
    result = await stop_watching()

    # Also stop fallback poller if it's running
    poller = get_poller()
    if poller.running:
        await poller.stop()

    return result


@router.get("/status")
async def monitor_status():
    """
    Get current monitoring status.

    Returns:
        watching            — Is watch API active?
        fallback_active     — Is fallback polling active instead?
        uptime_seconds      — Seconds since watch started
        events_processed    — Total K8s events received
        pending_events      — Events waiting in debounce queue
        sse_clients         — Connected SSE frontend clients
        resources_watched   — Number of resource types watched
    """
    status = get_watch_status()
    status["sse_clients"] = connected_client_count()
    status["fallback_status"] = get_poller().get_status()
    return status


# ── SSE stream endpoint ────────────────────────────────────────────────────────

@router.get("/events/stream")
async def events_stream():
    """
    Server-Sent Events (SSE) stream of real-time graph updates.

    Connect from the frontend with::

        const es = new EventSource('/api/monitor/events/stream');
        es.onmessage = (e) => {
            const update = JSON.parse(e.data);
            // update.type === "GRAPH_UPDATE"
            // update.diff  === full DiffResult
            // update.run_id, update.timestamp
        };

    A ``: heartbeat`` comment is sent every 25 seconds to keep the
    connection alive through proxies / load balancers.
    """

    async def generator():
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        register_client(queue)

        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxy connections alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass  # Client disconnected
        except GeneratorExit:
            pass
        finally:
            unregister_client(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "Connection":       "keep-alive",
            "X-Accel-Buffering": "no",   # Disable nginx buffering
        },
    )


# ── Real analysis triggers ─────────────────────────────────────────────────────

def _record_snapshot(triggered_by: str) -> dict:
    """
    Rebuild graph from kubectl, run attack path + cycle detection,
    persist a history run with REAL values, and return a summary dict.

    Shared by record_baseline and the pre-deploy step in run_scenario
    so both sides of a diff are computed identically.
    """
    from app.services.ingestion_service import ingest_and_build
    from app.services.history_service import record_analysis_run

    summary = ingest_and_build()

    attack_paths = 0
    cycle_count  = 0
    try:
        from app.services.attack_service import get_auto_attack_path
        res = get_auto_attack_path()
        attack_paths = 1 if res.get("found") else 0
    except Exception:
        pass

    try:
        from app.services.analysis_service import get_cycles
        res = get_cycles()
        cycle_count = res.get("cycle_count", 0)
    except Exception:
        pass

    run_id = record_analysis_run(
        cluster_name=settings.CLUSTER_NAME,
        source=summary.get("source", "kubectl"),
        triggered_by=triggered_by,
        attack_paths=attack_paths,
        cycles=cycle_count,
    )
    return {
        "run_id":      run_id,
        "node_count":  summary["node_count"],
        "edge_count":  summary["edge_count"],
        "attack_paths": attack_paths,
        "cycles":      cycle_count,
    }


@router.post("/record-baseline")
async def record_baseline():
    """
    Snapshot the current live cluster state into history WITHOUT diffing.

    Runs attack path detection and cycle detection so the stored values
    are accurate — not zeros. This matters for the diff to report real deltas.

    Call this once before making cluster changes so a diff target exists.
    Requires MOCK_MODE=false and a reachable kubectl context.
    """
    if settings.MOCK_MODE:
        raise HTTPException(400, "MOCK_MODE=true — set MOCK_MODE=false to use real kubectl data.")

    try:
        loop = asyncio.get_running_loop()
        snap = await loop.run_in_executor(None, lambda: _record_snapshot("manual_baseline"))
        return {
            "status":       "baseline_recorded",
            "run_id":       snap["run_id"],
            "node_count":   snap["node_count"],
            "edge_count":   snap["edge_count"],
            "attack_paths": snap["attack_paths"],
            "cycles":       snap["cycles"],
            "message":      (
                f"Baseline captured — {snap['node_count']} nodes, "
                f"{snap['attack_paths']} attack path(s), {snap['cycles']} cycle(s). "
                "Now make cluster changes and click 'Trigger Analysis'."
            ),
        }
    except Exception as exc:
        logger.error("record_baseline failed: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc)) from exc


@router.post("/trigger-analysis")
async def trigger_analysis():
    """
    Immediately rebuild the attack graph from live kubectl data,
    diff against the previous run, and push a GRAPH_UPDATE via SSE if
    alert thresholds are exceeded.

    This is exactly what the Watch API does automatically — use this
    to force an instant analysis cycle without waiting for a K8s event.

    Requires MOCK_MODE=false and a reachable kubectl context.
    """
    if settings.MOCK_MODE:
        raise HTTPException(400, "MOCK_MODE=true — set MOCK_MODE=false to use real kubectl data.")

    try:
        from app.services.watch_decision_engine import analyze_changes

        # Run in a background task so the HTTP response returns immediately
        # while the rebuild + diff + broadcast happens asynchronously.
        asyncio.create_task(
            analyze_changes([{"k8s_event_type": "MANUAL_TRIGGER", "resource_type": "all", "object": None}]),
            name="manual-analysis",
        )

        return {
            "status":  "analysis_started",
            "message": (
                "Graph rebuild started from live kubectl data. "
                "If risk or paths changed vs the previous run, a GRAPH_UPDATE "
                "event will arrive in the Monitor tab within a few seconds."
            ),
            "sse_clients": connected_client_count(),
        }
    except Exception as exc:
        logger.error("trigger_analysis failed: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc)) from exc


@router.post("/run-scenario")
async def run_scenario(cleanup: bool = False):
    """
    Deploy (or remove) the vulnerable scenario on the live minikube cluster.

    cleanup=false — apply 7 misconfigured K8s manifests that create:
        • web-server pod (entry point) → backend-sa (overprivileged SA)
        • backend-sa → vuln-admin-role (wildcard ClusterRole)
        • vuln-admin-role → db-credentials secret (sensitive data)
        • billing-db pod (high-value target consuming the secret)
        This creates a real 4-hop attack path the graph engine will detect.

    cleanup=true — delete all scenario resources from the cluster.

    Why no bash?
    ------------
    kubectl apply -f - (stdin YAML) is called directly via subprocess.run,
    exactly like ingestion_service.py fetches data. No bash, no shell path
    translation — works identically on Windows, Linux and macOS.

    Requires: minikube running, kubectl or minikube in PATH, MOCK_MODE=false.
    """
    if settings.MOCK_MODE:
        raise HTTPException(400, "MOCK_MODE=true — set MOCK_MODE=false to use a real cluster.")

    if not _find_kubectl() and not _find_minikube():
        raise HTTPException(
            400,
            "kubectl / minikube not found. Make sure minikube is running and "
            "kubectl is in your PATH, then restart the backend.",
        )

    try:
        loop = asyncio.get_running_loop()

        if cleanup:
            # ── Cleanup ───────────────────────────────────────────────────────
            success, output = await loop.run_in_executor(None, _cleanup_scenario_sync)
            logger.info("Scenario cleanup done (success=%s)", success)
            return {
                "status":  "cleanup_done" if success else "cleanup_partial",
                "output":  output,
                "message": "Scenario resources removed from the cluster." if success
                           else "Some resources could not be deleted — see output for details.",
            }

        # ── Deploy ────────────────────────────────────────────────────────────

        # 1. Record baseline BEFORE deploying — uses _record_snapshot so
        #    attack_paths and cycles are REAL values (not zeros), ensuring
        #    the post-deploy diff reports accurate deltas.
        snap       = await loop.run_in_executor(None, lambda: _record_snapshot("scenario_baseline"))
        run_id_pre = snap["run_id"]
        logger.info(
            "Scenario baseline: run=%s nodes=%d paths=%d cycles=%d",
            run_id_pre, snap["node_count"], snap["attack_paths"], snap["cycles"],
        )

        # 2. Apply all 7 manifests via `kubectl apply -f -` (pure Python, no bash)
        success, output = await loop.run_in_executor(None, _deploy_scenario_sync)

        if not success:
            logger.error("Scenario deploy failed:\n%s", output)
            return {
                "status":  "error",
                "output":  output,
                "message": (
                    "One or more manifests failed to apply. "
                    "Make sure minikube is running (`minikube start`) "
                    "and kubectl is authenticated. See output for the exact error."
                ),
            }

        logger.info("Scenario deployed successfully")

        # 3. Trigger real analysis → rebuilds graph from kubectl → diffs → SSE event
        from app.services.watch_decision_engine import analyze_changes
        asyncio.create_task(
            analyze_changes([{
                "k8s_event_type": "SCENARIO_DEPLOYED",
                "resource_type":  "all",
                "object":         None,
            }]),
            name="scenario-analysis",
        )

        return {
            "status":  "deployed",
            "output":  output,
            "message": (
                "7 vulnerable resources deployed. "
                "Real graph analysis started — the Monitor tab will receive "
                "a GRAPH_UPDATE event in a few seconds with the actual risk delta."
            ),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("run_scenario failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc


# ── Recent events (REST) ───────────────────────────────────────────────────────

@router.post("/demo-flow")
async def demo_full_flow():
    """
    One-click demo: record baseline → simulate risk increase → broadcast SSE.

    Perfect for judges demo. Shows:
    1. Baseline snapshot created
    2. Risk change detected
    3. SSE event broadcast
    4. B3 temporal diff shows changes

    Works in both MOCK_MODE and real K8s. Auto-reloads graph if empty.
    """
    try:
        from app.core.graph_builder import get_graph
        from app.services.snapshot_service import create_snapshot, diff_snapshots, get_latest_snapshot_id
        from app.services.ingestion_service import fetch_and_build

        # Auto-reload graph if empty
        try:
            G = get_graph()
        except RuntimeError:
            logger.info("Demo: Graph empty, auto-reloading from K8s...")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, fetch_and_build)
            G = get_graph()

        # Step 1: Record baseline if none exists
        latest_id = get_latest_snapshot_id()
        if not latest_id:
            baseline = create_snapshot(G, trigger_source="demo", trigger_desc="Demo baseline")
            latest_id = baseline.snapshot_id
            logger.info("Demo: Baseline recorded %s", latest_id[:8])

        # Step 2: Increase risk on all pods (simulate vulnerability discovered)
        for node_id in list(G.nodes()):
            if G.nodes[node_id].get("type") == "pod":
                current_risk = G.nodes[node_id].get("risk", 0.0)
                G.nodes[node_id]["risk"] = min(10.0, current_risk + 2.5)

        # Step 3: Create new snapshot with changes
        new_snap = create_snapshot(G, trigger_source="demo", trigger_desc="Demo after risk increase")
        logger.info("Demo: Change snapshot created %s", new_snap.snapshot_id[:8])

        # Step 4: Diff to get changes
        diff = diff_snapshots(latest_id, new_snap.snapshot_id)
        logger.info("Demo: Diff complete - risk_delta=%.2f", diff.overall_risk_delta)

        # Step 5: Broadcast SSE event
        from app.services.broadcast_service import broadcast_graph_update
        broadcast_graph_update({
            "event": "DEMO_CHANGE",
            "severity": diff.severity,
            "risk_delta": diff.overall_risk_delta,
            "message": f"Demo change: Risk increased by {diff.overall_risk_delta:.1f}. Check B3 for snapshot diff."
        })
        logger.info("Demo: SSE broadcast sent")

        return {
            "status": "success",
            "baseline_snapshot_id": latest_id[:8],
            "change_snapshot_id": new_snap.snapshot_id[:8],
            "risk_delta": diff.overall_risk_delta,
            "severity": diff.severity,
            "message": (
                f"Demo Complete!\n"
                f"Baseline: {latest_id[:8]}\n"
                f"After Change: {new_snap.snapshot_id[:8]}\n"
                f"Risk Delta: {diff.overall_risk_delta:.1f}\n"
                f"Severity: {diff.severity}"
            )
        }
    except Exception as exc:
        logger.error("demo_full_flow failed: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc)) from exc


@router.post("/simulate-change")
async def simulate_graph_change(action: str = "increase_risk", node_type: str = "pod"):
    """
    Simulate a graph change for DEMO purposes (works in MOCK_MODE).

    Actions:
    - increase_risk: Increase risk scores of nodes (simulating vulnerability discovered)
    - add_nodes: Add new nodes to graph (simulating new deployments)
    - add_edges: Add new edges (simulating new RBAC bindings)

    This triggers a graph update → diff against previous → SSE broadcast.
    Perfect for judges demo without needing a real K8s cluster.
    """
    try:
        from app.core.graph_builder import get_graph, ingest_and_build
        from app.services.analysis_service import get_full_analysis
        from app.services.snapshot_service import create_snapshot, diff_snapshots, get_latest_snapshot_id

        # Get current graph
        G = get_graph()
        latest_id = get_latest_snapshot_id()

        if action == "increase_risk":
            # Increase risk scores of all pods to simulate vulnerabilities found
            for node_id in list(G.nodes()):
                if G.nodes[node_id].get("type") == "pod":
                    current_risk = G.nodes[node_id].get("risk", 0.0)
                    G.nodes[node_id]["risk"] = min(10.0, current_risk + 2.0)
            logger.info("Simulated risk increase for all pods")

        elif action == "add_nodes":
            # Add a new high-risk pod node with RBAC bindings
            import uuid
            new_pod_id = f"pod:demo:rogue-{str(uuid.uuid4())[:8]}"
            G.add_node(
                new_pod_id,
                label="rogue-pod",
                type="pod",
                risk=8.5,
                namespace="demo",
            )
            # Connect it to admin role (privilege escalation path)
            for node_id in G.nodes():
                if "admin" in node_id.lower():
                    G.add_edge(new_pod_id, node_id, relation="uses", risk=8.0)
            logger.info("Simulated new high-risk pod with admin bindings")

        elif action == "add_edges":
            # Add new privilege escalation edges
            pods = [n for n in G.nodes() if G.nodes[n].get("type") == "pod"]
            roles = [n for n in G.nodes() if G.nodes[n].get("type") == "role"]
            if pods and roles:
                G.add_edge(pods[0], roles[-1], relation="escalates_to", risk=7.5)
                logger.info("Simulated new privilege escalation edge")

        # Create snapshot of modified graph
        new_snapshot = create_snapshot(G, trigger_source="demo", trigger_desc=f"Simulated {action}")

        # Diff against latest snapshot
        if latest_id:
            diff = diff_snapshots(latest_id, new_snapshot.snapshot_id)
            logger.info(
                "Simulated change: %d new nodes, %d new paths, severity=%s",
                diff.nodes_added_count,
                diff.new_attack_paths_count,
                diff.severity,
            )

            # Broadcast SSE event
            if diff.nodes_added_count > 0 or diff.new_attack_paths_count > 0:
                from app.services.broadcast_service import broadcast_graph_update
                broadcast_graph_update({
                    "event": "GRAPH_CHANGE",
                    "severity": diff.severity,
                    "changes": {
                        "nodes_added": diff.nodes_added_count,
                        "new_paths": diff.new_attack_paths_count,
                    }
                })
                logger.info("SSE broadcast sent for simulated change")

        return {
            "status": "change_simulated",
            "action": action,
            "snapshot_id": new_snapshot.snapshot_id,
            "message": f"Graph {action} simulated. Check Monitor tab for SSE event and B3 for snapshot diff."
        }

    except Exception as exc:
        logger.error("simulate_graph_change failed: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc)) from exc


@router.get("/events")
def recent_events(limit: int = 20):
    """
    Return the most recent monitoring events from the database.

    Useful for building an audit log / events timeline in the UI.
    """
    events = get_recent_monitoring_events(
        cluster_name=settings.CLUSTER_NAME, limit=limit
    )
    return {"events": events, "count": len(events)}
