"""
Firebase Authentication middleware for FastAPI.
Verifies Firebase ID tokens on every protected request.
Injects uid, tenant_id, role, email into request.state.
"""
import json
import logging
import os
from functools import lru_cache
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Routes that bypass authentication
PUBLIC_ROUTES = {
    "GET /health",
    "GET /api/v1/health",
    "POST /api/v1/auth/webhook",  # Firebase events
    "GET /docs",
    "GET /redoc",
    "GET /openapi.json",
}


@lru_cache(maxsize=1)
def get_firebase_app():
    """Initialize Firebase Admin SDK (once per process)."""
    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "{}")

    try:
        service_account_dict = json.loads(service_account_json)
        if not service_account_dict.get("project_id"):
            # Development mode: use default credentials or skip
            logger.warning(
                "Firebase service account not configured. "
                "Auth checks will be SKIPPED in development mode."
            )
            return None

        cred = credentials.Certificate(service_account_dict)
        app = firebase_admin.initialize_app(cred)
        logger.info(f"Firebase Admin initialized for project: {service_account_dict.get('project_id')}")
        return app
    except Exception as e:
        logger.error(f"Firebase Admin initialization failed: {e}")
        return None


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that verifies Firebase ID tokens.
    Sets request.state.uid, request.state.tenant_id, request.state.role.
    """

    def __init__(self, app, dev_bypass: bool = False):
        super().__init__(app)
        self.dev_bypass = dev_bypass
        # Initialize Firebase on middleware creation
        get_firebase_app()

    async def dispatch(self, request: Request, call_next):
        # Check if route is public
        route_key = f"{request.method} {request.url.path}"
        if route_key in PUBLIC_ROUTES:
            return await call_next(request)

        # WebSocket connections use ?token= query param
        token = None
        if request.url.path.startswith("/api/v1/ws"):
            token = request.query_params.get("token")
        else:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        # API Key authentication
        api_key = request.headers.get("X-API-Key")
        if api_key and not token:
            return await self._verify_api_key(request, api_key, call_next)

        if not token:
            if self.dev_bypass:
                # Development bypass: inject a mock user
                request.state.uid = "dev_user_001"
                request.state.tenant_id = "dev_tenant_001"
                request.state.role = "TENANT_ADMIN"
                request.state.email = "dev@antigravity.ai"
                request.state.permissions = ["*"]
                return await call_next(request)
            return JSONResponse(
                {"error": "Missing authentication token", "code": "NO_TOKEN"},
                status_code=401,
            )

        firebase_app = get_firebase_app()
        if not firebase_app:
            if self.dev_bypass:
                request.state.uid = "dev_user_001"
                request.state.tenant_id = "dev_tenant_001"
                request.state.role = "TENANT_ADMIN"
                request.state.email = "dev@antigravity.ai"
                request.state.permissions = ["*"]
                return await call_next(request)
            return JSONResponse(
                {"error": "Auth service unavailable", "code": "AUTH_UNAVAILABLE"},
                status_code=503,
            )

        try:
            decoded = auth.verify_id_token(token, app=firebase_app, check_revoked=True)

            request.state.uid = decoded["uid"]
            request.state.tenant_id = decoded.get("tenantId")
            request.state.role = decoded.get("role", "AGENT_OPERATOR")
            request.state.email = decoded.get("email", "")
            request.state.permissions = decoded.get("permissions", [])

        except auth.RevokedIdTokenError:
            return JSONResponse(
                {"error": "Token has been revoked", "code": "TOKEN_REVOKED"},
                status_code=401,
            )
        except auth.ExpiredIdTokenError:
            return JSONResponse(
                {"error": "Token has expired", "code": "TOKEN_EXPIRED"},
                status_code=401,
            )
        except auth.InvalidIdTokenError as e:
            return JSONResponse(
                {"error": f"Invalid token: {str(e)}", "code": "TOKEN_INVALID"},
                status_code=401,
            )
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return JSONResponse(
                {"error": "Authentication failed", "code": "AUTH_FAILED"},
                status_code=401,
            )

        return await call_next(request)

    async def _verify_api_key(self, request: Request, api_key: str, call_next):
        """Verify X-API-Key header against hashed keys in MongoDB."""
        from services.encryption_service import hash_api_key
        from db.models import APIKey

        key_hash = hash_api_key(api_key)
        db_key = await APIKey.find_one(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,
        )

        if not db_key:
            return JSONResponse(
                {"error": "Invalid API key", "code": "INVALID_API_KEY"},
                status_code=401,
            )

        # Check expiry
        from datetime import datetime
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            return JSONResponse(
                {"error": "API key expired", "code": "API_KEY_EXPIRED"},
                status_code=401,
            )

        # Update last_used_at asynchronously
        await db_key.set({APIKey.last_used_at: datetime.utcnow()})

        request.state.uid = db_key.user_id
        request.state.tenant_id = db_key.tenant_id
        request.state.role = "SERVICE_ACCOUNT"
        request.state.email = ""
        request.state.permissions = db_key.permissions

        return await call_next(request)


def require_role(*allowed_roles: str):
    """FastAPI dependency for role-based access control."""
    from fastapi import HTTPException

    async def role_checker(request: Request):
        user_role = getattr(request.state, "role", None)
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {allowed_roles}, Got: {user_role}",
            )
        return user_role

    return role_checker


def require_tenant(request: Request) -> str:
    """FastAPI dependency that ensures tenant_id is present."""
    from fastapi import HTTPException
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this account")
    return tenant_id


def set_custom_claims(uid: str, tenant_id: str, role: str, permissions: list):
    """Set Firebase custom claims for a user (called at user creation/update)."""
    firebase_app = get_firebase_app()
    if not firebase_app:
        logger.warning("Firebase not configured — skipping custom claims")
        return

    auth.set_custom_user_claims(uid, {
        "tenantId": tenant_id,
        "role": role,
        "permissions": permissions,
    }, app=firebase_app)
    logger.info(f"Custom claims set for uid={uid}: role={role}, tenantId={tenant_id}")
