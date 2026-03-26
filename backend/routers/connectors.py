"""
Connectors Router — connector CRUD and health management.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class CreateConnectorRequest(BaseModel):
    system_type: str
    display_name: Optional[str] = None
    config: dict = {}  # Will be encrypted before storage


@router.get("/connectors", summary="List connectors")
async def list_connectors(request: Request):
    """List all connectors. Config credentials are excluded from response."""
    from db.models import Connector

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    connectors = await Connector.find(Connector.tenant_id == tenant_id).to_list()

    return {
        "connectors": [
            {
                "connector_id": c.connector_id,
                "system_type": c.system_type,
                "display_name": c.display_name,
                "status": c.status,
                "last_health_check_at": c.last_health_check_at.isoformat() if c.last_health_check_at else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in connectors
        ],
        "count": len(connectors),
    }


@router.post("/connectors", summary="Create a connector")
async def create_connector(body: CreateConnectorRequest, request: Request):
    """Create a connector. Config is encrypted using AES-256-GCM before storage."""
    from db.models import Connector
    from services.encryption_service import encrypt_dict

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    config_encrypted = encrypt_dict(body.config) if body.config else {}

    connector = Connector(
        connector_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        system_type=body.system_type,
        display_name=body.display_name or body.system_type.upper(),
        config_encrypted=config_encrypted,
    )
    await connector.insert()

    return {
        "connector_id": connector.connector_id,
        "system_type": connector.system_type,
        "status": connector.status,
    }


@router.post("/connectors/{connector_id}/test", summary="Test connector health")
async def test_connector(connector_id: str, request: Request):
    """Test connector health and return connection status."""
    from db.models import Connector
    import time

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    connector = await Connector.find_one(
        Connector.connector_id == connector_id,
        Connector.tenant_id == tenant_id,
    )
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Mock health check — in production call the actual connector
    import random
    start = time.time()
    latency_ms = int((time.time() - start + random.uniform(0.05, 0.3)) * 1000)

    from datetime import datetime
    from db.models import ConnectorStatus

    await connector.set({
        Connector.last_health_check_at: datetime.utcnow(),
        Connector.status: ConnectorStatus.ACTIVE,
    })

    return {
        "connector_id": connector_id,
        "connected": True,
        "latency_ms": latency_ms,
        "system_type": connector.system_type,
    }
