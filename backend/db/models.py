
"""
Beanie ODM document models for ALL 21 MongoDB collections.
Every model inherits from Document and includes tenantId, createdAt, updatedAt.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional
from enum import Enum

from beanie import Document, Indexed, before_event, Insert, Replace, SaveChanges
from pydantic import BaseModel, Field, EmailStr
from pymongo import IndexModel, ASCENDING, DESCENDING


# ─── Enums ───────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    TENANT_ADMIN = "TENANT_ADMIN"
    WORKFLOW_MANAGER = "WORKFLOW_MANAGER"
    AGENT_OPERATOR = "AGENT_OPERATOR"
    AUDITOR = "AUDITOR"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"


class WorkflowStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class AgentFamily(str, Enum):
    MOA = "MOA"
    DRA = "DRA"
    DMA = "DMA"
    AEA = "AEA"
    VA = "VA"
    MIA = "MIA"


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    RESTARTING = "RESTARTING"
    DISABLED = "DISABLED"
    STUCK = "STUCK"


class SLAStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"


class HumanTaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class EscalationStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ConnectorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    DISABLED = "DISABLED"


class ActorType(str, Enum):
    AGENT = "AGENT"
    USER = "USER"
    SYSTEM = "SYSTEM"
    API = "API"


# ─── Embedded Models ──────────────────────────────────────────────────────────

class DAGNode(BaseModel):
    node_id: str
    node_type: str  # TASK | GATEWAY | HUMAN | START | END
    label: str
    agent_family: Optional[str] = None
    task_type: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)
    estimated_duration_seconds: Optional[int] = None
    position: Optional[dict[str, float]] = None  # {x, y} for React Flow


class DAGEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    label: Optional[str] = None
    condition: Optional[str] = None  # Python expression for conditional edges


class DAGDefinition(BaseModel):
    nodes: list[DAGNode] = Field(default_factory=list)
    edges: list[DAGEdge] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    entry_node: Optional[str] = None


class SLAConfigEmbedded(BaseModel):
    max_duration_seconds: int = 86400  # 24 hours default
    warning_threshold: float = 0.7
    breach_threshold: float = 0.9
    escalation_policy: dict[str, Any] = Field(default_factory=dict)


class PerformanceMetrics(BaseModel):
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_task_duration_seconds: float = 0.0
    avg_confidence: float = 0.0
    error_rate: float = 0.0
    last_24h_throughput: int = 0


# ─── Collection Documents ─────────────────────────────────────────────────────

class Tenant(Document):
    tenant_id: Indexed(str, unique=True)
    name: str
    plan: str = "FREE"  # FREE | STARTER | GROWTH | ENTERPRISE
    settings: dict[str, Any] = Field(default_factory=dict)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    billing_email: Optional[EmailStr] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "tenants"


class User(Document):
    uid: Indexed(str, unique=True)  # Firebase UID
    tenant_id: Indexed(str)
    email: EmailStr
    display_name: Optional[str] = None
    role: UserRole = UserRole.AGENT_OPERATOR
    preferences: dict[str, Any] = Field(default_factory=dict)
    slack_user_id: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    last_active_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "users"


class ProcessTemplate(Document):
    template_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    name: str
    description: Optional[str] = None
    version: int = 1
    dag: DAGDefinition = Field(default_factory=DAGDefinition)
    sla_config: SLAConfigEmbedded = Field(default_factory=SLAConfigEmbedded)
    tags: list[str] = Field(default_factory=list)
    created_by: str  # Firebase UID
    is_active: bool = True
    approval_policies: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "processTemplates"


class WorkflowRun(Document):
    workflow_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    template_id: Indexed(str)
    name: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.INITIALIZING
    context: dict[str, Any] = Field(default_factory=dict)
    health_score: float = 100.0
    sla_status: SLAStatus = SLAStatus.ON_TRACK
    breach_probability: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_node_id: Optional[str] = None
    assigned_agents: list[str] = Field(default_factory=list)
    paused_by: Optional[str] = None
    pause_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "workflowRuns"
        indexes = [
            IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING), ("started_at", DESCENDING)]),
            IndexModel([("tenant_id", ASCENDING), ("template_id", ASCENDING)]),
            IndexModel([("workflow_id", ASCENDING)], unique=True),
        ]


class WorkflowTask(Document):
    task_id: Indexed(str, unique=True)
    workflow_id: Indexed(str)
    tenant_id: Indexed(str)
    node_id: str  # Reference to DAG node
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    due_at: Optional[datetime] = None
    attempt_count: int = 0
    max_attempts: int = 5
    last_error: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    dependencies: list[str] = Field(default_factory=list)  # task_ids this depends on
    stop_requested: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "workflowTasks"
        indexes = [
            IndexModel([("workflow_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("assigned_agent_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("tenant_id", ASCENDING), ("due_at", ASCENDING)]),
        ]


class AgentInstance(Document):
    agent_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    family: AgentFamily
    name: str
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    performance_metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics)
    process_id: Optional[int] = None
    host: Optional[str] = None
    last_heartbeat_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "agentInstances"
        indexes = [
            IndexModel([("tenant_id", ASCENDING), ("family", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("last_heartbeat_at", ASCENDING)]),
        ]


class AuditRecord(Document):
    """
    IMMUTABLE append-only collection.
    Hash chain: currHash = SHA256(eventType + actorId + payload_json + prevHash + timestamp)
    """
    audit_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    workflow_id: Optional[Indexed(str)] = None
    task_id: Optional[str] = None
    event_type: str
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    curr_hash: Indexed(str, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "auditRecords"
        indexes = [
            IndexModel([("workflow_id", ASCENDING), ("created_at", ASCENDING)]),
            IndexModel([("tenant_id", ASCENDING), ("event_type", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("curr_hash", ASCENDING)], unique=True),
        ]


class DecisionRecord(Document):
    decision_id: Indexed(str, unique=True)
    workflow_id: Indexed(str)
    task_id: Optional[str] = None
    agent_id: str
    tenant_id: Indexed(str)
    decision_type: str
    decision_value: Any
    confidence: float  # 0.0 - 1.0
    requires_human_review: bool = False
    reasoning_trace: list[str] = Field(default_factory=list)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    alternatives_considered: list[dict[str, Any]] = Field(default_factory=list)
    model_version: str = "claude-sonnet-4-20250514"
    human_override: Optional[dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "decisionRecords"
        indexes = [
            IndexModel([("workflow_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("agent_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("tenant_id", ASCENDING), ("decision_type", ASCENDING)]),
        ]


class ActionRecord(Document):
    action_id: Indexed(str, unique=True)
    workflow_id: Indexed(str)
    task_id: Optional[str] = None
    agent_id: str
    tenant_id: Indexed(str)
    action_type: str
    action_payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Indexed(str, unique=True)
    status: str = "PENDING"  # PENDING | SUCCESS | FAILED | ROLLEDBACK
    response: Optional[dict[str, Any]] = None
    before_snapshot: Optional[dict[str, Any]] = None
    after_snapshot: Optional[dict[str, Any]] = None
    rollback_strategy: Optional[str] = None
    compensating_function: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "actionRecords"


class HumanTask(Document):
    human_task_id: Indexed(str, unique=True)
    workflow_id: Indexed(str)
    tenant_id: Indexed(str)
    assignee_id: Indexed(str)  # Firebase UID
    title: str
    description: str
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    status: HumanTaskStatus = HumanTaskStatus.PENDING
    priority: Priority = Priority.MEDIUM
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    outcome: Optional[str] = None
    reminder_count: int = 0
    temporal_timer_id: Optional[str] = None
    deep_link: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "humanTasks"
        indexes = [
            IndexModel([("assignee_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING), ("priority", DESCENDING)]),
            IndexModel([("due_at", ASCENDING)]),
        ]


class Escalation(Document):
    escalation_id: Indexed(str, unique=True)
    workflow_id: Indexed(str)
    tenant_id: Indexed(str)
    trigger_type: str  # SLA_BREACH | AGENT_FAILURE | DATA_QUALITY | COMPLIANCE
    risk_score: float
    predicted_breach_at: Optional[datetime] = None
    assigned_to: Optional[str] = None  # Firebase UID
    channel: Optional[str] = None  # SLACK | EMAIL | SMS
    status: EscalationStatus = EscalationStatus.OPEN
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    escalation_level: int = 1
    next_escalation_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "escalations"


class Meeting(Document):
    meeting_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    external_meeting_id: Optional[str] = None
    source: str  # ZOOM | TEAMS | GOOGLE_MEET | MANUAL
    participants: list[dict[str, str]] = Field(default_factory=list)
    transcript_storage_uri: Optional[str] = None
    summary_doc: Optional[dict[str, Any]] = None
    sentiment_timeline: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "PROCESSING"  # PROCESSING | ANALYZED | ARCHIVED
    meeting_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    workflow_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "meetings"


class ActionItem(Document):
    action_item_id: Indexed(str, unique=True)
    meeting_id: Indexed(str)
    workflow_id: Optional[str] = None
    tenant_id: Indexed(str)
    description: str
    owner_id: Optional[str] = None  # Firebase UID
    owner_mention: Optional[str] = None  # Raw mention from transcript
    assignee_name: Optional[str] = None  # Raw name extracted from transcript
    due_at: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    status: str = "PENDING"  # PENDING | IN_PROGRESS | COMPLETED | OVERDUE
    completed_at: Optional[datetime] = None
    reminder_count: int = 0
    linked_human_task_id: Optional[str] = None
    linked_workflow_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "actionItems"


class Connector(Document):
    connector_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    system_type: str  # sap | netsuite | salesforce | jira | servicenow | etc.
    display_name: Optional[str] = None
    config_encrypted: dict[str, Any] = Field(default_factory=dict)  # AES-256-GCM encrypted
    field_mapping: dict[str, Any] = Field(default_factory=dict)
    normalization_rules: list[dict[str, Any]] = Field(default_factory=list)
    status: ConnectorStatus = ConnectorStatus.ACTIVE
    last_health_check_at: Optional[datetime] = None
    error_log: list[dict[str, Any]] = Field(default_factory=list)
    rate_limit_config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "connectors"


class NotificationLog(Document):
    notif_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    workflow_id: Optional[str] = None
    channel: str  # EMAIL | SLACK | SMS
    recipient: str
    subject: Optional[str] = None
    body_storage_uri: Optional[str] = None
    status: str = "PENDING"  # PENDING | SENT | DELIVERED | FAILED | BOUNCED
    external_id: Optional[str] = None  # SendGrid message_id, Slack ts, etc.
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "notificationLog"


class APIKey(Document):
    key_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    user_id: str  # Firebase UID
    key_hash: str  # bcrypt hash
    name: str
    permissions: list[str] = Field(default_factory=list)
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "apiKeys"


class SLAConfig(Document):
    sla_id: Indexed(str, unique=True)
    template_id: Indexed(str)
    tenant_id: Indexed(str)
    task_type: str
    max_duration_seconds: int = 86400
    warning_threshold: float = 0.7
    breach_threshold: float = 0.9
    escalation_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "slaConfigs"


class VectorNamespace(Document):
    ns_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    workflow_id: Optional[str] = None
    qdrant_collection_name: str
    document_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "vectorNamespaces"


class RulesEngine(Document):
    rule_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    rule_name: str
    rule_set_id: str
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    priority: int = 0
    is_active: bool = True
    stop_on_match: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event([Replace, SaveChanges])
    def update_updated_at(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "rulesEngine"


class ActionRegistry(Document):
    action_type: Indexed(str, unique=True)
    connector_type: str
    handler_function: str
    compensating_function: Optional[str] = None
    schema: dict[str, Any] = Field(default_factory=dict)
    required_permissions: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "actionRegistry"


class AgentMemory(Document):
    """Long-term agent episodic memory. Embeddings stored in Qdrant."""
    memory_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: str
    content: str
    content_type: str = "TEXT"  # TEXT | DECISION | ACTION | OUTCOME
    embedding_id: Optional[str] = None  # Qdrant point ID
    qdrant_collection: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "agentMemory"


class VerificationRecord(Document):
    verification_id: Indexed(str, unique=True)
    workflow_id: Optional[Indexed(str)] = None
    action_record_id: Optional[str] = None
    agent_id: str
    tenant_id: Indexed(str)
    verification_type: str  # ACTION_OUTCOME | SCHEMA | THREE_WAY_MATCH etc.
    is_passed: bool
    confidence: float = 1.0
    checks_passed: list[dict[str, Any]] = Field(default_factory=list)
    checks_failed: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "verificationRecords"
        indexes = [
            IndexModel([(("workflow_id", ASCENDING), ("created_at", DESCENDING))]),
            IndexModel([(("agent_id", ASCENDING), ("created_at", DESCENDING))]),
        ]


class PIIToken(Document):
    """PII tokenization mapping. Encrypted at rest."""
    token_id: Indexed(str, unique=True)
    tenant_id: Indexed(str)
    pii_type: str  # EMAIL | PHONE | AADHAAR | PAN | CREDIT_CARD
    token: Indexed(str, unique=True)
    original_encrypted: str  # AES-256-GCM encrypted original value
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    class Settings:
        name = "piiTokens"
