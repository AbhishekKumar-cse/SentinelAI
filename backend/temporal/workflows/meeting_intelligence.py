"""
MeetingIntelligenceWorkflow — Temporal workflow.
Triggered on meeting ingestion. Runs MIA transcript analysis,
creates action items, schedules reminder timers, and spawns
child workflows for critical action items.
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities.meeting_activities import (
        fetch_transcript,
        run_mia_analysis,
        create_action_item_tasks,
        send_meeting_summary,
        schedule_action_reminders,
        mark_meeting_complete,
        escalate_overdue_action,
    )


@workflow.defn(name="MeetingIntelligenceWorkflow")
class MeetingIntelligenceWorkflow:
    """
    End-to-end meeting intelligence pipeline.

    Flow:
    1. Fetch transcript from storage (Zoom/Teams/Google Meet webhook)
    2. Run MIA analysis (claude-sonnet-4-20250514) → decisions + action items
    3. Create HumanTask records for each action item
    4. Send meeting summary to all participants
    5. Schedule reminder timers for each action item
    6. Escalate overdue actions at due date
    """

    def __init__(self):
        self._status = "STARTED"
        self._analysis_complete = False

    @workflow.run
    async def run(self, input: dict) -> dict:
        meeting_id: str = input["meeting_id"]
        tenant_id: str = input["tenant_id"]
        participants: list = input.get("participants", [])
        source: str = input.get("source", "MANUAL")

        retry_policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=2),
        )

        # ── Step 1: Fetch transcript ──────────────────────────────────────
        self._status = "FETCHING_TRANSCRIPT"
        transcript = await workflow.execute_activity(
            fetch_transcript,
            args=[meeting_id, tenant_id, source],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        if not transcript:
            self._status = "TRANSCRIPT_UNAVAILABLE"
            return {"meeting_id": meeting_id, "status": "TRANSCRIPT_UNAVAILABLE"}

        # ── Step 2: Run MIA Analysis ──────────────────────────────────────
        self._status = "ANALYZING"
        analysis = await workflow.execute_activity(
            run_mia_analysis,
            args=[meeting_id, tenant_id, transcript, participants],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )
        self._analysis_complete = True

        # ── Step 3: Create HumanTask records ──────────────────────────────
        self._status = "CREATING_TASKS"
        task_ids = await workflow.execute_activity(
            create_action_item_tasks,
            args=[meeting_id, tenant_id, analysis.get("action_items", [])],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry_policy,
        )

        # ── Step 4: Send summary notification ────────────────────────────
        self._status = "SENDING_SUMMARY"
        await workflow.execute_activity(
            send_meeting_summary,
            args=[meeting_id, tenant_id, participants, analysis],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        # ── Step 5: Schedule reminder timers ─────────────────────────────
        self._status = "SCHEDULING_REMINDERS"
        action_items = analysis.get("action_items", [])

        reminder_handles = []
        for idx, item in enumerate(action_items):
            due_in_days = item.get("due_in_days", 7)
            if due_in_days > 0:
                # Day-before reminder
                reminder_delay = timedelta(days=max(due_in_days - 1, 0))
                handle = await workflow.start_child_workflow(
                    ActionItemReminderWorkflow,
                    args=[{
                        "meeting_id": meeting_id,
                        "tenant_id": tenant_id,
                        "action_item_index": idx,
                        "action_description": item.get("description", ""),
                        "assignee_name": item.get("assignee_name", ""),
                        "due_in_days": due_in_days,
                        "reminder_delay_seconds": int(reminder_delay.total_seconds()),
                    }],
                    id=f"reminder-{meeting_id}-{idx}",
                    task_queue="antigravity-workers",
                )
                reminder_handles.append(handle)

        # ── Step 6: Mark complete ─────────────────────────────────────────
        self._status = "COMPLETE"
        await workflow.execute_activity(
            mark_meeting_complete,
            args=[meeting_id, tenant_id],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "meeting_id": meeting_id,
            "status": "ANALYZED",
            "decisions_count": len(analysis.get("decisions", [])),
            "action_items_count": len(action_items),
            "tasks_created": len(task_ids),
            "reminders_scheduled": len(reminder_handles),
        }

    @workflow.query
    def get_status(self) -> str:
        return self._status

    @workflow.query
    def is_analysis_complete(self) -> bool:
        return self._analysis_complete


@workflow.defn(name="ActionItemReminderWorkflow")
class ActionItemReminderWorkflow:
    """
    Child workflow that waits until action item is due and sends a reminder.
    If action not completed by due date, escalates.
    """

    @workflow.run
    async def run(self, input: dict) -> dict:
        meeting_id = input["meeting_id"]
        tenant_id = input["tenant_id"]
        description = input["action_description"]
        due_in_days = input["due_in_days"]
        reminder_delay_seconds = input.get("reminder_delay_seconds", 0)

        # Wait until day before due date
        if reminder_delay_seconds > 0:
            await workflow.sleep(timedelta(seconds=reminder_delay_seconds))

        # Send reminder
        await workflow.execute_activity(
            schedule_action_reminders,
            args=[meeting_id, tenant_id, [input]],
            start_to_close_timeout=timedelta(minutes=2),
        )

        # Wait remaining time until due
        await workflow.sleep(timedelta(days=1))

        # Escalate if overdue
        await workflow.execute_activity(
            escalate_overdue_action,
            args=[meeting_id, tenant_id, input],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        return {"status": "REMINDER_SENT", "meeting_id": meeting_id}
