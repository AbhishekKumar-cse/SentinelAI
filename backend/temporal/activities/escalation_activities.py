"""
Temporal Activities — Escalation Workflow.
"""
import logging
import uuid
from datetime import datetime
from temporalio import activity

logger = logging.getLogger(__name__)

ESCALATION_ROLE_MAP = {
    0: "AGENT_OPERATOR",
    1: "WORKFLOW_MANAGER",
    2: "TENANT_ADMIN",
    3: "TENANT_ADMIN",
}


@activity.defn(name="create_human_task")
async def create_human_task(workflow_id: str, tenant_id: str, task_config: dict) -> str:
    """Create a HumanTask document."""
    from db.models import HumanTask, HumanTaskStatus, Priority
    from datetime import timedelta

    activity.heartbeat("Creating human task")

    priority_str = task_config.get("priority", "HIGH")
    try:
        priority = Priority(priority_str)
    except ValueError:
        priority = Priority.HIGH

    task = HumanTask(
        human_task_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        assignee_id=task_config.get("assignee_id", "unassigned"),
        title=task_config.get("title", "Action Required"),
        description=task_config.get("description", "Please review and take action"),
        context_snapshot=task_config,
        status=HumanTaskStatus.PENDING,
        priority=priority,
        due_at=datetime.utcnow() + timedelta(hours=task_config.get("due_hours", 4)),
    )
    await task.insert()
    return task.human_task_id


@activity.defn(name="notify_assignee")
async def notify_assignee(human_task_id: str, tenant_id: str, tier: int, task_config: dict) -> bool:
    """Notify task assignee via email and Slack."""
    from agents.action_execution.agent import ActionExecutionAgent
    from db.models import HumanTask, User

    activity.heartbeat(f"Notifying assignee (tier {tier})")

    task = await HumanTask.find_one(HumanTask.human_task_id == human_task_id)
    if not task:
        return False

    aea = ActionExecutionAgent(tenant_id=tenant_id)

    tier_labels = ["you", "your manager", "director", "executive team"]
    urgency = "🔴 CRITICAL" if tier >= 2 else "⚠️ URGENT" if tier == 1 else "📋 Action Required"

    try:
        user = await User.find_one(User.uid == task.assignee_id)
        if user and user.email:
            await aea.send_email(
                to=[str(user.email)],
                cc=[],
                bcc=[],
                subject=f"{urgency}: {task.title}",
                body_html=f"""
                <h2>{urgency}</h2>
                <p><strong>{task.title}</strong></p>
                <p>{task.description}</p>
                <p>Task ID: <code>{human_task_id}</code></p>
                <p>Please complete this task in the AntiGravity platform.</p>
                <a href="http://localhost:3000/tasks/{human_task_id}"
                   style="background: #7c3aed; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none;">
                  View Task
                </a>
                """,
                workflow_id=task.workflow_id,
                idempotency_key=f"notify-{human_task_id}-tier{tier}",
            )
    except Exception as e:
        logger.warning(f"Email notification failed: {e}")

    return True


@activity.defn(name="check_task_completed")
async def check_task_completed(human_task_id: str, tenant_id: str) -> bool:
    """Check if a HumanTask has been completed via the API."""
    from db.models import HumanTask, HumanTaskStatus

    task = await HumanTask.find_one(HumanTask.human_task_id == human_task_id)
    if not task:
        return False
    return task.status == HumanTaskStatus.COMPLETED


@activity.defn(name="escalate_to_next_tier")
async def escalate_to_next_tier(
    human_task_id: str, tenant_id: str, workflow_id: str, next_tier: int, task_config: dict
) -> bool:
    """Re-assign task to next escalation tier and update escalation record."""
    from db.models import HumanTask, User, UserRole, Escalation, EscalationStatus
    from datetime import timedelta

    activity.heartbeat(f"Escalating to tier {next_tier}")

    # Find a user with the required role for this tier
    target_role = ESCALATION_ROLE_MAP.get(next_tier, "TENANT_ADMIN")
    try:
        target_role_enum = UserRole(target_role)
        manager = await User.find_one(
            User.tenant_id == tenant_id,
            User.role == target_role_enum,
            User.is_active == True,
        )
    except Exception:
        manager = None

    if manager:
        await HumanTask.find_one(HumanTask.human_task_id == human_task_id).update({
            "$set": {
                "assignee_id": manager.uid,
                "priority": "CRITICAL",
                "updated_at": datetime.utcnow(),
            }
        })

    # Update escalation level
    await Escalation.find_one(Escalation.workflow_id == workflow_id).update({
        "$set": {
            "escalation_level": next_tier + 1,
            "status": EscalationStatus.ESCALATED.value,
            "updated_at": datetime.utcnow(),
        }
    })

    # Notify new assignee
    await notify_assignee(human_task_id, tenant_id, next_tier, task_config)

    return True


@activity.defn(name="auto_resolve")
async def auto_resolve(human_task_id: str, tenant_id: str, task_config: dict) -> dict:
    """Auto-resolve task with conservative default when all tiers exhausted."""
    from db.models import HumanTask, HumanTaskStatus

    activity.heartbeat("Auto-resolving task")

    await HumanTask.find_one(HumanTask.human_task_id == human_task_id).update({
        "$set": {
            "status": HumanTaskStatus.COMPLETED.value,
            "outcome": "AUTO_RESOLVED",
            "completion_notes": "Automatically resolved after all escalation tiers exhausted. Conservative action taken.",
            "completed_at": datetime.utcnow(),
        }
    })

    return {
        "outcome": "AUTO_RESOLVED",
        "notes": "Conservative automatic resolution applied",
        "human_task_id": human_task_id,
    }


@activity.defn(name="mark_escalation_resolved")
async def mark_escalation_resolved(escalation_id: str, tenant_id: str, resolution: dict) -> bool:
    """Mark the parent escalation as resolved."""
    from db.models import Escalation, EscalationStatus

    if not escalation_id:
        return True

    await Escalation.find_one(Escalation.escalation_id == escalation_id).update({
        "$set": {
            "status": EscalationStatus.RESOLVED.value,
            "resolved_at": datetime.utcnow(),
            "resolution_notes": resolution.get("notes", "Resolved"),
        }
    })
    return True
