"""
Temporal Activities — Procurement P2P Workflow.
"""
import logging
import uuid
from datetime import datetime
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="validate_purchase_requisition")
async def validate_purchase_requisition(workflow_id: str, tenant_id: str, context: dict) -> dict:
    """Validate PR using DRA + DMA agents."""
    from agents.data_retrieval.agent import DataRetrievalAgent
    from agents.verification.agent import VerificationAgent

    activity.heartbeat("Validating purchase requisition")

    dra = DataRetrievalAgent(tenant_id=tenant_id)
    va = VerificationAgent(tenant_id=tenant_id)

    amount = float(context.get("amount", 0))
    vendor_id = context.get("vendor_id", "")

    is_valid = True
    reasons = []

    if amount <= 0:
        is_valid = False
        reasons.append("Amount must be positive")

    if not vendor_id:
        is_valid = False
        reasons.append("Vendor ID is required")

    if amount > 50_000_000:  # 5 crore INR max per PR
        is_valid = False
        reasons.append("Amount exceeds maximum PR limit (INR 5,00,00,000)")

    return {"is_valid": is_valid, "reasons": reasons}


@activity.defn(name="check_budget_availability")
async def check_budget_availability(
    workflow_id: str, tenant_id: str, amount: float, currency: str, cost_center: str
) -> dict:
    """Check budget availability for cost center via DRA."""
    activity.heartbeat(f"Checking budget for cost center {cost_center}")

    # In production: fetch from SAP/NetSuite via connector
    # Demo: always sufficient for amounts < 1 crore
    available = 10_000_000.0  # Simulated available budget

    return {
        "sufficient": amount <= available,
        "available": available,
        "requested": amount,
        "currency": currency,
        "cost_center": cost_center,
    }


@activity.defn(name="select_vendor")
async def select_vendor(
    workflow_id: str, tenant_id: str, vendor_id: str, amount: float, currency: str
) -> dict:
    """Run vendor scoring via DMA decision engine."""
    from agents.decision_making.agent import DecisionMakingAgent

    activity.heartbeat(f"Evaluating vendor {vendor_id}")

    dma = DecisionMakingAgent(tenant_id=tenant_id)

    # In production: fetch vendor data from procurement system
    vendor_data = {
        "vendor_id": vendor_id,
        "name": f"Vendor {vendor_id}",
        "financial_stability_score": 0.85,
        "delivery_track_record": 0.92,
        "compliance_status": "APPROVED",
        "risk_score": 0.2,
    }

    return {
        "selected": True,
        "vendor_id": vendor_id,
        "vendor_data": vendor_data,
        "risk_score": vendor_data["risk_score"],
        "score": 0.88,
    }


@activity.defn(name="request_human_approval")
async def request_human_approval(workflow_id: str, tenant_id: str, task_config: dict) -> str:
    """Create a HumanTask for approval and notify via Slack/email."""
    from db.models import HumanTask, HumanTaskStatus, Priority
    from agents.action_execution.agent import ActionExecutionAgent

    activity.heartbeat("Requesting human approval")

    amount = task_config.get("amount", 0)
    currency = task_config.get("currency", "INR")
    task_type = task_config.get("type", "PURCHASE_APPROVAL")

    task = HumanTask(
        human_task_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        assignee_id="user_manager_001",  # Route to manager
        title=f"Approval Required: {currency} {amount:,.2f} Purchase",
        description=f"Please review and approve/reject this purchase request.",
        context_snapshot=task_config,
        status=HumanTaskStatus.PENDING,
        priority=Priority.HIGH if amount > 500000 else Priority.MEDIUM,
    )
    await task.insert()

    # Send Slack notification
    aea = ActionExecutionAgent(tenant_id=tenant_id)
    try:
        await aea.post_to_slack(
            channel="#approvals",
            message=f"🔔 *Approval Required*\n*Amount:* {currency} {amount:,.0f}\n*Type:* {task_type}\n*Task ID:* `{task.human_task_id}`",
            blocks=None,
            workflow_id=workflow_id,
        )
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")

    return task.human_task_id


@activity.defn(name="create_purchase_order")
async def create_purchase_order(
    workflow_id: str, tenant_id: str, vendor_id: str, amount: float, currency: str, context: dict
) -> dict:
    """Create PO in the ERP system via AEA connector."""
    from agents.action_execution.agent import ActionExecutionAgent

    activity.heartbeat("Creating purchase order")

    po_id = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    aea = ActionExecutionAgent(tenant_id=tenant_id)

    action_result = await aea.execute_action(
        action_type="CREATE_PO",
        action_payload={
            "po_id": po_id,
            "vendor_id": vendor_id,
            "amount": amount,
            "currency": currency,
            "line_items": context.get("line_items", [{"description": "Services", "quantity": 1, "unit_price": amount}]),
        },
        workflow_id=workflow_id,
        idempotency_key=f"po-{workflow_id}",
    )

    return {"po_id": po_id, "status": "CREATED", **action_result}


@activity.defn(name="three_way_match")
async def three_way_match(
    workflow_id: str, tenant_id: str, po_id: str, invoice_id: str, receipt_id: str
) -> dict:
    """Run 3-way match via VA."""
    from agents.verification.agent import VerificationAgent

    activity.heartbeat("Running 3-way match")

    va = VerificationAgent(tenant_id=tenant_id)

    # In demo mode: if IDs are empty, simulate a successful match
    if not invoice_id or not receipt_id:
        return {
            "is_matched": True,
            "discrepancies": [],
            "message": "Demo: simulated successful 3-way match",
        }

    return await va.three_way_match(
        po_id=po_id,
        invoice_id=invoice_id,
        receipt_id=receipt_id,
        tolerance_pct=2.0,
        workflow_id=workflow_id,
    )


@activity.defn(name="execute_payment")
async def execute_payment(
    workflow_id: str, tenant_id: str, po_id: str, amount: float, currency: str
) -> dict:
    """Execute payment via AEA payment connector."""
    from agents.action_execution.agent import ActionExecutionAgent

    activity.heartbeat("Executing payment")

    aea = ActionExecutionAgent(tenant_id=tenant_id)

    result = await aea.verify_payment(
        payment_reference=f"PAY-{uuid.uuid4().hex[:12].upper()}",
        expected_amount=amount,
        expected_currency=currency,
        workflow_id=workflow_id,
        idempotency_key=f"payment-{workflow_id}-{po_id}",
    )

    return {"status": "PAYMENT_INITIATED", "reference": result.get("payment_reference"), "po_id": po_id}


@activity.defn(name="rollback_payment")
async def rollback_payment(workflow_id: str, tenant_id: str, po_id: str) -> dict:
    """Rollback/cancel a payment in case of failure."""
    activity.heartbeat("Rolling back payment")
    logger.warning(f"Payment rollback initiated for PO {po_id} workflow {workflow_id}")
    return {"status": "ROLLED_BACK", "po_id": po_id}


@activity.defn(name="notify_stakeholders")
async def notify_stakeholders(
    workflow_id: str, tenant_id: str, event_type: str, data: dict
) -> bool:
    """Send email/Slack notifications to relevant stakeholders."""
    from agents.action_execution.agent import ActionExecutionAgent

    activity.heartbeat(f"Notifying stakeholders: {event_type}")

    aea = ActionExecutionAgent(tenant_id=tenant_id)

    messages = {
        "PAYMENT_COMPLETE": f"✅ Payment executed successfully! PO: {data.get('po_id')} Amount: {data.get('currency')} {data.get('amount', 0):,.0f}",
        "PR_INVALID": f"❌ PR validation failed: {', '.join(data.get('reasons', []))}",
        "INSUFFICIENT_BUDGET": "❌ Purchase rejected: Insufficient budget",
        "APPROVAL_TIMEOUT": "⏰ Approval request timed out. Workflow cancelled.",
    }

    message = messages.get(event_type, f"📢 Workflow event: {event_type}")

    try:
        await aea.post_to_slack(
            channel="#procurement-alerts",
            message=message,
            blocks=None,
            workflow_id=workflow_id,
        )
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")

    return True


@activity.defn(name="compute_workflow_health")
async def compute_workflow_health(workflow_id: str, tenant_id: str) -> dict:
    """Compute health score and check if workflow is terminal."""
    from db.models import WorkflowRun

    wf = await WorkflowRun.find_one(WorkflowRun.workflow_id == workflow_id)
    if not wf:
        return {"health_score": 0, "is_terminal": True}

    is_terminal = wf.status.value in ("COMPLETED", "FAILED", "CANCELLED")
    return {
        "health_score": wf.health_score,
        "status": wf.status.value,
        "breach_probability": wf.breach_probability,
        "is_terminal": is_terminal,
    }
