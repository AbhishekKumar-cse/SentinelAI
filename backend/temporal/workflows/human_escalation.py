"""
HumanEscalationWorkflow — Temporal workflow.
Creates a HumanTask, waits for completion with tiered escalation.
Tier 1 → assigned user (N hrs), Tier 2 → manager, Tier 3 → director, Tier 4 → CISO.
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities.escalation_activities import (
        create_human_task,
        notify_assignee,
        check_task_completed,
        escalate_to_next_tier,
        auto_resolve,
        mark_escalation_resolved,
    )

ESCALATION_TIERS = [
    {"label": "Assignee", "timeout_hours": 4},
    {"label": "Manager", "timeout_hours": 8},
    {"label": "Director", "timeout_hours": 24},
    {"label": "Executive", "timeout_hours": 48},
]


@workflow.defn(name="HumanEscalationWorkflow")
class HumanEscalationWorkflow:
    """
    Manages a human task through multi-tier escalation.
    Escalates up the chain if not resolved within timeout.
    Auto-resolves with conservative default if all tiers exhausted.
    """

    def __init__(self):
        self._resolved = False
        self._resolution: dict | None = None
        self._current_tier = 0

    @workflow.run
    async def run(self, input: dict) -> dict:
        workflow_id: str = input["workflow_id"]
        tenant_id: str = input["tenant_id"]
        task_config: dict = input["task_config"]
        escalation_id: str = input.get("escalation_id", "")

        retry = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))

        # Create the HumanTask document
        human_task_id = await workflow.execute_activity(
            create_human_task,
            args=[workflow_id, tenant_id, task_config],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry,
        )

        # Notify initial assignee
        await workflow.execute_activity(
            notify_assignee,
            args=[human_task_id, tenant_id, 0, task_config],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry,
        )

        # Run escalation ladder
        for tier_idx, tier in enumerate(ESCALATION_TIERS):
            self._current_tier = tier_idx
            timeout = timedelta(hours=tier["timeout_hours"])

            try:
                await workflow.wait_condition(
                    lambda: self._resolved,
                    timeout=timeout,
                )
                break  # Resolved!
            except workflow.TimeoutError:
                # Check in case task was completed via direct API
                is_done = await workflow.execute_activity(
                    check_task_completed,
                    args=[human_task_id, tenant_id],
                    start_to_close_timeout=timedelta(minutes=1),
                )
                if is_done:
                    self._resolved = True
                    break

                # Escalate to next tier
                if tier_idx < len(ESCALATION_TIERS) - 1:
                    await workflow.execute_activity(
                        escalate_to_next_tier,
                        args=[human_task_id, tenant_id, workflow_id, tier_idx + 1, task_config],
                        start_to_close_timeout=timedelta(minutes=2),
                        retry_policy=retry,
                    )

        # If still not resolved after all tiers, auto-resolve conservatively
        if not self._resolved:
            resolution = await workflow.execute_activity(
                auto_resolve,
                args=[human_task_id, tenant_id, task_config],
                start_to_close_timeout=timedelta(minutes=2),
            )
            self._resolution = resolution

        # Mark escalation as resolved
        await workflow.execute_activity(
            mark_escalation_resolved,
            args=[escalation_id, tenant_id, self._resolution or {}],
            start_to_close_timeout=timedelta(minutes=2),
        )

        return {
            "human_task_id": human_task_id,
            "resolved": self._resolved,
            "final_tier": self._current_tier,
            "resolution": self._resolution,
        }

    @workflow.signal
    def task_completed(self, resolution: dict) -> None:
        """Signal from API when human completes the task."""
        self._resolved = True
        self._resolution = resolution

    @workflow.query
    def get_current_tier(self) -> int:
        return self._current_tier

    @workflow.query
    def is_resolved(self) -> bool:
        return self._resolved
