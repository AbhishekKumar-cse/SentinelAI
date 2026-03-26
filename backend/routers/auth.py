"""
Auth Router — user management, custom claims, API key management.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter()


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str
    display_name: Optional[str] = None


class UpdateRoleRequest(BaseModel):
    role: str


class CreateAPIKeyRequest(BaseModel):
    name: str
    permissions: list[str] = []
    expires_days: Optional[int] = None


@router.get("/auth/me", summary="Get current user profile")
async def get_me(request: Request):
    """Return the current authenticated user's profile."""
    from db.models import User

    uid = getattr(request.state, "uid", "dev_user_001")
    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    user = await User.find_one(User.uid == uid)
    if not user:
        return {
            "uid": uid,
            "email": getattr(request.state, "email", ""),
            "role": getattr(request.state, "role", "AGENT_OPERATOR"),
            "tenant_id": tenant_id,
            "display_name": None,
        }

    return {
        "uid": user.uid,
        "email": str(user.email),
        "role": user.role,
        "tenant_id": user.tenant_id,
        "display_name": user.display_name,
        "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
    }


@router.get("/settings/users", summary="List tenant users")
async def list_users(request: Request):
    """List all users in the tenant."""
    from db.models import User

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    users = await User.find(User.tenant_id == tenant_id).to_list()

    return {
        "users": [
            {
                "uid": u.uid,
                "email": str(u.email),
                "display_name": u.display_name,
                "role": u.role,
                "is_active": u.is_active,
                "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "count": len(users),
    }


@router.post("/settings/users/invite", summary="Invite a user")
async def invite_user(body: InviteUserRequest, request: Request):
    """
    Invite a new user to the tenant.
    Creates Firebase Auth user, sets custom claims, sends invite email.
    """
    from db.models import User
    from middleware.firebase_auth import get_firebase_app, set_custom_claims

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    # Check if user already exists
    existing = await User.find_one(User.email == body.email, User.tenant_id == tenant_id)
    if existing:
        raise HTTPException(status_code=409, detail="User already exists in this tenant")

    # Create Firebase user
    uid = f"user_{uuid.uuid4().hex[:12]}"  # Mock in dev
    firebase_app = get_firebase_app()
    if firebase_app:
        try:
            from firebase_admin import auth
            firebase_user = auth.create_user(
                email=body.email,
                display_name=body.display_name,
                app=firebase_app,
            )
            uid = firebase_user.uid
            set_custom_claims(uid, tenant_id, body.role, [])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Firebase user creation failed: {e}")

    # Create user document in MongoDB
    user = User(
        uid=uid,
        tenant_id=tenant_id,
        email=body.email,
        display_name=body.display_name,
        role=body.role,
    )
    await user.insert()

    return {
        "uid": uid,
        "email": body.email,
        "role": body.role,
        "status": "INVITED",
    }


@router.put("/settings/users/{uid}/role", summary="Update user role")
async def update_user_role(uid: str, body: UpdateRoleRequest, request: Request):
    """Update user role and Firebase custom claims."""
    from db.models import User, UserRole
    from middleware.firebase_auth import set_custom_claims

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    user = await User.find_one(User.uid == uid, User.tenant_id == tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        new_role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    await user.set({User.role: new_role})
    set_custom_claims(uid, tenant_id, body.role, [])

    return {"uid": uid, "role": body.role}


@router.post("/settings/api-keys", summary="Create API key")
async def create_api_key(body: CreateAPIKeyRequest, request: Request):
    """Create an API key. Returns the raw key ONCE — never stored in plaintext."""
    from db.models import APIKey
    from services.encryption_service import generate_api_key
    from datetime import timedelta

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")

    raw_key, key_hash = generate_api_key()

    expires_at = None
    if body.expires_days:
        expires_at = __import__("datetime").datetime.utcnow() + timedelta(days=body.expires_days)

    api_key = APIKey(
        key_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=uid,
        key_hash=key_hash,
        name=body.name,
        permissions=body.permissions,
        expires_at=expires_at,
    )
    await api_key.insert()

    return {
        "key_id": api_key.key_id,
        "name": body.name,
        "raw_key": raw_key,  # Show ONCE
        "expires_at": expires_at.isoformat() if expires_at else None,
        "warning": "Save this key now. It will never be shown again.",
    }


@router.delete("/settings/api-keys/{key_id}", summary="Revoke API key")
async def revoke_api_key(key_id: str, request: Request):
    """Revoke an API key."""
    from db.models import APIKey

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    key = await APIKey.find_one(APIKey.key_id == key_id, APIKey.tenant_id == tenant_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    await key.set({APIKey.is_active: False})
    return {"status": "REVOKED", "key_id": key_id}
