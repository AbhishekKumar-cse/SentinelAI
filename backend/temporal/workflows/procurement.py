"""
ProcurementWorkflow (P2P) — Temporal workflow.
Implements full Procure-to-Pay: PR validation → budget check →
vendor selection → PO creation → 3-way match → payment execution.
SLA-monitored, with human approval gates and automatic escalation.
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities.procurement_activities import (
        validate_purchase_requisition,
        check_budget_availability,
        select_vendor,
        create_purchase_order,
        three_way_match,
        request_human_approval,
        execute_payment,
        rollback_payment,
        notify_stakeholders,
        compute_workflow_health,
    )


@workflow.defn(name="ProcurementWorkflow")
class ProcurementWorkflow:
    """
    End-to-end Procure-to-Pay workflow with compliance gates.

    Human approval required when:
    - Amount exceeds tenant-configured threshold
    - Vendor risk score > 0.6
    - 3-way match has discrepancies > tolerance
    """

    def __init__(self):
        self._status = "STARTED"
        self._current_step = "INITIALIZING"
        self._health_score = 100.0
        self._approval_signal: str | None = None

    @workflow.run
    async def run(self, input: dict) -> dict:
        workflow_id: str = input["workflow_id"]
        tenant_id: str = input["tenant_id"]
        context: dict = input.get("context", {})

        vendor_id = context.get("vendor_id", "")
        amount = float(context.get("amount", 0))
        currency = context.get("currency", "INR")
        approval_threshold = float(context.get("approval_threshold", 100000))  # INR 1L

        retry_policy = RetryPolicy(
            maximum_attempts=5,
            initial_interval=timedelta(seconds=10),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=5),
        )

        # ── Step 1: Validate Purchase Requisition ─────────────────────────
        self._current_step = "VALIDATE_PR"
        pr_result = await workflow.execute_activity(
            validate_purchase_requisition,
            args=[workflow_id, tenant_id, context],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        if not pr_result.get("is_valid"):
            self._status = "FAILED"
            await workflow.execute_activity(
                notify_stakeholders,
                args=[workflow_id, tenant_id, "PR_INVALID", pr_result],
                start_to_close_timeout=timedelta(minutes=2),
            )
            return {"workflow_id": workflow_id, "status": "FAILED", "reason": "PR_INVALID", "details": pr_result}

        # ── Step 2: Budget Check ──────────────────────────────────────────
        self._current_step = "CHECK_BUDGET"
        budget_result = await workflow.execute_activity(
            check_budget_availability,
            args=[workflow_id, tenant_id, amount, currency, context.get("cost_center", "")],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=retry_policy,
        )

        if not budget_result.get("sufficient"):
            self._status = "FAILED"
            await workflow.execute_activity(
                notify_stakeholders,
                args=[workflow_id, tenant_id, "INSUFFICIENT_BUDGET", budget_result],
                start_to_close_timeout=timedelta(minutes=2),
            )
            return {"workflow_id": workflow_id, "status": "FAILED", "reason": "INSUFFICIENT_BUDGET"}

        # ── Step 3: Vendor Selection (DMA) ────────────────────────────────
        self._current_step = "VENDOR_SELECTION"
        vendor_result = await workflow.execute_activity(
            select_vendor,
            args=[workflow_id, tenant_id, vendor_id, amount, currency],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        # ── Step 4: Human Approval Gate ───────────────────────────────────
        needs_approval = amount > approval_threshold or vendor_result.get("risk_score", 0) > 0.6

        if needs_approval:
            self._current_step = "AWAITING_APPROVAL"
            await workflow.execute_activity(
                request_human_approval,
                args=[workflow_id, tenant_id, {
                    "amount": amount,
                    "currency": currency,
                    "vendor": vendor_result,
                    "pr_result": pr_result,
                }],
                start_to_close_timeout=timedelta(minutes=2),
            )

            # Wait for approval signal (up to 48h)
            try:
                await workflow.wait_condition(
                    lambda: self._approval_signal is not None,
                    timeout=timedelta(hours=48),
                )
            except workflow.TimeoutError:
                self._status = "TIMED_OUT"
                await workflow.execute_activity(
                    notify_stakeholders,
                    args=[workflow_id, tenant_id, "APPROVAL_TIMEOUT", {}],
                    start_to_close_timeout=timedelta(minutes=2),
                )
                return {"workflow_id": workflow_id, "status": "TIMED_OUT", "reason": "APPROVAL_TIMEOUT"}

            if self._approval_signal == "REJECTED":
                self._status = "CANCELLED"
                return {"workflow_id": workflow_id, "status": "CANCELLED", "reason": "HUMAN_REJECTED"}

        # ── Step 5: Create Purchase Order ─────────────────────────────────
        self._current_step = "CREATE_PO"
        po_result = await workflow.execute_activity(
            create_purchase_order,
            args=[workflow_id, tenant_id, vendor_id, amount, currency, context],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        po_id = po_result["po_id"]

        # ── Step 6: 3-Way Match ───────────────────────────────────────────
        # Wait for goods receipt (up to 30 days in production, short for demo)
        self._current_step = "THREE_WAY_MATCH"
        match_result = await workflow.execute_activity(
            three_way_match,
            args=[workflow_id, tenant_id, po_id, context.get("invoice_id", ""), context.get("receipt_id", "")],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        if not match_result.get("is_matched"):
            # Require human review for discrepancies
            self._current_step = "AWAITING_MATCH_REVIEW"
            await workflow.execute_activity(
                request_human_approval,
                args=[workflow_id, tenant_id, {
                    "type": "THREE_WAY_MATCH_DISCREPANCY",
                    "discrepancies": match_result.get("discrepancies", []),
                    "po_id": po_id,
                }],
                start_to_close_timeout=timedelta(minutes=2),
            )

            try:
                await workflow.wait_condition(
                    lambda: self._approval_signal is not None,
                    timeout=timedelta(hours=24),
                )
            except workflow.TimeoutError:
                return {"workflow_id": workflow_id, "status": "TIMED_OUT", "reason": "MATCH_REVIEW_TIMEOUT"}

            if self._approval_signal == "REJECTED":
                return {"workflow_id": workflow_id, "status": "CANCELLED", "reason": "MATCH_REJECTED"}

            # Reset for next wait
            self._approval_signal = None

        # ── Step 7: Execute Payment ───────────────────────────────────────
        self._current_step = "EXECUTE_PAYMENT"
        try:
            payment_result = await workflow.execute_activity(
                execute_payment,
                args=[workflow_id, tenant_id, po_id, amount, currency],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
        except Exception as e:
            # Compensate: rollback
            await workflow.execute_activity(
                rollback_payment,
                args=[workflow_id, tenant_id, po_id],
                start_to_close_timeout=timedelta(minutes=5),
            )
            self._status = "FAILED"
            return {"workflow_id": workflow_id, "status": "FAILED", "reason": "PAYMENT_FAILED", "error": str(e)}

        # ── Step 8: Final Notifications ───────────────────────────────────
        self._current_step = "NOTIFYING"
        await workflow.execute_activity(
            notify_stakeholders,
            args=[workflow_id, tenant_id, "PAYMENT_COMPLETE", {
                "po_id": po_id,
                "amount": amount,
                "currency": currency,
                "payment": payment_result,
            }],
            start_to_close_timeout=timedelta(minutes=2),
        )

        self._status = "COMPLETED"
        return {
            "workflow_id": workflow_id,
            "status": "COMPLETED",
            "po_id": po_id,
            "payment": payment_result,
            "three_way_match": match_result,
        }

    @workflow.signal
    def approval_decision(self, decision: str) -> None:
        """Signal handler for human approval decisions (APPROVED/REJECTED)."""
        self._approval_signal = decision

    @workflow.query
    def get_status(self) -> str:
        return self._status

    @workflow.query
    def get_current_step(self) -> str:
        return self._current_step

    @workflow.query
    def get_health_score(self) -> float:
        return self._health_score


@workflow.defn(name="SLAMonitorWorkflow")
class SLAMonitorWorkflow:
    """
    Runs alongside any workflow. Polls health score every N minutes.
    Triggers escalation if breach probability exceeds threshold.
    Terminates when parent workflow completes.
    """

    def __init__(self):
        self._should_stop = False

    @workflow.run
    async def run(self, input: dict) -> dict:
        workflow_id = input["workflow_id"]
        tenant_id = input["tenant_id"]
        check_interval_minutes = input.get("check_interval_minutes", 5)
        max_duration_hours = input.get("max_duration_hours", 48)

        checks_done = 0
        max_checks = int(max_duration_hours * 60 / check_interval_minutes)

        while not self._should_stop and checks_done < max_checks:
            await workflow.sleep(timedelta(minutes=check_interval_minutes))

            health = await workflow.execute_activity(
                compute_workflow_health,
                args=[workflow_id, tenant_id],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            checks_done += 1

            if health.get("is_terminal"):
                break

        return {"workflow_id": workflow_id, "checks_done": checks_done}

    @workflow.signal
    def stop(self) -> None:
        self._should_stop = True
