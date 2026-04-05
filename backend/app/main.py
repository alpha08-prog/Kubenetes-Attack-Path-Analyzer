"""
main.py — FastAPI Application Entry Point
Registers all routers, startup logic, middleware, and health endpoints.
Run with: uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ─── Background CVE enrichment ────────────────────────────────────────────────

def _start_background_cve_enrichment() -> None:
    """
    Launch CVE scoring in a daemon thread so startup is never blocked.

    The NVD API is slow (2-3 s per image) and rate-limits aggressively (429).
    Running it in the background means the server is ready in ~2 seconds while
    CVE data populates gradually. Results are written directly into the live
    NetworkX graph nodes so every subsequent request sees up-to-date scores.
    """
    import threading

    def _worker() -> None:
        import time as _time
        try:
            from app.core.graph_builder import get_graph
            from app.services.cve_service import get_cve_score_for_image
            G = get_graph()
            pod_nodes = [(n, d) for n, d in G.nodes(data=True) if d.get("type") == "pod"]
            logger.info("Background CVE enrichment started (%d pod nodes)", len(pod_nodes))

            # Collect every unique image across all pods so each image is scored
            # only once — avoids redundant NVD API calls when multiple pods
            # (e.g. etcd, kube-apiserver) share the same container image.
            image_to_score: dict = {}
            all_images: list = []
            for _, attrs in pod_nodes:
                for img in attrs.get("metadata", {}).get("image", []):
                    if img and img not in image_to_score:
                        image_to_score[img] = None   # placeholder
                        all_images.append(img)

            for img in all_images:
                image_to_score[img] = get_cve_score_for_image(img)
                _time.sleep(1.5)  # stay under NVD's 5 req/30s limit

            enriched = 0
            for node_id, attrs in pod_nodes:
                images = attrs.get("metadata", {}).get("image", [])
                if not images:
                    continue
                cvss_scores = {img: image_to_score.get(img, 0.0) for img in images}
                max_cve_score = max(cvss_scores.values(), default=0.0)

                if max_cve_score > 0:
                    old_risk = attrs.get("risk", 0.0)
                    G.nodes[node_id]["risk"] = round(min(10.0, old_risk + (max_cve_score * 0.2)), 1)
                    G.nodes[node_id].setdefault("metadata", {})
                    G.nodes[node_id]["metadata"]["cve_score"]        = max_cve_score
                    G.nodes[node_id]["metadata"]["cvss_scores"]      = cvss_scores
                    G.nodes[node_id]["metadata"]["container_images"] = list(images)
                    enriched += 1

            logger.info("Background CVE enrichment complete (%d pods enriched)", enriched)
        except Exception as exc:
            logger.warning("Background CVE enrichment failed (non-critical): %s", exc)

    t = threading.Thread(target=_worker, name="cve-enrichment", daemon=True)
    t.start()


# ─── Lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once on startup before the first request.
    Loads graph data so the app is ready immediately.
    """
    logger.info("=" * 60)
    logger.info("  %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("  MOCK_MODE   : %s", settings.MOCK_MODE)
    logger.info("  CLUSTER     : %s", settings.CLUSTER_NAME)
    logger.info("  GROQ MODEL  : %s", settings.GROQ_MODEL)
    logger.info("=" * 60)

    from app.core.database import init_db
    init_db()
 
    # Build graph on startup so first API call is instant
    try:
        from app.services.ingestion_service import ingest_and_build
        summary = ingest_and_build()
        logger.info(
            "Graph loaded — %d nodes, %d edges (source: %s)",
            summary["node_count"],
            summary["edge_count"],
            summary["source"],
        )
        # Run real algorithms before recording so the startup baseline has
        # accurate attack_paths / cycles values — not zeros. This prevents
        # a false NEW_ATTACK_PATHS alert when the Watch API's initial K8s
        # event flood diffs against a zeroed-out baseline on every restart.
        startup_paths  = 0
        startup_cycles = 0
        try:
            from app.services.attack_service import get_auto_attack_path
            _ap = get_auto_attack_path()
            startup_paths = 1 if _ap.get("found") else 0
        except Exception:
            pass
        try:
            from app.services.analysis_service import get_cycles
            _cy = get_cycles()
            startup_cycles = _cy.get("cycle_count", 0)
        except Exception:
            pass

        from app.services.history_service import record_analysis_run
        record_analysis_run(
            cluster_name=settings.CLUSTER_NAME,
            source=summary["source"],
            triggered_by="startup",
            attack_paths=startup_paths,
            cycles=startup_cycles,
        )

        # Start CVE enrichment in the background — avoids blocking startup
        # with slow sequential NVD API calls (2-5 s each, rate-limited).
        _start_background_cve_enrichment()

    except Exception as e:
        logger.error("Startup graph load failed: %s", e)
        logger.warning("App will start but graph is empty — call POST /api/graph/reload")

    # ── Auto-start K8s Watch API monitoring ─────────────────────────────────
    if settings.ENABLE_WATCH_API and not settings.MOCK_MODE:
        try:
            from app.services.watch_service import start_watching
            watch_result = await start_watching()
            logger.info("K8s Watch API started: %s", watch_result.get("message"))
        except Exception as exc:
            logger.warning(
                "Watch API failed to start (%s). "
                "Activating fallback poller (every %ds).",
                exc,
                settings.FALLBACK_POLL_INTERVAL_SEC,
            )
            try:
                from app.services.fallback_poller import get_poller
                await get_poller().start()
            except Exception as poll_exc:
                logger.error("Fallback poller also failed: %s", poll_exc)
    elif settings.MOCK_MODE:
        logger.info("MOCK_MODE=true — K8s Watch API disabled")
    else:
        logger.info("ENABLE_WATCH_API=false — real-time monitoring disabled")

    yield  # ← app is running and accepting requests

    logger.info("Shutting down %s", settings.APP_NAME)

    # ── Graceful shutdown of monitoring ─────────────────────────────────────
    if settings.ENABLE_WATCH_API and not settings.MOCK_MODE:
        try:
            from app.services.watch_service import stop_watching
            await stop_watching()
        except Exception:
            pass
        try:
            from app.services.fallback_poller import get_poller
            await get_poller().stop()
        except Exception:
            pass


# ─── App instance ─────────────────────────────────────────────────────────────

app = FastAPI(
    title       = settings.APP_NAME,
    version     = settings.APP_VERSION,
    description = "Attack Path Analysis & Blast Radius Mapping for Kubernetes — Nokia Hackathon",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)


# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─── Request timing middleware ─────────────────────────────────────────────────

import time

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"

    from app.utils.logger import log_api_request
    log_api_request(request.method, request.url.path, response.status_code, duration_ms)

    return response


# ─── Global exception handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "error":  "Internal server error",
            "detail": str(exc),
            "path":   str(request.url.path),
        },
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

from app.api.routes_graph    import router as graph_router
from app.api.routes_attack   import router as attack_router
from app.api.routes_blast    import router as blast_router
from app.api.routes_cycles   import router as cycles_router
from app.api.routes_critical import router as critical_router
from app.api.routes_report   import router as report_router
from app.api.routes_simulate import router as simulate_router
from app.api.routes_ai       import router as ai_router
from app.api.routes_cve      import router as cve_router
from app.api.routes_history import router as history_router
from app.api.routes_slack import router as slack_router
from app.api.routes_diff import router as diff_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_monitor  import router as monitor_router
from app.api.routes_snapshot import router as snapshot_router   # B3

app.include_router(graph_router,    prefix="/api/graph",    tags=["Graph"])
app.include_router(attack_router,   prefix="/api/attack",   tags=["Attack Path"])
app.include_router(blast_router,    prefix="/api/blast",    tags=["Blast Radius"])
app.include_router(cycles_router,   prefix="/api/cycles",   tags=["Cycle Detection"])
app.include_router(critical_router, prefix="/api/critical", tags=["Critical Nodes"])
app.include_router(report_router,   prefix="/api/report",   tags=["AI Report"])
app.include_router(simulate_router, prefix="/api/simulate", tags=["Simulation"])
app.include_router(ai_router,       prefix="/api/ai",       tags=["AI"])
app.include_router(cve_router, prefix = "/api/cves", tags = ["CVE Feed"])
app.include_router(history_router, prefix="/api/history", tags=["History"])
app.include_router(slack_router, prefix="/api/slack", tags=["Slack Alerts"])
app.include_router(diff_router, prefix="/api/diff", tags=["Graph Diff"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(monitor_router,  prefix="/api/monitor",  tags=["Monitoring"])
app.include_router(snapshot_router, prefix="/api/snapshots", tags=["Temporal Analysis"])  # B3


# ─── Health & info endpoints ───────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    """Liveness probe — always returns 200 if the process is alive."""
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
def ready():
    """
    Readiness probe — returns 200 only if graph is loaded.
    Used by docker-compose healthcheck.
    """
    try:
        from app.core.graph_builder import get_graph, get_metadata
        G = get_graph()
        meta = get_metadata()
        return {
            "status":     "ready",
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "built_at":   meta.get("built_at"),
            "mock_mode":  settings.MOCK_MODE,
        }
    except RuntimeError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "detail": "Graph not loaded yet"},
        )
