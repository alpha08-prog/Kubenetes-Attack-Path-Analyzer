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
    except Exception as e:
        logger.error("Startup graph load failed: %s", e)
        logger.warning("App will start but graph is empty — call POST /api/graph/reload")

    yield  # app runs here

    logger.info("Shutting down %s", settings.APP_NAME)


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

app.include_router(graph_router,    prefix="/api/graph",    tags=["Graph"])
app.include_router(attack_router,   prefix="/api/attack",   tags=["Attack Path"])
app.include_router(blast_router,    prefix="/api/blast",    tags=["Blast Radius"])
app.include_router(cycles_router,   prefix="/api/cycles",   tags=["Cycle Detection"])
app.include_router(critical_router, prefix="/api/critical", tags=["Critical Nodes"])
app.include_router(report_router,   prefix="/api/report",   tags=["AI Report"])
app.include_router(simulate_router, prefix="/api/simulate", tags=["Simulation"])
app.include_router(ai_router,       prefix="/api/ai",       tags=["AI"])
app.include_router(cve_router, prefix = "/api/cves", tags = ["CVE Feed"])


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
