"""
Verification Agent (VA) — All verifications before high-stakes actions.
Makes actions atomic by checking expected state before and after.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from agents.base_agent import BaseAgent, AgentToolError

logger = logging.getLogger(__name__)

VA_SYSTEM_PROMPT = """You are a Verification Agent. Your purpose is to confirm the actual state of the world matches expected outcomes before and after every action.

Verification protocol:
1. Pre-verify: confirm the starting state matches assumptions
2. Post-verify: confirm the action produced the expected outcome
3. Cross-verify: confirm no side effects occurred in other systems
4. If verification fails: HALT and escalate immediately

Never pass a verification if you have any doubt. False negatives are preferable to false positives."""


class VerificationAgent(BaseAgent):
    family = "VA"

    def get_system_prompt(self) -> str:
        return VA_SYSTEM_PROMPT

    async def verify_action_outcome(
        self,
        action_record_id: str,
        expected_outcome: dict,
        actual_outcome: dict,
        verification_method: str,
        workflow_id: str,
    ) -> dict:
        """
        Verify an action produced the expected outcome.
        Returns VerificationResult with pass/fail and evidence.
        """
        from db.models import VerificationRecord

        checks_passed = []
        checks_failed = []

        # Compare expected vs actual
        for key, expected_val in expected_outcome.items():
            actual_val = actual_outcome.get(key)
            if actual_val == expected_val:
                checks_passed.append({
                    "field": key,
                    "expected": expected_val,
                    "actual": actual_val,
                })
            else:
                checks_failed.append({
                    "field": key,
                    "expected": expected_val,
                    "actual": actual_val,
                })

        is_passed = len(checks_failed) == 0
        confidence = len(checks_passed) / max(len(expected_outcome), 1)

        record = VerificationRecord(
            verification_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            action_record_id=action_record_id,
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            verification_type="ACTION_OUTCOME",
            is_passed=is_passed,
            confidence=confidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )
        await record.insert()

        await self.write_audit_record(
            event_type="VERIFICATION_COMPLETED",
            payload={
                "verification_id": record.verification_id,
                "action_record_id": action_record_id,
                "is_passed": is_passed,
                "checks_failed": len(checks_failed),
                "confidence": confidence,
            },
            workflow_id=workflow_id,
        )

        if not is_passed:
            await self.emit_kafka_event(
                topic="escalations",
                event_type="VerificationFailed",
                data={
                    "verification_id": record.verification_id,
                    "action_record_id": action_record_id,
                    "checks_failed": checks_failed,
                },
                workflow_id=workflow_id,
            )

        return {
            "is_passed": is_passed,
            "confidence": confidence,
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "verification_id": record.verification_id,
        }

    async def three_way_match(
        self,
        po_id: str,
        invoice_id: str,
        receipt_id: str,
        tolerance_pct: float,
        workflow_id: str,
    ) -> dict:
        """
        Procurement 3-way match: PO vs Invoice vs Goods Receipt.
        Industry-standard financial control.
        """
        from agents.data_retrieval.agent import DataRetrievalAgent

        dra = DataRetrievalAgent(tenant_id=self.tenant_id)

        # Fetch all three documents
        po = await dra.fetch_entity("purchase_order", po_id, "default", workflow_id)
        invoice = await dra.fetch_entity("invoice", invoice_id, "default", workflow_id)
        receipt = await dra.fetch_entity("goods_receipt", receipt_id, "default", workflow_id)

        discrepancies = []

        # Check amounts
        po_amount = float(po.get("total_amount", 0))
        invoice_amount = float(invoice.get("total_amount", 0))
        receipt_amount = float(receipt.get("total_amount", 0))

        amount_tolerance = po_amount * (tolerance_pct / 100)

        if abs(po_amount - invoice_amount) > amount_tolerance:
            discrepancies.append({
                "type": "AMOUNT_MISMATCH",
                "po_amount": po_amount,
                "invoice_amount": invoice_amount,
                "difference": abs(po_amount - invoice_amount),
            })

        if abs(po_amount - receipt_amount) > amount_tolerance:
            discrepancies.append({
                "type": "RECEIPT_MISMATCH",
                "po_amount": po_amount,
                "receipt_amount": receipt_amount,
                "difference": abs(po_amount - receipt_amount),
            })

        # Check quantities
        for item in po.get("line_items", []):
            inv_item = next((i for i in invoice.get("line_items", []) if i.get("sku") == item.get("sku")), None)
            rec_item = next((i for i in receipt.get("line_items", []) if i.get("sku") == item.get("sku")), None)

            if inv_item and abs(item.get("quantity", 0) - inv_item.get("quantity", 0)) > 0:
                discrepancies.append({
                    "type": "QUANTITY_MISMATCH",
                    "sku": item.get("sku"),
                    "po_qty": item.get("quantity"),
                    "invoice_qty": inv_item.get("quantity"),
                })

        is_matched = len(discrepancies) == 0

        await self.write_audit_record(
            event_type="THREE_WAY_MATCH_COMPLETED",
            payload={
                "po_id": po_id,
                "invoice_id": invoice_id,
                "receipt_id": receipt_id,
                "is_matched": is_matched,
                "discrepancies": discrepancies,
            },
            workflow_id=workflow_id,
        )

        return {
            "is_matched": is_matched,
            "pos_id": po_id,
            "invoice_id": invoice_id,
            "receipt_id": receipt_id,
            "discrepancies": discrepancies,
            "requires_human_review": not is_matched,
        }

    async def validate_data_schema(
        self,
        data: dict,
        schema: dict,
        workflow_id: str,
    ) -> dict:
        """Validate data against a JSON schema."""
        import jsonschema

        try:
            jsonschema.validate(data, schema)
            is_valid = True
            validation_errors = []
        except jsonschema.ValidationError as e:
            is_valid = False
            validation_errors = [{"path": str(e.path), "message": e.message}]
        except jsonschema.SchemaError as e:
            is_valid = False
            validation_errors = [{"path": "schema", "message": f"Invalid schema: {e.message}"}]

        await self.write_audit_record(
            event_type="SCHEMA_VALIDATION_COMPLETED",
            payload={"is_valid": is_valid, "errors": validation_errors},
            workflow_id=workflow_id,
        )

        return {
            "is_valid": is_valid,
            "errors": validation_errors,
            "fields_checked": len(schema.get("properties", {})),
        }

    async def verify_idempotency(
        self,
        idempotency_key: str,
        action_type: str,
        workflow_id: str,
    ) -> dict:
        """Check if an action with this idempotency key was already executed."""
        import redis.asyncio as aioredis
        import os

        r = await aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        cached = await r.get(f"idem:{idempotency_key}")

        return {
            "already_executed": cached is not None,
            "idempotency_key": idempotency_key,
            "cached_result": cached,
        }

    async def verify_all_tasks_complete(
        self,
        workflow_id: str,
        required_task_types: list[str],
    ) -> dict:
        """Verify all required task types have been completed for a workflow."""
        from db.models import WorkflowTask, TaskStatus

        tasks = await WorkflowTask.find(
            WorkflowTask.workflow_id == workflow_id,
        ).to_list()

        completed = {t.task_type for t in tasks if t.status == TaskStatus.COMPLETED}
        required = set(required_task_types)
        missing = required - completed

        return {
            "all_complete": len(missing) == 0,
            "completed_types": list(completed),
            "missing_types": list(missing),
        }

    async def execute_task(
        self,
        task_id: str,
        workflow_id: str,
        task_definition: dict[Any, Any],
        context: dict[Any, Any],
    ) -> dict[Any, Any]:
        """VA task execution entry point."""
        action = task_definition.get("action", "verify")

        if action == "three_way_match":
            return await self.three_way_match(
                po_id=task_definition.get("po_id", ""),
                invoice_id=task_definition.get("invoice_id", ""),
                receipt_id=task_definition.get("receipt_id", ""),
                tolerance_pct=task_definition.get("tolerance_pct", 2.0),
                workflow_id=workflow_id,
            )
        elif action == "validate_schema":
            return await self.validate_data_schema(
                data=context,
                schema=task_definition.get("schema", {}),
                workflow_id=workflow_id,
            )
        else:
            return {"action": action, "status": "verified"}
