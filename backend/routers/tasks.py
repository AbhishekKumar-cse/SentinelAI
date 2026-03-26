"""
Tasks Router — Human task inbox and management.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class CompleteTaskRequest(BaseModel):
    completion_notes: str
    outcome: Optional[str] = None


class ReassignTaskRequest(BaseModel):
    new_assignee_id: str
    reason: str


class ExtendTaskRequest(BaseModel):
    new_due_at: datetime
    reason: str


class EscalateTaskRequest(BaseModel):
    escalate_to_id: str
    reason: str


@router.get("/tasks", summary="Human task inbox")
async def list_tasks(
    request: Request,
    assignee_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    due_within_hours: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
    my_tasks_only: bool = Query(False),
):
    """Paginated human task inbox with filtering."""
    from db.models import HumanTask, HumanTaskStatus, Priority

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")
    role = getattr(request.state, "role", "AGENT_OPERATOR")

    filters = [HumanTask.tenant_id == tenant_id]

    # Role-based filtering
    if my_tasks_only or role == "AGENT_OPERATOR":
        filters.append(HumanTask.assignee_id == uid)
    elif assignee_id:
        filters.append(HumanTask.assignee_id == assignee_id)

    if status:
        try:
            filters.append(HumanTask.status == HumanTaskStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if priority:
        try:
            filters.append(HumanTask.priority == Priority(priority))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    if due_within_hours:
        from datetime import timedelta
        due_before = datetime.utcnow() + timedelta(hours=due_within_hours)
        filters.append(HumanTask.due_at <= due_before)

    tasks = await HumanTask.find(*filters).sort(-HumanTask.created_at).limit(limit).to_list()

    return {
        "tasks": [
            {
                "human_task_id": t.human_task_id,
                "workflow_id": t.workflow_id,
                "title": t.title,
                "description": t.description[:200],
                "assignee_id": t.assignee_id,
                "status": t.status,
                "priority": t.priority,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "reminder_count": t.reminder_count,
                "created_at": t.created_at.isoformat(),
                "deep_link": t.deep_link,
            }
            for t in tasks
        ],
        "count": len(tasks),
    }


@router.get("/tasks/{task_id}", summary="Task detail")
async def get_task(task_id: str, request: Request):
    """Task detail with full context snapshot and workflow position."""
    from db.models import HumanTask

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    task = await HumanTask.find_one(
        HumanTask.human_task_id == task_id,
        HumanTask.tenant_id == tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "human_task_id": task.human_task_id,
        "workflow_id": task.workflow_id,
        "title": task.title,
        "description": task.description,
        "assignee_id": task.assignee_id,
        "status": task.status,
        "priority": task.priority,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "context_snapshot": task.context_snapshot,
        "completion_notes": task.completion_notes,
        "outcome": task.outcome,
        "reminder_count": task.reminder_count,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.post("/tasks/{task_id}/complete", summary="Complete a task")
async def complete_task(task_id: str, body: CompleteTaskRequest, request: Request):
    """Mark a human task as complete and resume the workflow."""
    from db.models import HumanTask, HumanTaskStatus
    import services.audit_service as audit_service

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")

    task = await HumanTask.find_one(
        HumanTask.human_task_id == task_id,
        HumanTask.tenant_id == tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == HumanTaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task already completed")

    await task.set({
        HumanTask.status: HumanTaskStatus.COMPLETED,
        HumanTask.completion_notes: body.completion_notes,
        HumanTask.outcome: body.outcome,
        HumanTask.completed_at: datetime.utcnow(),
    })

    await audit_service.write(
        event_type="HUMAN_TASK_COMPLETED",
        actor_type="USER",
        actor_id=uid,
        payload={
            "task_id": task_id,
            "completion_notes": body.completion_notes,
            "outcome": body.outcome,
        },
        tenant_id=tenant_id,
        workflow_id=task.workflow_id,
        task_id=task_id,
    )

    # Emit Kafka event to resume workflow task
    from kafka.producer import publish
    await publish(
        topic="human.tasks",
        event_type="HumanTaskCompleted",
        data={
            "human_task_id": task_id,
            "workflow_id": task.workflow_id,
            "outcome": body.outcome,
        },
        tenant_id=tenant_id,
        workflow_id=task.workflow_id,
    )

    return {"status": "COMPLETED", "task_id": task_id}


@router.post("/tasks/{task_id}/reassign", summary="Reassign task")
async def reassign_task(task_id: str, body: ReassignTaskRequest, request: Request):
    """Reassign a task to a different user."""
    from db.models import HumanTask
    import services.audit_service as audit_service

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    uid = getattr(request.state, "uid", "dev_user_001")

    task = await HumanTask.find_one(
        HumanTask.human_task_id == task_id,
        HumanTask.tenant_id == tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_assignee = task.assignee_id
    await task.set({HumanTask.assignee_id: body.new_assignee_id})

    await audit_service.write(
        event_type="HUMAN_TASK_REASSIGNED",
        actor_type="USER",
        actor_id=uid,
        payload={
            "task_id": task_id,
            "from_assignee": old_assignee,
            "to_assignee": body.new_assignee_id,
            "reason": body.reason,
        },
        tenant_id=tenant_id,
        workflow_id=task.workflow_id,
    )

    return {"status": "REASSIGNED", "new_assignee_id": body.new_assignee_id}


@router.post("/tasks/{task_id}/extend", summary="Extend task due date")
async def extend_task(task_id: str, body: ExtendTaskRequest, request: Request):
    """Extend the due date of a task."""
    from db.models import HumanTask

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    task = await HumanTask.find_one(
        HumanTask.human_task_id == task_id,
        HumanTask.tenant_id == tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task.set({HumanTask.due_at: body.new_due_at})

    return {"status": "EXTENDED", "new_due_at": body.new_due_at.isoformat()}


@router.post("/tasks/{task_id}/escalate", summary="Escalate task urgency")
async def escalate_task(task_id: str, body: EscalateTaskRequest, request: Request):
    """Escalate task urgency to a senior person."""
    from db.models import HumanTask, Priority

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    task = await HumanTask.find_one(
        HumanTask.human_task_id == task_id,
        HumanTask.tenant_id == tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await task.set({
        HumanTask.priority: Priority.CRITICAL,
        HumanTask.assignee_id: body.escalate_to_id,
    })

    return {"status": "ESCALATED", "escalated_to": body.escalate_to_id}
