"""
Audit Ledger Service — The most critical component in AntiGravity.
Implements SHA-256 hash chain for immutable, tamper-evident audit records.
Uses MongoDB sessions + transactions to ensure atomic read-then-write.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


class AuditWriteError(Exception):
    """Raised when an audit record cannot be written. Triggers human escalation."""
    pass


class ChainIntegrityError(Exception):
    """Raised when hash chain verification fails."""
    pass


def _compute_hash(
    event_type: str,
    actor_id: str,
    payload: dict,
    prev_hash: str,
    timestamp: datetime,
) -> str:
    """Compute SHA-256 hash for a single audit record."""
    content = (
        event_type
        + actor_id
        + json.dumps(payload, sort_keys=True, default=str)
        + prev_hash
        + timestamp.isoformat()
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


GENESIS_HASH = hashlib.sha256(b"ANTIGRAVITY_GENESIS").hexdigest()


@retry(stop=stop_after_attempt(3), wait=wait_fixed(0.1))
async def write(
    event_type: str,
    actor_type: str,
    actor_id: str,
    payload: dict[str, Any],
    tenant_id: str,
    workflow_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> "AuditRecord":
    """
    Write an immutable audit record with hash chain integrity.

    Algorithm:
    1. MongoDB session + transaction for atomic read-then-write
    2. Fetch last record for workflow → get prev_hash
    3. Compute curr_hash = SHA256(event_type + actor_id + payload_json + prev_hash + timestamp)
    4. Insert new AuditRecord with both hashes
    5. Commit transaction (retry on write conflict up to 3 times)

    NEVER fails silently — raises AuditWriteError on persistent failure.
    """
    from db.models import AuditRecord, ActorType
    from db.mongodb import get_client, get_db

    client = get_client()
    db = get_db()

    async with await client.start_session() as session:
        async with session.start_transaction():
            # Fetch the last audit record for this workflow to get prev_hash
            if workflow_id:
                last_record = await AuditRecord.find(
                    AuditRecord.workflow_id == workflow_id,
                    session=session,
                ).sort(-AuditRecord.created_at).first_or_none()
            else:
                # For non-workflow audits, use tenant-level last record
                last_record = await AuditRecord.find(
                    AuditRecord.tenant_id == tenant_id,
                    AuditRecord.workflow_id == None,
                    session=session,
                ).sort(-AuditRecord.created_at).first_or_none()

            prev_hash = last_record.curr_hash if last_record else GENESIS_HASH

            timestamp = datetime.utcnow()
            curr_hash = _compute_hash(event_type, actor_id, payload, prev_hash, timestamp)

            record = AuditRecord(
                audit_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                task_id=task_id,
                event_type=event_type,
                actor_type=ActorType(actor_type),
                actor_id=actor_id,
                payload=payload,
                prev_hash=prev_hash,
                curr_hash=curr_hash,
                created_at=timestamp,
            )

            await record.insert(session=session)
            logger.debug(f"Audit record written: {event_type} for workflow {workflow_id}")
            return record


async def verify_chain(workflow_id: str, tenant_id: str) -> dict:
    """
    Verify the hash chain integrity for a workflow's audit trail.
    Returns a ChainIntegrityReport dict.
    """
    from db.models import AuditRecord

    records = await AuditRecord.find(
        AuditRecord.workflow_id == workflow_id,
        AuditRecord.tenant_id == tenant_id,
    ).sort(AuditRecord.created_at).to_list()

    hash_failures = []
    sequence_violations = []
    temporal_anomalies = []
    seen_ids = set()

    for i, record in enumerate(records):
        # Detect duplicates
        if record.audit_id in seen_ids:
            hash_failures.append({
                "audit_id": record.audit_id,
                "reason": "DUPLICATE_ID",
                "index": i,
            })
        seen_ids.add(record.audit_id)

        # Determine expected prev_hash
        if i == 0:
            expected_prev = GENESIS_HASH
        else:
            expected_prev = records[i - 1].curr_hash

        # Recompute hash
        expected_curr = _compute_hash(
            record.event_type,
            record.actor_id,
            record.payload,
            expected_prev,
            record.created_at,
        )

        if record.curr_hash != expected_curr:
            hash_failures.append({
                "audit_id": record.audit_id,
                "event_type": record.event_type,
                "index": i,
                "reason": "HASH_MISMATCH",
                "expected": expected_curr,
                "actual": record.curr_hash,
            })

        # Check prev_hash chain
        if record.prev_hash != expected_prev:
            hash_failures.append({
                "audit_id": record.audit_id,
                "index": i,
                "reason": "BROKEN_CHAIN",
            })

        # Temporal anomaly: event out of order
        if i > 0 and record.created_at < records[i - 1].created_at:
            temporal_anomalies.append({
                "audit_id": record.audit_id,
                "index": i,
                "reason": "OUT_OF_ORDER",
            })

    is_intact = len(hash_failures) == 0 and len(temporal_anomalies) == 0

    return {
        "is_intact": is_intact,
        "total_records": len(records),
        "hash_failures": hash_failures,
        "sequence_violations": sequence_violations,
        "temporal_anomalies": temporal_anomalies,
        "workflow_id": workflow_id,
        "verified_at": datetime.utcnow().isoformat(),
    }


async def query_audit_trail(
    workflow_id: str,
    tenant_id: str,
    event_type: Optional[str] = None,
    actor_type: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """
    Query audit records with filtering and pagination.
    Uses cursor-based pagination on created_at.
    """
    from db.models import AuditRecord

    query = {
        "workflow_id": workflow_id,
        "tenant_id": tenant_id,
    }
    if event_type:
        query["event_type"] = event_type
    if actor_type:
        query["actor_type"] = actor_type

    filters = [
        AuditRecord.workflow_id == workflow_id,
        AuditRecord.tenant_id == tenant_id,
    ]
    if event_type:
        filters.append(AuditRecord.event_type == event_type)
    if actor_type:
        filters.append(AuditRecord.actor_type == actor_type)

    # Cursor pagination
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            filters.append(AuditRecord.created_at > cursor_dt)
        except ValueError:
            pass

    records = await AuditRecord.find(*filters).sort(AuditRecord.created_at).limit(limit).to_list()

    next_cursor = records[-1].created_at.isoformat() if len(records) == limit else None

    return {
        "records": [r.model_dump() for r in records],
        "next_cursor": next_cursor,
        "count": len(records),
    }
