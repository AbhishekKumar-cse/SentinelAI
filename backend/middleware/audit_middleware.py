"""
Audit middleware — auto-audits all mutating (POST/PUT/PATCH/DELETE) requests.
Captures request/response metadata for compliance trail.
"""
import logging
import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

SKIP_AUDIT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/metrics"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        if request.url.path in SKIP_AUDIT_PATHS:
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Log mutation for compliance (async, non-blocking)
        uid = getattr(request.state, "uid", "anonymous")
        tenant_id = getattr(request.state, "tenant_id", "unknown")
        role = getattr(request.state, "role", "unknown")

        logger.info(
            "API_MUTATION",
            extra={
                "method": request.method,
                "path": request.url.path,
                "uid": uid,
                "tenant_id": tenant_id,
                "role": role,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-Duration-Ms"] = str(duration_ms)
        return response
