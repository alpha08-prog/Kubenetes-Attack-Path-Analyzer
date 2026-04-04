# Backend Agent Implementation Guide: Real-Time K8s Monitoring

## Executive Summary

This document guides you through implementing **real-time Kubernetes cluster monitoring** using the K8s Watch API. The system will detect security changes (new attack paths, privilege escalation cycles, risk increase) within **2 seconds** and alert via Slack + auto-refresh the frontend.

**Target Outcome:**
- K8s resources streamed to backend via Watch API
- Graph updates within 2-5 seconds of cluster change
- Frontend auto-refreshes with diff visualization
- Alerts sent for: risk increase, new attack paths, privilege escalation cycles

**Estimated Implementation Time:** 4 weeks (Milestone 1-4)

---

## PREREQUISITE CONTEXT

### Current Architecture (Already Implemented)

Your existing system has these pieces that we'll integrate with:

1. **Data Ingestion** (`ingestion_service.py`)
   - Function: `ingest_and_build()`
   - Takes raw K8s data → builds NetworkX graph
   - Reuse this for watch-triggered updates

2. **Graph Diffing** (`graph_diff_service.py`)
   - Function: `diff_runs(run_id_before, run_id_after)`
   - Compares two snapshots, returns risk delta
   - Will use this to decide if alert is needed

3. **History Recording** (`history_service.py`)
   - Function: `record_analysis_run()`
   - Saves snapshots to SQLite
   - We'll call this after each watch-triggered update

4. **Slack Alerting** (`slack_service.py`)
   - Function: `send_critical_alert(findings, cluster_name)`
   - Reuse for watch-based alerts

### What You're Building

A bridge between K8s Watch API and the existing analysis pipeline:

```
K8s Watch API Stream
    ↓ [NEW: watch_service.py]
Debounce Events (2 sec window)
    ↓ [NEW: event_debouncer.py]
Detect Significance (is change dangerous?)
    ↓ [EXISTING: ingest_and_build()]
Rebuild Graph from new cluster state
    ↓ [EXISTING: diff_runs()]
Compare with previous state
    ↓ [NEW: alert_decision_engine]
Decide: is this worth alerting on?
    ↓ [EXISTING: send_critical_alert() + record_analysis_run()]
Slack Alert + SSE to Frontend + Save to History
```

---

## PHASE 1: ENVIRONMENT & DEPENDENCIES (Day 1-2)

### Step 1A: Update requirements.txt

**File:** `backend/requirements.txt`

Add these lines at the end:
```
kubernetes>=30.0.0
python-watch>=4.0.0
aiodns>=3.1.0
```

**Rationale:**
- `kubernetes`: Official K8s Python client (Watch API, stream events)
- `python-watch`: Alternative watch library (fallback)
- `aiodns`: Async DNS resolution (better performance)

**Command to verify:**
```bash
cd backend
pip install -r requirements.txt
# Should complete without errors
python -c "import kubernetes; print(kubernetes.__version__)"  # ✓ 30.0.0 or higher
```

### Step 1B: Update Configuration

**File:** `backend/app/config.py`

Add these fields to the `Settings` class after existing fields:

```python
# Real-time monitoring
ENABLE_WATCH_API: bool = Field(
    default=True,
    description="Enable K8s Watch API for real-time monitoring"
)
WATCH_DEBOUNCE_MS: int = Field(
    default=2000,
    description="Debounce window for K8s events (ms). Prevents analysis thrashing."
)
ALERT_RISK_DELTA_THRESHOLD: float = Field(
    default=1.0,
    description="Risk score delta to trigger alert (e.g., 6.2 → 7.5 = delta 1.3 > 1.0 → alert)"
)
ALERT_ON_NEW_PATHS: bool = Field(
    default=True,
    description="Send alert when new attack paths detected"
)
ALERT_ON_NEW_CYCLES: bool = Field(
    default=True,
    description="Send alert when privilege escalation cycles detected"
)
WATCH_RECONNECT_DELAY_SEC: int = Field(
    default=5,
    description="Seconds to wait before reconnecting watch if it fails"
)
FALLBACK_POLL_INTERVAL_SEC: int = Field(
    default=300,
    description="Fallback polling interval if Watch API unavailable (seconds)"
)
```

**Also add to config.py before Settings class:**
```python
from enum import Enum

class MonitoringMode(str, Enum):
    """How to monitor cluster changes"""
    WATCH_API = "watch"      # Real-time K8s Watch API
    POLLING = "polling"      # Fallback: periodic kubectl
    DISABLED = "disabled"    # No monitoring
```

### Step 1C: Environment Variables

**File:** `backend/app/.env`

Add (or verify they exist):
```
ENABLE_WATCH_API=true
WATCH_DEBOUNCE_MS=2000
ALERT_RISK_DELTA_THRESHOLD=1.0
ALERT_ON_NEW_PATHS=true
ALERT_ON_NEW_CYCLES=true
WATCH_RECONNECT_DELAY_SEC=5
FALLBACK_POLL_INTERVAL_SEC=300
```

---

## PHASE 2: DATABASE SCHEMA (Day 2-3)

### Step 2A: Create Migration for Monitoring Tables

**File:** `backend/app/core/database.py`

Find the `init_db()` function. Add these table creations to it:

```python
def init_db():
    """Initialize all database tables."""
    with get_conn() as conn:
        # ... existing table creations ...

        # NEW: Monitoring Events Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                severity TEXT,
                summary TEXT,
                details TEXT,
                triggered_alerts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
            )
        """)

        # NEW: Monitoring Configuration
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_config (
                cluster_name TEXT PRIMARY KEY,
                watching BOOLEAN DEFAULT 0,
                watch_started_at TIMESTAMP,
                watch_stopped_at TIMESTAMP,
                alert_threshold_risk_delta FLOAT DEFAULT 1.0,
                alert_on_new_paths BOOLEAN DEFAULT 1,
                alert_on_new_cycles BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # NEW: Event Queue (for debouncing)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                k8s_event_type TEXT,
                resource_type TEXT,
                resource_id TEXT,
                resource_json TEXT,
                queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)

        # Indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_monitoring_events_run_id ON monitoring_events(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_monitoring_events_severity ON monitoring_events(severity)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_monitoring_events_created_at ON monitoring_events(created_at)")

        conn.commit()
```

### Step 2B: Add Helper Functions to Database Module

```python
def record_monitoring_event(
    run_id: str,
    event_type: str,  # RESOURCE_ADDED, RISK_INCREASED, NEW_PATH, NEW_CYCLE
    resource_type: str = None,
    resource_id: str = None,
    severity: str = None,
    summary: str = None,
    details: dict = None,
    triggered_alerts: list = None
) -> None:
    """Record a monitoring event to the database."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO monitoring_events
            (run_id, event_type, resource_type, resource_id, severity, summary, details, triggered_alerts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, event_type, resource_type, resource_id, severity, summary,
            json.dumps(details) if details else None,
            ','.join(triggered_alerts) if triggered_alerts else None
        ))
        conn.commit()

def get_monitoring_config(cluster_name: str) -> dict:
    """Get monitoring configuration for a cluster."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM monitoring_config WHERE cluster_name = ?",
            (cluster_name,)
        ).fetchone()
        return dict(row) if row else None

def update_monitoring_config(cluster_name: str, **kwargs) -> None:
    """Update monitoring configuration."""
    with get_conn() as conn:
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [cluster_name]
        conn.execute(f"UPDATE monitoring_config SET {fields} WHERE cluster_name = ?", values)
        conn.commit()
```

---

## PHASE 3: WATCH SERVICE IMPLEMENTATION (Days 3-7)

### Step 3A: Create Watch Service

**File:** `backend/app/services/watch_service.py`

This is the **core component**. It:
1. Connects to K8s Watch API
2. Receives events (pod created, role deleted, etc)
3. Filters significant changes
4. Triggers graph updates

```python
"""
watch_service.py — Real-time Kubernetes cluster monitoring
Watches K8s resources and triggers graph updates on changes
"""

import asyncio
import json
from typing import Optional, List, Dict, Any
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from datetime import datetime
from app.utils.logger import get_logger
from app.config import settings
from app.services.ingestion_service import ingest_and_build
from app.services.graph_diff_service import diff_runs, diff_latest_two
from app.services.history_service import record_analysis_run, get_run_history
from app.core.database import (
    get_conn, record_monitoring_event, update_monitoring_config,
    get_monitoring_config
)
from app.services.slack_service import send_critical_alert
from app.services.event_debouncer import EventDebouncer

logger = get_logger(__name__)


class KubernetesWatcher:
    """
    Watches Kubernetes cluster for resource changes using the Watch API.
    Debounces events and triggers analysis when significant changes detected.
    """

    def __init__(self):
        self.watching = False
        self.v1_client = None
        self.watch_thread = None
        self.last_analysis_run_id = None
        self.debouncer = EventDebouncer(debounce_ms=settings.WATCH_DEBOUNCE_MS)
        self.resource_watchers = [
            ('v1', 'pods'),
            ('v1', 'serviceaccounts'),
            ('v1', 'secrets'),
            ('v1', 'rolebindings'),
            ('rbac.authorization.k8s.io/v1', 'roles'),
            ('rbac.authorization.k8s.io/v1', 'clusterroles'),
            ('rbac.authorization.k8s.io/v1', 'clusterrolebindings'),
        ]

    async def start(self) -> Dict[str, Any]:
        """
        Start watching K8s cluster for changes.

        Returns:
            {
                "status": "watching",
                "resources": 7,
                "message": "Watching 7 resource types"
            }
        """
        if self.watching:
            return {"status": "already_watching", "message": "Watch already active"}

        try:
            # Load K8s config from kubeconfig or in-cluster
            config.load_incluster_config()  # If running in K8s pod
        except Exception:
            try:
                config.load_kube_config()  # Use local kubeconfig
            except Exception as e:
                logger.error(f"Failed to load K8s config: {e}")
                raise ValueError("Cannot connect to Kubernetes cluster. Check kubeconfig or in-cluster config.")

        self.v1_client = client.CoreV1Api()
        self.watching = True

        # Record monitoring started
        update_monitoring_config(
            cluster_name=settings.CLUSTER_NAME,
            watching=True,
            watch_started_at=datetime.utcnow().isoformat()
        )

        logger.info(f"Started watching {len(self.resource_watchers)} K8s resource types")

        # Start background watch task
        asyncio.create_task(self._watch_all_resources())

        return {
            "status": "watching",
            "resources": len(self.resource_watchers),
            "message": f"Watching {len(self.resource_watchers)} resource types"
        }

    async def stop(self) -> Dict[str, Any]:
        """Stop watching K8s cluster."""
        self.watching = False
        update_monitoring_config(
            cluster_name=settings.CLUSTER_NAME,
            watching=False,
            watch_stopped_at=datetime.utcnow().isoformat()
        )
        logger.info("Stopped K8s watch")
        return {"status": "stopped", "message": "Watch stopped"}

    async def _watch_all_resources(self):
        """Main watch loop. Streams events from K8s API."""
        while self.watching:
            try:
                for api_version, resource_type in self.resource_watchers:
                    if not self.watching:
                        break
                    await self._watch_resource_type(api_version, resource_type)
            except Exception as e:
                logger.error(f"Watch loop error: {e}")
                if self.watching:
                    # Reconnect after delay
                    await asyncio.sleep(settings.WATCH_RECONNECT_DELAY_SEC)
                    continue

    async def _watch_resource_type(self, api_version: str, resource_type: str):
        """Watch a single resource type (e.g., pods, roles)."""
        try:
            w = watch.Watch()

            if api_version == 'v1':
                stream = w.stream(
                    self.v1_client.list_namespaced_custom_object,
                    group=api_version.split('/')[0] if '/' in api_version else '',
                    version=api_version,
                    plural=resource_type,
                    namespace='default',  # TODO: make configurable
                    timeout_seconds=30
                )
            else:
                # For RBAC resources
                api = client.RbacAuthorizationV1Api()
                stream = w.stream(
                    getattr(api, f'list_{"cluster" if "cluster" in resource_type else "namespaced"}_{resource_type}'),
                    namespace=None if 'cluster' in resource_type else 'default'
                )

            async for event in stream:
                if not self.watching:
                    break

                event_type = event['type']  # ADDED, MODIFIED, DELETED
                resource = event['object']

                # Queue event for debouncing
                await self.debouncer.queue_event({
                    'k8s_event_type': event_type,
                    'resource_type': resource_type,
                    'resource': resource,
                    'api_version': api_version
                })

        except Exception as e:
            logger.error(f"Error watching {resource_type}: {e}")

    async def get_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        config = get_monitoring_config(settings.CLUSTER_NAME)

        if not config:
            return {
                "watching": False,
                "message": "No monitoring session active"
            }

        return {
            "watching": config.get('watching', False),
            "started_at": config.get('watch_started_at'),
            "cluster": settings.CLUSTER_NAME,
            "debounce_ms": settings.WATCH_DEBOUNCE_MS,
            "alert_threshold": settings.ALERT_RISK_DELTA_THRESHOLD,
            "resources_watched": len(self.resource_watchers)
        }


# Module-level singleton
_watcher: Optional[KubernetesWatcher] = None


def get_watcher() -> KubernetesWatcher:
    """Get or create the global watcher instance."""
    global _watcher
    if _watcher is None:
        _watcher = KubernetesWatcher()
    return _watcher


async def start_watching():
    """Start the global watcher."""
    watcher = get_watcher()
    return await watcher.start()


async def stop_watching():
    """Stop the global watcher."""
    watcher = get_watcher()
    return await watcher.stop()


async def get_watch_status():
    """Get watcher status."""
    watcher = get_watcher()
    return await watcher.get_status()
```

### Step 3B: Create Event Debouncer

**File:** `backend/app/services/event_debouncer.py`

The debouncer accumulates K8s events that arrive in rapid bursts and processes them in batches:

```python
"""
event_debouncer.py — Batches rapid K8s events for efficient processing
When cluster is under load, 100+ events arrive at once.
Wait 2 seconds, deduplicate, then analyze once.
"""

import asyncio
from typing import List, Dict, Any
from collections import defaultdict
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EventDebouncer:
    """
    Accumulates K8s events and debounces them.
    Prevents analysis thrashing from burst changes.
    """

    def __init__(self, debounce_ms: int = 2000):
        self.debounce_ms = debounce_ms
        self.event_queue: List[Dict[str, Any]] = []
        self.pending_flush = None
        self.changes_by_resource = defaultdict(list)

    async def queue_event(self, event: Dict[str, Any]) -> None:
        """Queue an event for debounced processing."""
        self.event_queue.append(event)

        # Start debounce timer if not already running
        if self.pending_flush is None:
            self.pending_flush = asyncio.create_task(
                self._flush_after_delay()
            )

    async def _flush_after_delay(self) -> None:
        """Wait for debounce window, then process accumulated events."""
        try:
            await asyncio.sleep(self.debounce_ms / 1000.0)  # Convert ms to seconds

            if self.event_queue:
                await self._process_events(self.event_queue)

            # Reset
            self.event_queue = []
            self.pending_flush = None
            self.changes_by_resource.clear()

        except Exception as e:
            logger.error(f"Error in debouncer flush: {e}")
            self.pending_flush = None

    async def _process_events(self, events: List[Dict[str, Any]]) -> None:
        """Process deduplicated batch of events."""
        # Deduplicate: only keep latest state for each resource
        unique_changes = {}

        for event in events:
            resource_key = (
                event['resource_type'],
                event['resource'].get('metadata', {}).get('uid', '')
            )
            unique_changes[resource_key] = event

        logger.info(f"Processing {len(unique_changes)} deduplicated resource changes")

        # Import here to avoid circular dependencies
        from app.services.watch_decision_engine import analyze_changes

        # Analyze the changes
        await analyze_changes(list(unique_changes.values()))

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return len(self.event_queue)
```

### Step 3C: Create Decision Engine for Alerts

**File:** `backend/app/services/watch_decision_engine.py`

This module decides whether changes warrant an alert:

```python
"""
watch_decision_engine.py — Determines if cluster changes require alerts
Compares previous state with new state, checks thresholds
"""

from typing import List, Dict, Any
from app.config import settings
from app.utils.logger import get_logger
from app.services.ingestion_service import ingest_and_build
from app.services.graph_diff_service import diff_runs, diff_latest_two
from app.services.history_service import record_analysis_run, get_run_history
from app.services.slack_service import send_critical_alert
from app.services.broadcast_service import broadcast_graph_update
from app.core.database import record_monitoring_event

logger = get_logger(__name__)


async def analyze_changes(events: List[Dict[str, Any]]) -> None:
    """
    Analyze deduplicated K8s events.
    1. Rebuild graph from current cluster state
    2. Compare with previous run
    3. Decide if alert is warranted
    4. Send alerts to Slack + frontend
    """

    logger.info(f"Analyzing {len(events)} K8s changes")

    try:
        # STEP 1: Get previous run ID (most recent from history)
        history = get_run_history(limit=1, cluster_name=settings.CLUSTER_NAME)
        if not history or history == []:
            logger.warn("No previous run in history. Skipping diff.")
            return

        previous_run_id = history[0]['run_id']

        # STEP 2: Rebuild graph with current cluster state
        # This re-fetches from kubectl and rebuilds the in-memory graph
        summary = ingest_and_build()

        # STEP 3: Record the new run
        new_run_id = record_analysis_run(
            cluster_name=settings.CLUSTER_NAME,
            source="watch_api",
            triggered_by="watch_event"
        )

        # STEP 4: Compare with previous
        diff_result = diff_runs(previous_run_id, new_run_id)

        # STEP 5: Check if alerts should be sent
        alerts_to_send = _check_alert_thresholds(diff_result)

        if alerts_to_send:
            # STEP 6: Send Slack alert
            await _send_alerts(alerts_to_send, diff_result, new_run_id)

            # STEP 7: Broadcast to frontend
            await broadcast_graph_update(diff_result, new_run_id)

            # STEP 8: Record to monitoring_events table
            for alert in alerts_to_send:
                record_monitoring_event(
                    run_id=new_run_id,
                    event_type=alert['type'],
                    severity=alert['severity'],
                    summary=alert['summary'],
                    details=alert,
                    triggered_alerts=['slack', 'websocket', 'history']
                )

            logger.info(f"Sent {len(alerts_to_send)} alerts for run {new_run_id}")
        else:
            logger.info(f"No alerts triggered for run {new_run_id}")

    except Exception as e:
        logger.error(f"Error analyzing changes: {e}", exc_info=True)


def _check_alert_thresholds(diff_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check if diff crosses alert thresholds.

    Returns list of alerts:
    [
        {
            "type": "RISK_INCREASE",
            "severity": "critical",
            "summary": "Risk increased from 6.2 to 7.5 (+24%)",
            "delta": 1.3
        }
    ]
    """
    alerts = []

    # ALERT 1: Risk increase
    if settings.ALERT_RISK_DELTA_THRESHOLD and diff_result.get('risk_delta'):
        risk_delta = diff_result['risk_delta'].get('delta', 0)
        if risk_delta > settings.ALERT_RISK_DELTA_THRESHOLD:
            severity = 'critical' if risk_delta > 2.0 else 'high'
            alerts.append({
                'type': 'RISK_INCREASE',
                'severity': severity,
                'summary': f"Risk increased from {diff_result['risk_delta']['before']} to {diff_result['risk_delta']['after']} (+{risk_delta:.1f})",
                'delta': risk_delta,
                'delta_pct': diff_result['risk_delta'].get('delta_pct', 0)
            })

    # ALERT 2: New attack paths
    if settings.ALERT_ON_NEW_PATHS and diff_result.get('path_delta'):
        path_delta = diff_result['path_delta'].get('delta', 0)
        if path_delta > 0:
            alerts.append({
                'type': 'NEW_ATTACK_PATHS',
                'severity': 'critical',
                'summary': f"{path_delta} new attack path(s) detected",
                'delta': path_delta
            })

    # ALERT 3: New privilege escalation cycles
    if settings.ALERT_ON_NEW_CYCLES and diff_result.get('cycle_delta'):
        cycle_delta = diff_result['cycle_delta'].get('delta', 0)
        if cycle_delta > 0:
            alerts.append({
                'type': 'NEW_CYCLES',
                'severity': 'high',
                'summary': f"{cycle_delta} new privilege escalation cycle(s) detected",
                'delta': cycle_delta
            })

    return alerts


async def _send_alerts(
    alerts: List[Dict[str, Any]],
    diff_result: Dict[str, Any],
    new_run_id: str
) -> None:
    """Send alerts to Slack."""
    try:
        # Format for Slack
        findings = {
            'alerts': alerts,
            'run_id': new_run_id,
            'diff': diff_result
        }

        # Send to Slack (reuse existing function)
        send_critical_alert(findings, settings.CLUSTER_NAME)

    except Exception as e:
        logger.error(f"Error sending alerts: {e}")
```

---

## PHASE 4: BROADCAST SERVICE & FRONTEND INTEGRATION (Days 7-10)

### Step 4A: Create Broadcast Service

**File:** `backend/app/services/broadcast_service.py`

Sends real-time updates to frontend clients:

```python
"""
broadcast_service.py — Real-time graph updates to frontend
Uses Server-Sent Events (SSE) to stream changes
"""

import json
import asyncio
from typing import Dict, Any, List
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Global set of connected SSE clients
connected_clients: List[asyncio.Queue] = []


def register_client(queue: asyncio.Queue) -> None:
    """Register a new SSE client."""
    connected_clients.append(queue)
    logger.info(f"Client registered. Total connected: {len(connected_clients)}")


def unregister_client(queue: asyncio.Queue) -> None:
    """Unregister an SSE client."""
    if queue in connected_clients:
        connected_clients.remove(queue)
    logger.info(f"Client unregistered. Total connected: {len(connected_clients)}")


async def broadcast_graph_update(
    diff_result: Dict[str, Any],
    new_run_id: str
) -> None:
    """
    Broadcast graph update to all connected frontend clients.

    Message format:
    {
        "type": "GRAPH_UPDATE",
        "run_id": "a3f9b2c1",
        "diff": {...full diff result...},
        "timestamp": "2026-04-04T14:30:12Z"
    }
    """
    message = {
        "type": "GRAPH_UPDATE",
        "run_id": new_run_id,
        "diff": diff_result,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Send to all connected clients
    dead_clients = []
    for client_queue in connected_clients:
        try:
            await asyncio.wait_for(
                client_queue.put(json.dumps(message)),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            logger.warn("Client queue full, marking for removal")
            dead_clients.append(client_queue)
        except Exception as e:
            logger.error(f"Error broadcasting to client: {e}")
            dead_clients.append(client_queue)

    # Clean up dead clients
    for client in dead_clients:
        unregister_client(client)

    logger.info(f"Broadcasted update to {len(connected_clients)} clients")
```

### Step 4B: Create SSE Endpoint

**File:** `backend/app/api/routes_monitor.py`

New API endpoints for monitoring control:

```python
"""
routes_monitor.py — Real-time monitoring API endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.services.watch_service import start_watching, stop_watching, get_watch_status
from app.services.broadcast_service import register_client, unregister_client
from app.utils.logger import get_logger
from app.config import settings
from app.core.database import get_monitoring_config

logger = get_logger(__name__)
router = APIRouter()


@router.post("/monitor/start")
async def start_monitor():
    """
    Start real-time K8s monitoring via Watch API.

    Returns:
        {"status": "watching", "resources": 7, "message": "..."}
    """
    if settings.MOCK_MODE:
        raise HTTPException(
            status_code=400,
            detail="Cannot enable monitoring in MOCK_MODE. Set MOCK_MODE=false in .env"
        )

    try:
        result = await start_watching()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting monitor: {e}")
        raise HTTPException(status_code=500, detail="Failed to start monitoring")


@router.post("/monitor/stop")
async def stop_monitor():
    """Stop real-time monitoring."""
    result = await stop_watching()
    return result


@router.get("/monitor/status")
async def monitor_status():
    """Get current monitoring status."""
    status = await get_watch_status()
    return status


@router.get("/monitor/events/stream")
async def events_stream():
    """
    Server-Sent Events (SSE) stream of graph updates.

    Frontend connects to this endpoint and receives live updates:

    event: GRAPH_UPDATE
    data: {"type": "GRAPH_UPDATE", "diff": {...}, "run_id": "a3f9b2c1"}

    Usage in frontend:
        const eventSource = new EventSource('/api/monitor/events/stream');
        eventSource.onmessage = (event) => {
            const update = JSON.parse(event.data);
            // Refresh graph, show diff panel, etc
        };
    """

    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue()
        register_client(client_queue)

        try:
            while True:
                try:
                    # Wait for message (with timeout to keep connection alive)
                    message = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=30.0
                    )
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat comment
                    yield ": heartbeat\n\n"

        except GeneratorExit:
            # Client disconnected
            unregister_client(client_queue)
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            unregister_client(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

### Step 4C: Update Main.py for Lifespan

**File:** `backend/app/main.py`

Modify the lifespan context manager to start/stop watch:

```python
# In the lifespan function:

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager: startup and shutdown.
    """
    # STARTUP
    logger.info(f"Starting {settings.APP_NAME}...")
    init_db()

    # Ingest initial graph
    summary = ingest_and_build()
    record_analysis_run(
        cluster_name=settings.CLUSTER_NAME,
        source="startup",
        triggered_by="startup"
    )

    # Start watching K8s if enabled and not in MOCK_MODE
    if settings.ENABLE_WATCH_API and not settings.MOCK_MODE:
        try:
            watch_status = await start_watching()
            logger.info(f"Monitoring started: {watch_status}")
        except Exception as e:
            logger.warn(f"Failed to start watch API: {e}. Will use fallback polling.")

    yield  # App is running

    # SHUTDOWN
    logger.info("Shutting down...")
    try:
        await stop_watching()
    except:
        pass
    logger.info("Shutdown complete")
```

Also register the new monitor routes in app creation:

```python
from app.api import routes_monitor

# In app creation:
app.include_router(routes_monitor.router, prefix="/api")
```

---

## PHASE 5: TESTING & VALIDATION (Days 10-14)

### Step 5A: Unit Tests

**File:** `backend/tests/test_watch_service.py`

```python
"""Test watch service initialization and event processing."""

import pytest
from app.services.watch_service import KubernetesWatcher
from app.services.event_debouncer import EventDebouncer


def test_debouncer_accumulates_events():
    """Test debouncer batches events."""
    debouncer = EventDebouncer(debounce_ms=100)

    # Queue 3 events
    debouncer.queue_event({'type': 'ADDED', 'id': '1'})
    debouncer.queue_event({'type': 'MODIFIED', 'id': '2'})
    debouncer.queue_event({'type': 'DELETED', 'id': '3'})

    assert debouncer.get_queue_size() == 3


def test_watcher_singleton():
    """Test watcher is a singleton."""
    from app.services.watch_service import get_watcher

    watcher1 = get_watcher()
    watcher2 = get_watcher()

    assert watcher1 is watcher2
```

### Step 5B: Integration Test

**File:** `backend/tests/test_watch_integration.py`

```python
"""
Integration test: simulate K8s event, verify alert triggered.
Requires local minikube or K8s cluster.
"""

import pytest
import subprocess
from app.services.watch_decision_engine import _check_alert_thresholds


@pytest.mark.integration
def test_risk_increase_triggers_alert():
    """Test that risk increase above threshold triggers alert."""

    diff_result = {
        'risk_delta': {
            'before': 6.2,
            'after': 7.5,
            'delta': 1.3,
            'delta_pct': 20.9
        },
        'path_delta': {'delta': 0},
        'cycle_delta': {'delta': 0}
    }

    alerts = _check_alert_thresholds(diff_result)

    assert len(alerts) == 1
    assert alerts[0]['type'] == 'RISK_INCREASE'
    assert alerts[0]['severity'] == 'high'
```

### Step 5C: Manual End-to-End Test

**Test Scenario 1: Deploy Pod**

```bash
# Terminal 1: Start backend
cd backend
python -m app.main

# Check monitoring is active
curl http://localhost:8000/api/monitor/status
# Should return: {"watching": true, "resources": 7}

# Terminal 2: Watch frontend updates
open http://localhost:3000/dashboard
# Open browser console (F12)
# Watch Network tab for SSE messages

# Terminal 3: Deploy a pod to minikube
minikube start
kubectl create deployment test-deployment --image=nginx
# Within 2 seconds, should see SSE event in browser
# Should see Slack alert
```

**Test Scenario 2: Create Dangerous Binding**

```bash
# Create a role binding that elevates privileges
kubectl create rolebinding admin-binding --clusterrole=admin --serviceaccount=default:default
# Risk should increase, trigger alert
```

---

## PHASE 6: FRONTEND INTEGRATION (Days 14-21)

### Step 6A: Create useMonitoring Hook

**File:** `frontend/src/hooks/useMonitoring.ts`

```typescript
import { useEffect, useState, useCallback } from 'react';

interface GraphUpdate {
  type: 'GRAPH_UPDATE';
  run_id: string;
  diff: any;
  timestamp: string;
}

export function useMonitoring() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<GraphUpdate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Connect to SSE stream
    const eventSource = new EventSource('/api/monitor/events/stream');

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const update: GraphUpdate = JSON.parse(event.data);
        setLastUpdate(update);

        // Trigger graph refresh in parent component
        window.dispatchEvent(
          new CustomEvent('graphUpdate', { detail: update })
        );
      } catch (e) {
        console.error('Failed to parse SSE message', e);
      }
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      setError('Monitoring connection lost. Retrying...');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, []);

  return { isConnected, lastUpdate, error };
}
```

### Step 6B: Update Dashboard.tsx

```typescript
// In Dashboard.tsx, add monitoring:

import { useMonitoring } from '@/hooks/useMonitoring';

export default function Dashboard() {
  const { isConnected, lastUpdate } = useMonitoring();

  // Listen for graph updates
  useEffect(() => {
    const handleUpdate = (event: any) => {
      const update = event.detail;
      // Show notification
      toast({
        title: 'Graph Updated',
        description: `Risk changed by ${update.diff.risk_delta.delta.toFixed(1)}`,
      });
      // Refresh graph
      reload();
      // Show diff panel
      setActiveTab('diff');
    };

    window.addEventListener('graphUpdate', handleUpdate);
    return () => window.removeEventListener('graphUpdate', handleUpdate);
  }, []);

  return (
    <div>
      {/* Existing dashboard... */}

      {/* Monitoring status indicator */}
      <div className="flex items-center gap-2 px-4 py-2 bg-secondary rounded-lg">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
        <span className="text-xs text-muted-foreground">
          {isConnected ? 'Monitoring active' : 'Monitoring disconnected'}
        </span>
      </div>
    </div>
  );
}
```

---

## PHASE 7: FALLBACK & RESILIENCE (Days 21-25)

### Step 7A: Implement Fallback Polling

**File:** `backend/app/services/fallback_poller.py`

If Watch API fails, fall back to periodic polling:

```python
"""
fallback_poller.py — Fallback monitoring if Watch API unavailable
Polls K8s cluster every 5 minutes using kubectl
"""

import asyncio
from datetime import datetime
from app.config import settings
from app.services.ingestion_service import ingest_and_build
from app.services.watch_decision_engine import analyze_changes
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FallbackPoller:
    """Polls K8s cluster on interval as fallback."""

    def __init__(self, interval_sec: int = None):
        self.interval_sec = interval_sec or settings.FALLBACK_POLL_INTERVAL_SEC
        self.running = False
        self.last_graph_hash = None

    async def start(self):
        """Start polling loop."""
        self.running = True
        logger.info(f"Started fallback poller (interval: {self.interval_sec}s)")

        while self.running:
            try:
                await self._poll_once()
                await asyncio.sleep(self.interval_sec)
            except Exception as e:
                logger.error(f"Poller error: {e}")
                await asyncio.sleep(5)  # Short wait before retry

    async def _poll_once(self):
        """Poll cluster once, check for changes."""
        # Rebuild graph
        summary = ingest_and_build()

        # Check if state changed (using hash of graph)
        current_hash = hash(str(summary))

        if current_hash != self.last_graph_hash:
            logger.info("Cluster state changed, triggering analysis")
            self.last_graph_hash = current_hash

            # Trigger analysis same as watch would
            await analyze_changes([])

    async def stop(self):
        """Stop polling."""
        self.running = False
        logger.info("Stopped fallback poller")


# Module-level instance
_poller: FallbackPoller | None = None


def get_poller() -> FallbackPoller:
    """Get or create poller."""
    global _poller
    if _poller is None:
        _poller = FallbackPoller()
    return _poller
```

### Step 7B: Hybrid Mode in Watch Service

Modify `watch_service.py` to enable fallback:

```python
# In KubernetesWatcher class:

async def _watch_all_resources(self):
    """Main watch loop with fallback support."""
    from app.services.fallback_poller import get_poller

    fallback_attempts = 0

    while self.watching:
        try:
            for api_version, resource_type in self.resource_watchers:
                if not self.watching:
                    break
                await self._watch_resource_type(api_version, resource_type)
            fallback_attempts = 0  # Reset on success
        except Exception as e:
            logger.error(f"Watch error: {e}")
            fallback_attempts += 1

            if fallback_attempts >= 3:
                # After 3 failures, use fallback polling
                logger.warn("Switching to fallback polling after 3 watch failures")
                poller = get_poller()
                await poller.start()
                return

            if self.watching:
                await asyncio.sleep(settings.WATCH_RECONNECT_DELAY_SEC)
```

---

## SUMMARY: Files to Create & Modify

### CREATE (6 new files):
```
backend/app/services/watch_service.py          (300 lines)
backend/app/services/event_debouncer.py        (100 lines)
backend/app/services/watch_decision_engine.py  (200 lines)
backend/app/services/broadcast_service.py      (100 lines)
backend/app/services/fallback_poller.py        (100 lines)
backend/app/api/routes_monitor.py              (150 lines)
```

### MODIFY (5 existing files):
```
backend/app/config.py              (+30 lines new settings)
backend/app/core/database.py       (+80 lines new tables)
backend/app/main.py                (+20 lines watch startup)
backend/requirements.txt            (+3 new dependencies)
frontend/src/pages/Dashboard.tsx   (+30 lines monitoring UI)
```

---

## VERIFICATION CHECKLIST

- [ ] All dependencies installed: `pip install kubernetes python-watch aiodns`
- [ ] Database tables created on first run
- [ ] Watch service starts on backend startup (when MOCK_MODE=false)
- [ ] K8s connection succeeds with `kubectl` available
- [ ] SSE endpoint accessible: `GET /api/monitor/events/stream`
- [ ] Monitor status shows: `GET /api/monitor/status` returns watching=true
- [ ] Test deployment to minikube triggers alert within 2-5 seconds
- [ ] Frontend receives SSE update and refreshes graph
- [ ] Slack receives alert message
- [ ] History table records monitoring events
- [ ] Fallback polling activates if watch API fails
- [ ] Graceful shutdown without errors

---

## DEBUGGING TIPS

If Watch API fails:
```bash
# Check K8s connection
kubectl cluster-info
kubectl get pods -A

# Check logs
docker logs <backend-container>  # or tail backend/app/logs/

# Check kubeconfig
cat ~/.kube/config

# Test watch manually
python -c "from kubernetes import client, config, watch; config.load_kube_config(); w = watch.Watch(); print('OK')"
```

If events not arriving at frontend:
```bash
# Check SSE endpoint
curl -N http://localhost:8000/api/monitor/events/stream

# Check browser console for errors
# Check Network tab in DevTools for EventSource connection

# Check backend logs for broadcast errors
```

---

## SUCCESS CRITERIA

✅ System detects K8s changes within **2 seconds** (debounce window)
✅ Graph rebuilds automatically on significant changes
✅ Alerts sent to Slack + frontend on: risk increase, new paths, new cycles
✅ Frontend receives and displays updates via SSE
✅ History database populated with monitoring events
✅ Graceful fallback to polling if watch API fails
✅ Zero data loss or missed events
✅ Comprehensive error handling and logging

