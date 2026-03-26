"""
Workflows Router — all workflow CRUD and control endpoints.
POST/GET /api/v1/workflows, workflow control (pause/resume/cancel), audit, health, decisions.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from middleware.firebase_auth import require_role

router = APIRouter()


# ─── Request/Response Models ──────────────────────────────────────────────────

class LaunchWorkflowRequest(BaseModel):
    template_id: str
    initial_context: dict = Field(default_factory=dict)
    sla_overrides: Optional[dict] = None
    name: Optional[str] = None


class PauseWorkflowRequest(BaseModel):
    reason: str


class ResumeWorkflowRequest(BaseModel):
    resume_context: dict = Field(default_factory=dict)


class CancelWorkflowRequest(BaseModel):
    reason: str
    execute_rollback: bool = False


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/workflows", summary="Launch a new workflow run")
async def launch_workflow(body: LaunchWorkflowRequest, request: Request):
    """
    Launch a new workflow from a process template.
    Creates WorkflowRun, instantiates tasks from DAG, assigns first batch to agents.
    """
    from db.models import ProcessTemplate, WorkflowRun, WorkflowStatus
    from agents.meta_orchestrator.agent import MetaOrchestratorAgent
    import services.audit_service as audit_service

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")

    # Verify template exists
    template = await ProcessTemplate.find_one(
        ProcessTemplate.template_id == body.template_id,
        ProcessTemplate.tenant_id == tenant_id,
        ProcessTemplate.is_active == True,
    )
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {body.template_id} not found")

    workflow_id = str(uuid.uuid4())

    # Create MOA and orchestrate
    moa = MetaOrchestratorAgent(tenant_id=tenant_id)
    await moa.initialize()

    try:
        result = await moa.orchestrate_workflow(
            workflow_id=workflow_id,
            process_template_id=body.template_id,
            initial_context=body.initial_context,
            tenant_id=tenant_id,
            launched_by=uid,
        )

        return {
            "workflow_id": workflow_id,
            "status": "RUNNING",
            "template_id": body.template_id,
            "planned_tasks": result.get("task_count", 0),
            "message": "Workflow launched successfully",
        }
    finally:
        await moa.shutdown()


@router.get("/workflows", summary="List workflow runs")
async def list_workflows(
    request: Request,
    status: Optional[str] = Query(None),
    template_id: Optional[str] = Query(None),
    started_after: Optional[datetime] = Query(None),
    started_before: Optional[datetime] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
):
    """Paginated list of workflow runs with filtering."""
    from db.models import WorkflowRun, WorkflowStatus

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    filters = [WorkflowRun.tenant_id == tenant_id]

    if status:
        try:
            filters.append(WorkflowRun.status == WorkflowStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if template_id:
        filters.append(WorkflowRun.template_id == template_id)

    if started_after:
        filters.append(WorkflowRun.started_at >= started_after)

    if started_before:
        filters.append(WorkflowRun.started_at <= started_before)

    # Cursor-based pagination
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            filters.append(WorkflowRun.started_at < cursor_dt)
        except ValueError:
            pass

    runs = await WorkflowRun.find(*filters).sort(-WorkflowRun.started_at).limit(limit).to_list()

    next_cursor = None
    if len(runs) == limit and runs:
        next_cursor = runs[-1].started_at.isoformat() if runs[-1].started_at else None

    return {
        "workflows": [
            {
                "workflow_id": r.workflow_id,
                "name": r.name,
                "template_id": r.template_id,
                "status": r.status,
                "health_score": r.health_score,
                "sla_status": r.sla_status,
                "breach_probability": r.breach_probability,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ],
        "next_cursor": next_cursor,
        "count": len(runs),
    }


@router.get("/workflows/{workflow_id}", summary="Get workflow detail")
async def get_workflow(workflow_id: str, request: Request):
    """Full workflow detail with embedded tasks, agent assignments, and context summary."""
    from db.models import WorkflowRun, WorkflowTask

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    run = await WorkflowRun.find_one(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.tenant_id == tenant_id,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")

    tasks = await WorkflowTask.find(
        WorkflowTask.workflow_id == workflow_id,
    ).to_list()

    return {
        "workflow_id": run.workflow_id,
        "name": run.name,
        "template_id": run.template_id,
        "status": run.status,
        "health_score": run.health_score,
        "sla_status": run.sla_status,
        "breach_probability": run.breach_probability,
        "context_summary": {k: str(v)[:100] for k, v in (run.context or {}).items()},
        "current_node_id": run.current_node_id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "assigned_agents": run.assigned_agents,
        "tasks": [
            {
                "task_id": t.task_id,
                "node_id": t.node_id,
                "task_type": t.task_type,
                "status": t.status,
                "assigned_agent_id": t.assigned_agent_id,
                "priority": t.priority,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "attempt_count": t.attempt_count,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
    }


@router.post("/workflows/{workflow_id}/pause", summary="Pause workflow")
async def pause_workflow(workflow_id: str, body: PauseWorkflowRequest, request: Request):
    """Gracefully pause all in-progress tasks and save agent state."""
    from db.models import WorkflowRun
    from agents.meta_orchestrator.agent import MetaOrchestratorAgent

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")

    run = await WorkflowRun.find_one(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.tenant_id == tenant_id,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")

    moa = MetaOrchestratorAgent(tenant_id=tenant_id)
    await moa.initialize()
    try:
        result = await moa.pause_workflow(
            workflow_id=workflow_id,
            reason=body.reason,
            paused_by=uid,
            tenant_id=tenant_id,
        )
        return result
    finally:
        await moa.shutdown()


@router.post("/workflows/{workflow_id}/resume", summary="Resume paused workflow")
async def resume_workflow(workflow_id: str, body: ResumeWorkflowRequest, request: Request):
    """Resume a paused workflow, optionally merging new context."""
    from db.models import WorkflowRun, WorkflowStatus
    from agents.meta_orchestrator.agent import MetaOrchestratorAgent

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")

    run = await WorkflowRun.find_one(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.tenant_id == tenant_id,
    )
    if not run or run.status != WorkflowStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Workflow not found or not in PAUSED state")

    moa = MetaOrchestratorAgent(tenant_id=tenant_id)
    await moa.initialize()
    try:
        result = await moa.resume_workflow(
            workflow_id=workflow_id,
            resume_context=body.resume_context,
            resumed_by=uid,
            tenant_id=tenant_id,
        )
        return result
    finally:
        await moa.shutdown()


@router.post("/workflows/{workflow_id}/cancel", summary="Cancel workflow")
async def cancel_workflow(workflow_id: str, body: CancelWorkflowRequest, request: Request):
    """Cancel a workflow. Optionally triggers saga rollback for completed actions."""
    from db.models import WorkflowRun, WorkflowStatus, WorkflowTask, TaskStatus
    import services.audit_service as audit_service

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")

    run = await WorkflowRun.find_one(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.tenant_id == tenant_id,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Cancel all pending/assigned tasks
    await WorkflowTask.find(
        WorkflowTask.workflow_id == workflow_id,
        WorkflowTask.status.in_([TaskStatus.PENDING, TaskStatus.ASSIGNED]),
    ).update({"$set": {"status": TaskStatus.CANCELLED}})

    # Update workflow
    await run.set({
        WorkflowRun.status: WorkflowStatus.CANCELLED,
        WorkflowRun.completed_at: datetime.utcnow(),
    })

    await audit_service.write(
        event_type="WORKFLOW_CANCELLED",
        actor_type="USER",
        actor_id=uid,
        payload={"reason": body.reason, "execute_rollback": body.execute_rollback},
        tenant_id=tenant_id,
        workflow_id=workflow_id,
    )

    return {"status": "CANCELLED", "workflow_id": workflow_id}


@router.get("/workflows/{workflow_id}/audit", summary="Workflow audit trail")
async def get_audit_trail(
    workflow_id: str,
    request: Request,
    event_type: Optional[str] = Query(None),
    actor_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Paginated audit trail with hash chain status."""
    from services import audit_service

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    result = await audit_service.query_audit_trail(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        event_type=event_type,
        actor_type=actor_type,
        limit=limit,
        cursor=cursor,
    )
    return result


@router.get("/workflows/{workflow_id}/health", summary="Workflow health score")
async def get_workflow_health(workflow_id: str, request: Request):
    """Current health score, SLA status, breach probability."""
    from db.models import WorkflowRun, WorkflowTask, TaskStatus

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    # Try Redis cache first
    try:
        import redis.asyncio as aioredis
        import os
        r = await aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        cached_score = await r.get(f"health:{tenant_id}:{workflow_id}")
        if cached_score:
            health_score = float(cached_score)
        else:
            health_score = None
    except Exception:
        health_score = None

    run = await WorkflowRun.find_one(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.tenant_id == tenant_id,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if health_score is None:
        health_score = run.health_score

    tasks = await WorkflowTask.find(WorkflowTask.workflow_id == workflow_id).to_list()
    task_stats = {
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
        "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
        "in_progress": sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS),
        "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
    }

    return {
        "workflow_id": workflow_id,
        "health_score": health_score,
        "sla_status": run.sla_status,
        "breach_probability": run.breach_probability,
        "task_stats": task_stats,
        "status": run.status,
    }


@router.get("/workflows/{workflow_id}/decisions", summary="Workflow decisions")
async def get_workflow_decisions(
    workflow_id: str,
    request: Request,
    min_confidence: Optional[float] = Query(None),
    decision_type: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """All DMA decisions for this workflow."""
    from db.models import DecisionRecord

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")

    filters = [
        DecisionRecord.workflow_id == workflow_id,
        DecisionRecord.tenant_id == tenant_id,
    ]
    if min_confidence is not None:
        filters.append(DecisionRecord.confidence >= min_confidence)
    if decision_type:
        filters.append(DecisionRecord.decision_type == decision_type)

    records = await DecisionRecord.find(*filters).sort(-DecisionRecord.created_at).limit(limit).to_list()

    return {
        "decisions": [
            {
                "decision_id": r.decision_id,
                "decision_type": r.decision_type,
                "decision_value": r.decision_value,
                "confidence": r.confidence,
                "requires_human_review": r.requires_human_review,
                "reasoning_trace": r.reasoning_trace,
                "model_version": r.model_version,
                "created_at": r.created_at.isoformat(),
                "agent_id": r.agent_id,
            }
            for r in records
        ],
        "count": len(records),
    }
