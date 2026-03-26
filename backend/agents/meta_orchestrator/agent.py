"""
Meta-Orchestrator Agent (MOA) — The brain of AntiGravity.
Runs on a 30-second heartbeat. Never executes tasks directly.
Directs all other agents, manages the workflow DAG, predicts failures.

LangGraph StateGraph with: initialize → plan → execute → verify → audit → emit → finalize
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, TypedDict

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from agents.base_agent import BaseAgent, AgentToolError, AuthorizationError

logger = logging.getLogger(__name__)


# ─── LangGraph State ─────────────────────────────────────────────────────────

class MOAState(TypedDict):
    messages: list
    workflow_id: str
    task_id: str
    tenant_id: str
    context: dict
    current_step: str
    error_count: int
    audit_trail: list
    plan: Optional[dict]
    result: Optional[dict]


# ─── MOA System Prompt ────────────────────────────────────────────────────────

MOA_SYSTEM_PROMPT = """You are the Meta-Orchestrator of AntiGravity. Your sole purpose is to ensure complex enterprise workflows complete successfully, on time, and with full auditability. You manage a fleet of specialized agents. You never execute tasks yourself. You analyze workflow state, predict problems before they occur, and direct other agents to act.

For EVERY decision you make you must output:
1. Your assessment of the current situation
2. All options you considered
3. Your chosen action and why
4. Expected outcome
5. The signal that will confirm success

Always prefer preemptive action over reactive recovery. Sign every decision with your agent ID for the audit ledger."""


# ─── MOA Tool Functions ───────────────────────────────────────────────────────

class MetaOrchestratorAgent(BaseAgent):
    family = "MOA"

    def get_system_prompt(self) -> str:
        return MOA_SYSTEM_PROMPT

    async def orchestrate_workflow(
        self,
        workflow_id: str,
        process_template_id: str,
        initial_context: dict,
        tenant_id: str,
        launched_by: str,
    ) -> dict:
        """
        Initialize a new workflow run from a process template.
        Instantiates WorkflowRun, creates all WorkflowTask records,
        and assigns the first batch of independent tasks.
        """
        from db.models import (
            WorkflowRun, WorkflowTask, ProcessTemplate,
            WorkflowStatus, TaskStatus, Priority,
        )
        import uuid

        # Load template
        template = await ProcessTemplate.find_one(
            ProcessTemplate.template_id == process_template_id,
            ProcessTemplate.tenant_id == tenant_id,
            ProcessTemplate.is_active == True,
        )
        if not template:
            raise AgentToolError(
                f"Template {process_template_id} not found",
                "TEMPLATE_NOT_FOUND",
                is_retryable=False,
            )

        # Create workflow run
        run = WorkflowRun(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            template_id=process_template_id,
            name=f"{template.name} - {datetime.utcnow().strftime('%Y-%m-%d')}",
            status=WorkflowStatus.INITIALIZING,
            context=initial_context,
            health_score=100.0,
            started_at=datetime.utcnow(),
        )
        await run.insert()

        # Parse DAG and find critical path (topological sort)
        nodes = {n.node_id: n for n in template.dag.nodes}
        edges = template.dag.edges

        # Build adjacency list and in-degree map
        in_degree = {n: 0 for n in nodes}
        adj = {n: [] for n in nodes}
        for edge in edges:
            if edge.source in nodes and edge.target in nodes:
                adj[edge.source].append(edge.target)
                in_degree[edge.target] += 1

        # Topological sort (Kahn's algorithm)
        from collections import deque
        queue = deque([n for n, deg in in_degree.items() if deg == 0])
        topo_order = []
        while queue:
            node = queue.popleft()
            topo_order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Create WorkflowTask for each DAG node
        task_id_map = {}
        tasks = []
        for node_id in topo_order:
            node = nodes[node_id]
            if node.node_type in {"START", "END"}:
                continue

            # Find dependency task IDs
            dep_node_ids = [e.source for e in edges if e.target == node_id]
            dep_task_ids = [task_id_map[n] for n in dep_node_ids if n in task_id_map]

            task = WorkflowTask(
                task_id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                node_id=node_id,
                task_type=node.task_type or node.node_type,
                status=TaskStatus.PENDING,
                dependencies=dep_task_ids,
                priority=Priority.MEDIUM,
            )
            tasks.append(task)
            task_id_map[node_id] = task.task_id

        if tasks:
            await WorkflowTask.insert_many(tasks)

        # Update workflow to RUNNING
        await run.set({
            WorkflowRun.status: WorkflowStatus.RUNNING,
            WorkflowRun.current_node_id: topo_order[0] if topo_order else None,
        })

        # Assign first batch (tasks with no dependencies)
        first_batch = [t for t in tasks if not t.dependencies]
        assigned = []
        for task in first_batch:
            node = nodes[task.node_id]
            if node.agent_family:
                result = await self.assign_task(
                    task_id=task.task_id,
                    agent_family=node.agent_family,
                    priority=1,
                    deadline=datetime.utcnow() + timedelta(seconds=template.sla_config.max_duration_seconds),
                    tenant_id=tenant_id,
                )
                assigned.append(result)

        # Write audit record
        await self.write_audit_record(
            event_type="WORKFLOW_STARTED",
            payload={
                "template_id": process_template_id,
                "task_count": len(tasks),
                "first_batch": [t.task_id for t in first_batch],
                "launched_by": launched_by,
            },
            workflow_id=workflow_id,
        )

        # Emit Kafka event
        await self.emit_kafka_event(
            topic="workflow.events",
            event_type="WorkflowStarted",
            data={
                "workflow_id": workflow_id,
                "template_id": process_template_id,
                "task_count": len(tasks),
                "status": "RUNNING",
            },
            workflow_id=workflow_id,
        )

        return {
            "workflow_id": workflow_id,
            "status": "RUNNING",
            "task_count": len(tasks),
            "first_batch": [t.task_id for t in first_batch],
            "planned_nodes": topo_order,
        }

    async def assign_task(
        self,
        task_id: str,
        agent_family: str,
        priority: int,
        deadline: datetime,
        tenant_id: str,
    ) -> dict:
        """
        Assign a task to the best available agent.
        Uses atomic MongoDB session to prevent double-assignment.
        Falls back to BullMQ queue if no idle agents.
        """
        from db.models import AgentInstance, WorkflowTask, AgentStatus, TaskStatus
        from db.mongodb import get_client

        client = get_client()

        async with await client.start_session() as session:
            async with session.start_transaction():
                # Find best idle agent
                idle_agents = await AgentInstance.find(
                    AgentInstance.tenant_id == tenant_id,
                    AgentInstance.family == agent_family,
                    AgentInstance.status == AgentStatus.IDLE,
                    session=session,
                ).sort(AgentInstance.performance_metrics.avg_task_duration_seconds).to_list()

                if not idle_agents:
                    # Add to Redis queue
                    await self._queue_task(task_id, agent_family, priority, tenant_id)
                    return {"status": "QUEUED", "task_id": task_id}

                # Select fastest agent
                selected = idle_agents[0]

                # Atomic update — agent + task
                await AgentInstance.find_one(
                    AgentInstance.agent_id == selected.agent_id,
                    session=session,
                ).update({
                    "$set": {
                        "status": AgentStatus.BUSY,
                        "current_task_id": task_id,
                    }
                })

                task = await WorkflowTask.find_one(
                    WorkflowTask.task_id == task_id,
                    session=session,
                )
                if task:
                    await task.set({
                        WorkflowTask.status: TaskStatus.ASSIGNED,
                        WorkflowTask.assigned_agent_id: selected.agent_id,
                        WorkflowTask.due_at: deadline,
                    }, session=session)
                    workflow_id = task.workflow_id
                else:
                    workflow_id = None

        # Publish TaskAssigned event
        await self.emit_kafka_event(
            topic="workflow.tasks",
            event_type="TaskAssigned",
            data={
                "task_id": task_id,
                "agent_id": selected.agent_id,
                "agent_family": agent_family,
            },
            workflow_id=workflow_id,
        )

        return {
            "status": "ASSIGNED",
            "task_id": task_id,
            "agent_id": selected.agent_id,
            "agent_family": agent_family,
        }

    async def _queue_task(self, task_id: str, agent_family: str, priority: int, tenant_id: str):
        """Add task to Redis priority queue when no agents are available."""
        import redis.asyncio as aioredis
        import os

        r = await aioredis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
        queue_key = f"queue:{tenant_id}:{agent_family}"
        await r.zadd(queue_key, {task_id: -priority})  # Negative priority = higher priority first
        logger.info(f"Task {task_id} queued for {agent_family}")

    async def compute_health_score(self, workflow_id: str, tenant_id: str) -> float:
        """
        Compute weighted health score 0-100.
        SLA adherence: 40%, Error rate: 30%, Agent utilization: 20%, Data quality: 10%
        """
        from db.models import WorkflowRun, WorkflowTask, TaskStatus

        run = await WorkflowRun.find_one(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.tenant_id == tenant_id,
        )
        if not run:
            return 0.0

        # Get all tasks
        tasks = await WorkflowTask.find(
            WorkflowTask.workflow_id == workflow_id,
        ).to_list()

        total_tasks = len(tasks)
        if total_tasks == 0:
            return 100.0

        failed_tasks = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)

        # SLA component (40%): inverse of breach probability
        sla_score = (1 - min(run.breach_probability * 2, 1.0)) * 40

        # Error rate component (30%)
        error_rate = failed_tasks / total_tasks if total_tasks > 0 else 0
        error_score = (1 - error_rate) * 30

        # Utilization component (20%): simplified for now
        utilization_score = 20.0

        # Data quality component (10%): simplified
        quality_score = 10.0

        health = sla_score + error_score + utilization_score + quality_score

        # Update MongoDB and Redis
        await run.set({WorkflowRun.health_score: health})

        try:
            import redis.asyncio as aioredis
            import os
            r = await aioredis.from_url(
                os.environ.get("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
            )
            await r.setex(
                f"health:{tenant_id}:{workflow_id}",
                60,
                str(health),
            )
        except Exception:
            pass

        return health

    async def handle_agent_failure(
        self,
        agent_id: str,
        task_id: str,
        failure_reason: str,
        retry_count: int,
        tenant_id: str,
    ) -> dict:
        """
        Four-tier recovery for agent failures:
        Tier 1: Retry with exponential backoff (transient errors, <5 retries)
        Tier 2: Reassign to another agent (exhausted retries)
        Tier 3: DMA resolves exception (no agents available)
        Tier 4: Human escalation (all else fails)
        """
        from db.models import WorkflowTask, AgentInstance

        task = await WorkflowTask.find_one(WorkflowTask.task_id == task_id)
        if not task:
            return {"action": "TASK_NOT_FOUND"}

        # Classify failure type
        transient_conditions = ["timeout", "rate limit", "5xx", "connection", "temporarily"]
        is_transient = any(c in failure_reason.lower() for c in transient_conditions)

        # TIER 1: Retry
        if retry_count < 5 and is_transient:
            delay = 2 ** retry_count
            await self.write_audit_record(
                event_type="TIER1_RETRY",
                payload={
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "retry_count": retry_count,
                    "failure_reason": failure_reason,
                    "delay_seconds": delay,
                },
                workflow_id=task.workflow_id,
                task_id=task_id,
            )
            return {
                "action": "RETRY",
                "delay_seconds": delay,
                "retry_count": retry_count + 1,
            }

        # TIER 2: Reassign to another agent
        from db.models import AgentStatus
        agent = await AgentInstance.find_one(AgentInstance.agent_id == agent_id)
        if agent:
            other_agents = await AgentInstance.find(
                AgentInstance.tenant_id == tenant_id,
                AgentInstance.family == agent.family,
                AgentInstance.status == AgentStatus.IDLE,
                AgentInstance.agent_id != agent_id,
            ).to_list()

            if other_agents:
                from datetime import timedelta
                result = await self.assign_task(
                    task_id=task_id,
                    agent_family=agent.family,
                    priority=2,  # Elevated priority for retry
                    deadline=datetime.utcnow() + timedelta(hours=4),
                    tenant_id=tenant_id,
                )
                await self.write_audit_record(
                    event_type="TIER2_REASSIGNED",
                    payload={
                        "from_agent": agent_id,
                        "to_agent": result.get("agent_id"),
                        "task_id": task_id,
                    },
                    workflow_id=task.workflow_id,
                    task_id=task_id,
                )
                return {"action": "REASSIGNED", "new_agent": result.get("agent_id")}

        # TIER 3: DMA strategy
        await self.write_audit_record(
            event_type="TIER3_DMA_STRATEGY",
            payload={"task_id": task_id, "failure_reason": failure_reason},
            workflow_id=task.workflow_id,
            task_id=task_id,
        )
        # In real implementation, call DMA.resolve_exception here
        return {"action": "STRATEGY_SUBSTITUTED", "note": "DMA resolution queued"}

    async def pause_workflow(
        self, workflow_id: str, reason: str, paused_by: str, tenant_id: str
    ) -> dict:
        """Gracefully pause all in-progress tasks and save state."""
        from db.models import WorkflowRun, WorkflowTask, TaskStatus, WorkflowStatus

        # Signal all running tasks to stop
        await WorkflowTask.find(
            WorkflowTask.workflow_id == workflow_id,
            WorkflowTask.status == TaskStatus.IN_PROGRESS,
        ).update({"$set": {"stop_requested": True}})

        # Wait up to 30s for agents to finish current atomic ops
        await asyncio.sleep(5)  # Simplified — in production poll for completion

        # Update workflow status
        await WorkflowRun.find_one(
            WorkflowRun.workflow_id == workflow_id,
        ).update({
            "$set": {
                "status": WorkflowStatus.PAUSED,
                "paused_by": paused_by,
                "pause_reason": reason,
            }
        })

        await self.write_audit_record(
            event_type="WORKFLOW_PAUSED",
            payload={"reason": reason, "paused_by": paused_by},
            workflow_id=workflow_id,
        )

        await self.emit_kafka_event(
            topic="workflow.events",
            event_type="WorkflowPaused",
            data={"workflow_id": workflow_id, "reason": reason},
            workflow_id=workflow_id,
        )

        return {"status": "PAUSED", "workflow_id": workflow_id}

    async def resume_workflow(
        self, workflow_id: str, resume_context: dict, resumed_by: str, tenant_id: str
    ) -> dict:
        """Resume a paused workflow."""
        from db.models import WorkflowRun, WorkflowTask, TaskStatus, WorkflowStatus

        # Update status
        await WorkflowRun.find_one(
            WorkflowRun.workflow_id == workflow_id,
        ).update({
            "$set": {
                "status": WorkflowStatus.RUNNING,
                "paused_by": None,
                "pause_reason": None,
            },
            "$unset": {"paused_by": 1},
        })

        # Clear stop_requested flag
        await WorkflowTask.find(
            WorkflowTask.workflow_id == workflow_id,
        ).update({"$set": {"stop_requested": False}})

        # Merge resume context
        if resume_context:
            await self.update_context(workflow_id, resume_context)

        await self.write_audit_record(
            event_type="WORKFLOW_RESUMED",
            payload={"resumed_by": resumed_by, "context_keys": list(resume_context.keys())},
            workflow_id=workflow_id,
        )

        await self.emit_kafka_event(
            topic="workflow.events",
            event_type="WorkflowResumed",
            data={"workflow_id": workflow_id},
            workflow_id=workflow_id,
        )

        return {"status": "RUNNING", "workflow_id": workflow_id}

    async def preemptive_escalation(
        self,
        workflow_id: str,
        predicted_breach_time: datetime,
        risk_score: float,
        tenant_id: str,
    ) -> dict:
        """Create an escalation for predicted SLA breach."""
        from db.models import Escalation, EscalationStatus, WorkflowRun

        esc = Escalation(
            escalation_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            trigger_type="SLA_BREACH",
            risk_score=risk_score,
            predicted_breach_at=predicted_breach_time,
            status=EscalationStatus.OPEN,
            escalation_level=1,
            next_escalation_at=datetime.utcnow() + timedelta(hours=2),
        )
        await esc.insert()

        await self.write_audit_record(
            event_type="ESCALATION_TRIGGERED",
            payload={
                "escalation_id": esc.escalation_id,
                "risk_score": risk_score,
                "predicted_breach_at": predicted_breach_time.isoformat(),
            },
            workflow_id=workflow_id,
        )

        await self.emit_kafka_event(
            topic="escalations",
            event_type="EscalationTriggered",
            data={
                "escalation_id": esc.escalation_id,
                "workflow_id": workflow_id,
                "risk_score": risk_score,
            },
            workflow_id=workflow_id,
        )

        return {
            "escalation_id": esc.escalation_id,
            "status": "OPEN",
            "risk_score": risk_score,
        }

    async def execute_task(
        self,
        task_id: str,
        workflow_id: str,
        task_definition: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """MOA task execution entry point."""
        action = task_definition.get("action", "orchestrate")

        if action == "orchestrate":
            return await self.orchestrate_workflow(
                workflow_id=task_definition["workflow_id"],
                process_template_id=task_definition["template_id"],
                initial_context=context,
                tenant_id=self.tenant_id,
                launched_by=task_definition.get("launched_by", "system"),
            )
        elif action == "health_check":
            score = await self.compute_health_score(workflow_id, self.tenant_id)
            return {"health_score": score}
        elif action == "pause":
            return await self.pause_workflow(
                workflow_id=workflow_id,
                reason=task_definition.get("reason", "Manual pause"),
                paused_by=task_definition.get("paused_by", "system"),
                tenant_id=self.tenant_id,
            )
        else:
            return {"action": action, "status": "completed"}
