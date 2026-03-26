"""
Rate limiting middleware using Redis.
Per-tenant rate limits with configurable windows.
"""
import logging
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis_async

logger = logging.getLogger(__name__)

# Default rate limit: 1000 requests per minute per tenant
DEFAULT_RATE_LIMIT = 1000
DEFAULT_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str = "redis://localhost:6379"):
        super().__init__(app)
        self.redis_url = redis_url
        self._redis: redis_async.Redis | None = None

    async def get_redis(self) -> redis_async.Redis:
        if not self._redis:
            self._redis = await redis_async.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        try:
            r = await self.get_redis()
            key = f"rl:{tenant_id}:{int(time.time() // DEFAULT_WINDOW_SECONDS)}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, DEFAULT_WINDOW_SECONDS * 2)

            if count > DEFAULT_RATE_LIMIT:
                logger.warning(f"Rate limit exceeded for tenant {tenant_id}: {count} req/min")
                return JSONResponse(
                    {
                        "error": "Rate limit exceeded",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "retry_after": DEFAULT_WINDOW_SECONDS,
                    },
                    status_code=429,
                    headers={"Retry-After": str(DEFAULT_WINDOW_SECONDS)},
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(DEFAULT_RATE_LIMIT)
            response.headers["X-RateLimit-Remaining"] = str(max(0, DEFAULT_RATE_LIMIT - count))
            return response

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open — don't block requests if Redis is down
            return await call_next(request)
