"""
Temporal Worker — registers all workflows and activities,
then polls the task queue indefinitely.
Run: python -m temporal.worker
"""
import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

# Workflows
from temporal.workflows.meeting_intelligence import (
    MeetingIntelligenceWorkflow,
    ActionItemReminderWorkflow,
)
from temporal.workflows.procurement import (
    ProcurementWorkflow,
    SLAMonitorWorkflow,
)
from temporal.workflows.human_escalation import HumanEscalationWorkflow

# Activities
from temporal.activities.meeting_activities import (
    fetch_transcript,
    run_mia_analysis,
    create_action_item_tasks,
    send_meeting_summary,
    schedule_action_reminders,
    escalate_overdue_action,
    mark_meeting_complete,
)
from temporal.activities.procurement_activities import (
    validate_purchase_requisition,
    check_budget_availability,
    select_vendor,
    request_human_approval,
    create_purchase_order,
    three_way_match,
    execute_payment,
    rollback_payment,
    notify_stakeholders,
    compute_workflow_health,
)
from temporal.activities.escalation_activities import (
    create_human_task,
    notify_assignee,
    check_task_completed,
    escalate_to_next_tier,
    auto_resolve,
    mark_escalation_resolved,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

TASK_QUEUE = "antigravity-workers"
TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


async def run_worker():
    """Start Temporal worker with all registered workflows and activities."""
    logger.info(f"Connecting to Temporal at {TEMPORAL_HOST} namespace={TEMPORAL_NAMESPACE}")

    # Initialize MongoDB for activities
    os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0")
    from db.mongodb import init_mongodb
    await init_mongodb()

    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)

    # All activities across all workflow types
    all_activities = [
        # Meeting
        fetch_transcript,
        run_mia_analysis,
        create_action_item_tasks,
        send_meeting_summary,
        schedule_action_reminders,
        escalate_overdue_action,
        mark_meeting_complete,
        # Procurement
        validate_purchase_requisition,
        check_budget_availability,
        select_vendor,
        request_human_approval,
        create_purchase_order,
        three_way_match,
        execute_payment,
        rollback_payment,
        notify_stakeholders,
        compute_workflow_health,
        # Escalation
        create_human_task,
        notify_assignee,
        check_task_completed,
        escalate_to_next_tier,
        auto_resolve,
        mark_escalation_resolved,
    ]

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            MeetingIntelligenceWorkflow,
            ActionItemReminderWorkflow,
            ProcurementWorkflow,
            SLAMonitorWorkflow,
            HumanEscalationWorkflow,
        ],
        activities=all_activities,
        max_concurrent_activities=20,
        max_concurrent_workflow_tasks=10,
    )

    logger.info(f"Starting Temporal worker on queue: {TASK_QUEUE}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
