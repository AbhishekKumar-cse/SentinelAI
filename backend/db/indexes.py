
"""
MongoDB index and Atlas Search index creation.
Called once at application startup after Beanie initialization.
"""
import logging
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT

logger = logging.getLogger(__name__)


async def create_all_indexes():
    """Create all compound, text, and unique indexes across all collections."""
    from db.models import (
        WorkflowRun, WorkflowTask, AuditRecord, DecisionRecord,
        HumanTask, AgentInstance, ActionRecord, User, Connector,
        ProcessTemplate, Meeting, ActionItem, AgentMemory,
    )

    logger.info("Creating MongoDB indexes...")

    # workflowRuns
    await WorkflowRun.get_motor_collection().create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING), ("started_at", DESCENDING)], name="tenant_status_started"),
        IndexModel([("tenant_id", ASCENDING), ("template_id", ASCENDING)], name="tenant_template"),
        IndexModel([("workflow_id", ASCENDING)], unique=True, name="workflow_id_unique"),
    ])

    # workflowTasks
    await WorkflowTask.get_motor_collection().create_indexes([
        IndexModel([("workflow_id", ASCENDING), ("status", ASCENDING)], name="workflow_status"),
        IndexModel([("assigned_agent_id", ASCENDING), ("status", ASCENDING)], name="agent_status"),
        IndexModel([("tenant_id", ASCENDING), ("due_at", ASCENDING)], name="tenant_due"),
        IndexModel([("task_id", ASCENDING)], unique=True, name="task_id_unique"),
    ])

    # auditRecords (immutable, hash-chain)
    await AuditRecord.get_motor_collection().create_indexes([
        IndexModel([("workflow_id", ASCENDING), ("created_at", ASCENDING)], name="workflow_timeline"),
        IndexModel([("tenant_id", ASCENDING), ("event_type", ASCENDING), ("created_at", DESCENDING)], name="tenant_event_time"),
        IndexModel([("curr_hash", ASCENDING)], unique=True, name="hash_unique"),
        IndexModel([("audit_id", ASCENDING)], unique=True, name="audit_id_unique"),
    ])

    # decisionRecords
    await DecisionRecord.get_motor_collection().create_indexes([
        IndexModel([("workflow_id", ASCENDING), ("created_at", DESCENDING)], name="workflow_time"),
        IndexModel([("agent_id", ASCENDING), ("created_at", DESCENDING)], name="agent_time"),
        IndexModel([("tenant_id", ASCENDING), ("decision_type", ASCENDING)], name="tenant_type"),
        IndexModel([("decision_id", ASCENDING)], unique=True, name="decision_id_unique"),
    ])

    # humanTasks
    await HumanTask.get_motor_collection().create_indexes([
        IndexModel([("assignee_id", ASCENDING), ("status", ASCENDING)], name="assignee_status"),
        IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING), ("priority", DESCENDING)], name="tenant_status_priority"),
        IndexModel([("due_at", ASCENDING)], name="due_at"),
        IndexModel([("human_task_id", ASCENDING)], unique=True, name="human_task_id_unique"),
    ])

    # agentInstances
    await AgentInstance.get_motor_collection().create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("family", ASCENDING), ("status", ASCENDING)], name="tenant_family_status"),
        IndexModel([("last_heartbeat_at", ASCENDING)], name="heartbeat"),
        IndexModel([("agent_id", ASCENDING)], unique=True, name="agent_id_unique"),
    ])

    # actionRecords
    await ActionRecord.get_motor_collection().create_indexes([
        IndexModel([("workflow_id", ASCENDING)], name="workflow"),
        IndexModel([("idempotency_key", ASCENDING)], unique=True, name="idempotency_unique"),
        IndexModel([("action_id", ASCENDING)], unique=True, name="action_id_unique"),
    ])

    # users
    await User.get_motor_collection().create_indexes([
        IndexModel([("uid", ASCENDING)], unique=True, name="uid_unique"),
        IndexModel([("tenant_id", ASCENDING), ("role", ASCENDING)], name="tenant_role"),
        IndexModel([("email", ASCENDING)], name="email"),
    ])

    # meetings
    await Meeting.get_motor_collection().create_indexes([
        IndexModel([("meeting_id", ASCENDING)], unique=True, name="meeting_id_unique"),
        IndexModel([("tenant_id", ASCENDING), ("meeting_at", DESCENDING)], name="tenant_time"),
    ])

    # actionItems
    await ActionItem.get_motor_collection().create_indexes([
        IndexModel([("meeting_id", ASCENDING), ("status", ASCENDING)], name="meeting_status"),
        IndexModel([("owner_id", ASCENDING), ("status", ASCENDING)], name="owner_status"),
        IndexModel([("action_item_id", ASCENDING)], unique=True, name="action_item_id_unique"),
    ])

    # agentMemory (text search + embedding lookup)
    await AgentMemory.get_motor_collection().create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("workflow_id", ASCENDING)], name="tenant_workflow"),
        IndexModel([("agent_id", ASCENDING), ("created_at", DESCENDING)], name="agent_time"),
        IndexModel([("memory_id", ASCENDING)], unique=True, name="memory_id_unique"),
    ])

    # connectors
    await Connector.get_motor_collection().create_indexes([
        IndexModel([("tenant_id", ASCENDING), ("system_type", ASCENDING)], name="tenant_type"),
        IndexModel([("connector_id", ASCENDING)], unique=True, name="connector_id_unique"),
    ])

    logger.info("All MongoDB indexes created successfully")


async def create_atlas_search_indexes():
    """
    Create Atlas Search and Vector Search indexes.
    NOTE: These require MongoDB Atlas M10+ tier.
    Run this script manually or via infrastructure setup.
    Index definitions provided as reference for manual Atlas Console setup.
    """
    AUDIT_SEARCH_INDEX = {
        "name": "audit_search",
        "definition": {
            "mappings": {
                "dynamic": False,
                "fields": {
                    "event_type": {"type": "string"},
                    "actor_id": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "workflow_id": {"type": "string"},
                    "payload": {"type": "document", "dynamic": True},
                }
            }
        }
    }

    DECISION_SEARCH_INDEX = {
        "name": "decision_search",
        "definition": {
            "mappings": {
                "dynamic": False,
                "fields": {
                    "reasoning_trace": {"type": "string"},
                    "decision_value": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "workflow_id": {"type": "string"},
                }
            }
        }
    }

    AGENT_MEMORY_VECTOR_INDEX = {
        "name": "agent_memory_vector",
        "definition": {
            "fields": [
                {
                    "numDimensions": 1536,
                    "path": "embedding",
                    "similarity": "cosine",
                    "type": "vector"
                },
                {
                    "path": "tenant_id",
                    "type": "filter"
                },
                {
                    "path": "workflow_id",
                    "type": "filter"
                }
            ]
        }
    }

    logger.info("Atlas Search indexes definition reference logged. Create manually in Atlas Console.")
    logger.info(f"Audit Search: {AUDIT_SEARCH_INDEX}")
    logger.info(f"Decision Search: {DECISION_SEARCH_INDEX}")
    logger.info(f"Vector Search: {AGENT_MEMORY_VECTOR_INDEX}")
