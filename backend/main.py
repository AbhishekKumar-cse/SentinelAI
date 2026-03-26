"""
AntiGravity v2.0 — FastAPI Application Entry Point
"""
import logging
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Routers
from routers import (
    workflows,
    agents,
    audit,
    tasks,
    meetings,
    analytics,
    connectors,
    auth,
    websockets,
)
from middleware.firebase_auth import FirebaseAuthMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.audit_middleware import AuditMiddleware
from middleware.pii_detector import PIIDetectorMiddleware
from db.mongodb import init_mongodb, close_mongodb
from db.indexes import create_all_indexes
from kafka.producer import ensure_topics_exist, flush as kafka_flush

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logging.basicConfig(level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper()))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup and shutdown logic."""
    # ── Startup ────────────────────────────────────────────────────────────
    logger.info("AntiGravity v2.0 starting up...")

    # Initialize MongoDB + Beanie ODM
    await init_mongodb()

    # Create all indexes
    try:
        await create_all_indexes()
    except Exception as e:
        logger.warning(f"Index creation partial failure: {e}")

    # Ensure Kafka topics exist
    try:
        await ensure_topics_exist()
    except Exception as e:
        logger.warning(f"Kafka topic creation failed: {e}")

    logger.info("AntiGravity v2.0 ready to serve requests")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    logger.info("AntiGravity v2.0 shutting down...")
    kafka_flush()
    await close_mongodb()
    logger.info("Shutdown complete")


# ─── Create FastAPI App ───────────────────────────────────────────────────────

app = FastAPI(
    title="AntiGravity API",
    description="AI-powered autonomous enterprise workflow orchestration platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://app.antigravity.ai",
        os.environ.get("FRONTEND_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Custom Middleware (order matters — last added = first executed) ───────────
environment = os.environ.get("ENVIRONMENT", "development")
is_dev = environment == "development"

# PII Detection (outermost — log before any processing)
app.add_middleware(PIIDetectorMiddleware)

# Audit Middleware
app.add_middleware(AuditMiddleware)

# Rate Limiting
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
app.add_middleware(RateLimitMiddleware, redis_url=redis_url)

# Firebase Auth (innermost — auth before business logic)
app.add_middleware(FirebaseAuthMiddleware, dev_bypass=is_dev)

# ─── Routes ──────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(workflows.router, prefix=API_PREFIX, tags=["Workflows"])
app.include_router(agents.router, prefix=API_PREFIX, tags=["Agents"])
app.include_router(audit.router, prefix=API_PREFIX, tags=["Audit"])
app.include_router(tasks.router, prefix=API_PREFIX, tags=["Tasks"])
app.include_router(meetings.router, prefix=API_PREFIX, tags=["Meetings"])
app.include_router(analytics.router, prefix=API_PREFIX, tags=["Analytics"])
app.include_router(connectors.router, prefix=API_PREFIX, tags=["Connectors"])
app.include_router(auth.router, prefix=API_PREFIX, tags=["Auth"])
app.include_router(websockets.router, prefix=API_PREFIX, tags=["WebSocket"])


# ─── Health Check (public) ────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and Docker healthchecks."""
    return {
        "status": "healthy",
        "service": "antigravity-api",
        "version": "2.0.0",
        "environment": environment,
    }


@app.get("/api/v1/health", tags=["System"])
async def api_health():
    """Detailed health check with dependency status."""
    from db.mongodb import get_db

    checks = {"api": "healthy", "database": "unknown", "cache": "unknown"}

    # Check MongoDB
    try:
        db = get_db()
        await db.command("ping")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)[:50]}"

    # Check Redis
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
        checks["cache"] = "healthy"
    except Exception as e:
        checks["cache"] = f"unhealthy: {str(e)[:50]}"

    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"

    return {
        "status": overall,
        "checks": checks,
        "version": "2.0.0",
        "environment": environment,
    }


# ─── Exception Handlers ───────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)[:200]},
    )
