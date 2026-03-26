"""
Base Agent class for all AntiGravity agent families.
Provides: heartbeat loop, audit ledger writes, Kafka events,
Redis context cache, and MongoDB registration.
"""
import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

import redis.asyncio as redis_async
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

# LLM configuration — ALL agents use this model
LLM = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    temperature=0,
    max_tokens=4096,
)


class AuditWriteError(Exception):
    """Raised when audit record write fails permanently."""
    pass


class AgentToolError(Exception):
    """Base class for typed agent tool errors."""
    def __init__(self, message: str, error_code: str, is_retryable: bool = True):
        super().__init__(message)
        self.error_code = error_code
        self.is_retryable = is_retryable


class AuthorizationError(AgentToolError):
    def __init__(self, message: str):
        super().__init__(message, "AUTHORIZATION_ERROR", is_retryable=False)


class SchemaValidationError(AgentToolError):
    def __init__(self, message: str):
        super().__init__(message, "SCHEMA_VALIDATION_ERROR", is_retryable=False)


class DuplicateActionError(AgentToolError):
    def __init__(self, message: str):
        super().__init__(message, "DUPLICATE_ACTION_ERROR", is_retryable=False)


class BaseAgent(ABC):
    """
    Base class for all AntiGravity agents.

    Subclasses MUST:
    1. Call super().__init__() to register and start heartbeat
    2. Define self.family (AgentFamily enum value)
    3. Define self.SYSTEM_PROMPT
    4. Implement build_graph() to return a LangGraph StateGraph
    """

    HEARTBEAT_INTERVAL = 10  # seconds

    def __init__(self, tenant_id: str, capabilities: list[str] = None):
        self.agent_id = str(uuid.uuid4())
        self.tenant_id = tenant_id
        self.capabilities = capabilities or []
        self._redis: Optional[redis_async.Redis] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def initialize(self):
        """
        Register agent in MongoDB and start heartbeat loop.
        Call this after __init__ in async context.
        """
        from db.models import AgentInstance, AgentFamily, AgentStatus

        # Register in MongoDB
        instance = AgentInstance(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            family=AgentFamily(self.family),
            name=f"{self.family}-{self.agent_id[:8]}",
            status=AgentStatus.IDLE,
            capabilities=self.capabilities,
            last_heartbeat_at=datetime.utcnow(),
        )
        await instance.insert()
        logger.info(f"Agent {self.agent_id} ({self.family}) registered")

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def shutdown(self):
        """Gracefully shutdown the agent."""
        self._stop_event.set()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Update status to DISABLED
        from db.models import AgentInstance, AgentStatus
        await AgentInstance.find_one(AgentInstance.agent_id == self.agent_id).update(
            {"$set": {"status": AgentStatus.DISABLED}}
        )
        logger.info(f"Agent {self.agent_id} shut down")

    async def _heartbeat_loop(self):
        """Update lastHeartbeatAt every 10 seconds."""
        from db.models import AgentInstance
        while not self._stop_event.is_set():
            try:
                await AgentInstance.find_one(
                    AgentInstance.agent_id == self.agent_id
                ).update({"$set": {"last_heartbeat_at": datetime.utcnow()}})
            except Exception as e:
                logger.error(f"Heartbeat failed for agent {self.agent_id}: {e}")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.HEARTBEAT_INTERVAL,
                )
            except asyncio.TimeoutError:
                pass

    async def _get_redis(self) -> redis_async.Redis:
        """Get or create Redis connection."""
        import os
        if not self._redis:
            self._redis = await redis_async.from_url(
                os.environ.get("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
            )
        return self._redis

    async def write_audit_record(
        self,
        event_type: str,
        payload: dict[str, Any],
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        actor_type: str = "AGENT",
    ) -> None:
        """
        Write to the immutable audit ledger.
        NEVER fails silently — raises AuditWriteError which triggers human escalation.
        """
        from services import audit_service

        try:
            await audit_service.write(
                event_type=event_type,
                actor_type=actor_type,
                actor_id=self.agent_id,
                payload=payload,
                tenant_id=self.tenant_id,
                workflow_id=workflow_id,
                task_id=task_id,
            )
        except Exception as e:
            logger.critical(f"AUDIT WRITE FAILURE for agent {self.agent_id}: {e}")
            raise AuditWriteError(
                f"Critical: audit record write failed for event {event_type}: {e}"
            )

    async def emit_kafka_event(
        self,
        topic: str,
        event_type: str,
        data: dict[str, Any],
        workflow_id: Optional[str] = None,
    ) -> None:
        """Publish event to Kafka (async fire-and-forget)."""
        from kafka.producer import publish

        try:
            await publish(
                topic=topic,
                event_type=event_type,
                data=data,
                tenant_id=self.tenant_id,
                workflow_id=workflow_id,
                source=f"agent/{self.family}/{self.agent_id}",
            )
        except Exception as e:
            logger.error(f"Kafka emit failed: {e}")
            # Don't raise — Kafka failures should not block business logic

    async def load_context(self, workflow_id: str) -> dict[str, Any]:
        """
        Load workflow context. Checks Redis first, falls back to MongoDB.
        """
        from db.models import WorkflowRun

        try:
            r = await self._get_redis()
            cache_key = f"ctx:{self.tenant_id}:{workflow_id}"
            cached = await r.get(cache_key)
            if cached:
                import json
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis context cache miss: {e}")

        # Fall back to MongoDB
        run = await WorkflowRun.find_one(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.tenant_id == self.tenant_id,
        )
        if run:
            return run.context or {}
        return {}

    async def update_context(self, workflow_id: str, updates: dict[str, Any]) -> None:
        """
        Apply $set updates to workflowRuns.context and invalidate Redis cache.
        """
        from db.models import WorkflowRun

        # Build dot-notation update paths
        set_ops = {f"context.{k}": v for k, v in updates.items()}

        await WorkflowRun.find_one(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.tenant_id == self.tenant_id,
        ).update({"$set": set_ops})

        # Invalidate cache
        try:
            r = await self._get_redis()
            await r.delete(f"ctx:{self.tenant_id}:{workflow_id}")
        except Exception:
            pass

    async def set_agent_busy(self, task_id: str) -> None:
        """Mark agent as BUSY in MongoDB."""
        from db.models import AgentInstance, AgentStatus
        await AgentInstance.find_one(
            AgentInstance.agent_id == self.agent_id
        ).update({
            "$set": {
                "status": AgentStatus.BUSY,
                "current_task_id": task_id,
            }
        })

    async def set_agent_idle(self) -> None:
        """Mark agent as IDLE in MongoDB."""
        from db.models import AgentInstance, AgentStatus
        await AgentInstance.find_one(
            AgentInstance.agent_id == self.agent_id
        ).update({
            "$set": {
                "status": AgentStatus.IDLE,
                "current_task_id": None,
            }
        })

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent's system prompt."""
        pass

    @abstractmethod
    async def execute_task(
        self,
        task_id: str,
        workflow_id: str,
        task_definition: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a task and return the result."""
        pass
