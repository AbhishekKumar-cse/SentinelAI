"""
WebSocket Router — Real-time event push via MongoDB Change Streams.
Authenticated via ?token= query param (Firebase ID token).
Streams: WorkflowUpdated, TaskStatusChanged, NewHumanTask, NewAuditEvent, EscalationTriggered.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections keyed by tenant_id."""

    def __init__(self):
        # tenant_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}

    def add(self, tenant_id: str, ws: WebSocket):
        if tenant_id not in self._connections:
            self._connections[tenant_id] = set()
        self._connections[tenant_id].add(ws)
        logger.info(f"WS connected: tenant={tenant_id}, total={len(self._connections[tenant_id])}")

    def remove(self, tenant_id: str, ws: WebSocket):
        if tenant_id in self._connections:
            self._connections[tenant_id].discard(ws)
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]
        logger.info(f"WS disconnected: tenant={tenant_id}")

    async def broadcast(self, tenant_id: str, event: dict):
        """Broadcast an event to all WebSocket connections for a tenant."""
        connections = self._connections.get(tenant_id, set()).copy()
        dead_connections = set()

        for ws in connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(event, default=str))
            except Exception as e:
                logger.warning(f"WS send failed: {e}")
                dead_connections.add(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.remove(tenant_id, ws)

    def connection_count(self, tenant_id: str) -> int:
        return len(self._connections.get(tenant_id, set()))


# Singleton connection manager
manager = ConnectionManager()


def _serialize_change_event(collection: str, operation: str, doc: dict) -> dict:
    """Map MongoDB change stream events to AntiGravity event types."""
    event_type_map = {
        "workflowRuns": "WorkflowUpdated",
        "workflowTasks": "TaskStatusChanged",
        "humanTasks": "NewHumanTask" if operation == "insert" else "HumanTaskUpdated",
        "auditRecords": "NewAuditEvent",
        "escalations": "EscalationTriggered",
    }

    return {
        "event_type": event_type_map.get(collection, f"{collection}Changed"),
        "operation": operation,
        "collection": collection,
        "data": doc,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def watch_collection(
    tenant_id: str,
    collection_name: str,
    websocket: WebSocket,
):
    """
    Watch a specific MongoDB collection for changes and push to WebSocket.
    Filters by tenantId for multi-tenancy isolation.
    """
    from db.mongodb import get_db

    db = get_db()
    collection = db[collection_name]

    # Define the change stream pipeline — filter by tenantId
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"fullDocument.tenant_id": tenant_id},
                    {"updateDescription.updatedFields.tenant_id": tenant_id},
                ]
            }
        }
    ]

    try:
        async with collection.watch(
            pipeline,
            full_document="updateLookup",
        ) as stream:
            while True:
                # Check if WebSocket is still connected
                if websocket.client_state != WebSocketState.CONNECTED:
                    break

                # Non-blocking check for next change event
                try:
                    change = await asyncio.wait_for(stream.next(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if change:
                    operation = change.get("operationType", "unknown")
                    doc = change.get("fullDocument", {})

                    # Remove MongoDB internal fields
                    doc.pop("_id", None)
                    doc.pop("config_encrypted", None)  # Never send encrypted config

                    event = _serialize_change_event(collection_name, operation, doc)
                    await manager.broadcast(tenant_id, event)

    except Exception as e:
        logger.error(f"Change stream error on {collection_name}: {e}")


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time event streaming.
    Authentication: ?token=<Firebase_ID_token>
    Streams events for the authenticated tenant.
    """
    # Authenticate via Firebase ID token
    tenant_id = "dev_tenant_001"  # Default for dev

    if token:
        try:
            from middleware.firebase_auth import get_firebase_app
            import os
            firebase_app = get_firebase_app()

            if firebase_app:
                from firebase_admin import auth
                decoded = auth.verify_id_token(token, app=firebase_app)
                tenant_id = decoded.get("tenantId", "dev_tenant_001")
            elif os.environ.get("ENVIRONMENT") == "development":
                # Dev bypass
                tenant_id = "dev_tenant_001"
            else:
                await websocket.close(code=4001, reason="Authentication required")
                return

        except Exception as e:
            logger.warning(f"WS auth failed: {e}")
            if os.environ.get("ENVIRONMENT") != "development":
                await websocket.close(code=4001, reason="Authentication failed")
                return

    await websocket.accept()
    manager.add(tenant_id, websocket)

    # Send connected acknowledgment
    await websocket.send_text(json.dumps({
        "event_type": "Connected",
        "tenant_id": tenant_id,
        "message": "Real-time event stream connected",
        "timestamp": datetime.utcnow().isoformat(),
    }))

    # Start watching all 5 collections simultaneously
    WATCHED_COLLECTIONS = [
        "workflowRuns",
        "workflowTasks",
        "humanTasks",
        "auditRecords",
        "escalations",
    ]

    watch_tasks = [
        asyncio.create_task(
            watch_collection(tenant_id, collection, websocket)
        )
        for collection in WATCHED_COLLECTIONS
    ]

    # Also start a heartbeat task
    async def heartbeat():
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_text(json.dumps({"event_type": "Heartbeat", "timestamp": datetime.utcnow().isoformat()}))
                await asyncio.sleep(30)
            except Exception:
                break

    watch_tasks.append(asyncio.create_task(heartbeat()))

    try:
        # Wait for client disconnect
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                # Handle client messages (ping/pong, filter updates)
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    pass
            except asyncio.TimeoutError:
                # Send ping
                try:
                    await websocket.send_text(json.dumps({"event_type": "Ping"}))
                except Exception:
                    break
            except WebSocketDisconnect:
                break

    finally:
        # Clean up
        for task in watch_tasks:
            task.cancel()
        await asyncio.gather(*watch_tasks, return_exceptions=True)
        manager.remove(tenant_id, websocket)
