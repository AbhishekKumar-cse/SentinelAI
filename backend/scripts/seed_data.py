"""
Seed data script — creates demo tenant, users, templates, workflows, meetings.
Run: python scripts/seed_data.py
"""
import asyncio
import json
import uuid
import hashlib
from datetime import datetime, timedelta
import random

# We need to set PYTHONPATH
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def seed():
    """Main seed function — creates all demo data."""
    from db.mongodb import init_mongodb
    from db.models import (
        Tenant, User, ProcessTemplate, WorkflowRun, WorkflowTask,
        AgentInstance, AuditRecord, DecisionRecord, HumanTask,
        Escalation, Meeting, ActionItem, Connector,
        SLAConfig, DAGNode, DAGEdge, DAGDefinition,
        SLAConfigEmbedded, PerformanceMetrics,
        WorkflowStatus, TaskStatus, AgentStatus, AgentFamily, HumanTaskStatus, Priority,
        EscalationStatus, ActorType, ConnectorStatus, UserRole,
    )
    import services.audit_service as audit_service

    print("Connecting to MongoDB...")
    os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0")
    os.environ.setdefault("ENVIRONMENT", "development")
    await init_mongodb()
    print("Connected!")

    TENANT_ID = "demo_tenant_001"

    # ── 1. Create Tenant ──────────────────────────────────────────────────
    existing = await Tenant.find_one(Tenant.tenant_id == TENANT_ID)
    if not existing:
        tenant = Tenant(
            tenant_id=TENANT_ID,
            name="AntiGravity Demo Corp",
            plan="ENTERPRISE",
            settings={"timezone": "Asia/Kolkata", "currency": "INR"},
            feature_flags={"mia_enabled": True, "advanced_analytics": True},
            billing_email="billing@democorp.com",
        )
        await tenant.insert()
        print(f"✓ Created tenant: {TENANT_ID}")
    else:
        print(f"  Tenant already exists: {TENANT_ID}")

    # ── 2. Create Users ───────────────────────────────────────────────────
    users_data = [
        {"uid": "user_admin_001", "email": "admin@democorp.com", "display_name": "Priya Sharma", "role": UserRole.TENANT_ADMIN},
        {"uid": "user_manager_001", "email": "manager@democorp.com", "display_name": "Arjun Mehta", "role": UserRole.WORKFLOW_MANAGER},
        {"uid": "user_operator_001", "email": "operator1@democorp.com", "display_name": "Kavya Reddy", "role": UserRole.AGENT_OPERATOR},
        {"uid": "user_operator_002", "email": "operator2@democorp.com", "display_name": "Rohit Kumar", "role": UserRole.AGENT_OPERATOR},
        {"uid": "user_auditor_001", "email": "auditor@democorp.com", "display_name": "Sneha Patel", "role": UserRole.AUDITOR},
    ]

    for u_data in users_data:
        existing_user = await User.find_one(User.uid == u_data["uid"])
        if not existing_user:
            user = User(
                uid=u_data["uid"],
                tenant_id=TENANT_ID,
                email=u_data["email"],
                display_name=u_data["display_name"],
                role=u_data["role"],
                last_active_at=datetime.utcnow() - timedelta(hours=random.randint(0, 48)),
            )
            await user.insert()
        print(f"✓ User: {u_data['display_name']} ({u_data['role']})")

    # ── 3. Create Process Templates ───────────────────────────────────────
    templates = [
        {
            "template_id": "tmpl_p2p_001",
            "name": "Procurement to Payment",
            "description": "End-to-end purchase order to payment workflow",
            "dag": DAGDefinition(
                nodes=[
                    DAGNode(node_id="start", node_type="START", label="Start"),
                    DAGNode(node_id="validate_pr", node_type="TASK", label="Validate PR", agent_family="DRA", task_type="VALIDATE_REQUISITION", estimated_duration_seconds=300),
                    DAGNode(node_id="check_budget", node_type="TASK", label="Check Budget", agent_family="DRA", task_type="CHECK_BUDGET", estimated_duration_seconds=120),
                    DAGNode(node_id="select_vendor", node_type="TASK", label="Select Vendor", agent_family="DMA", task_type="VENDOR_SELECTION", estimated_duration_seconds=600),
                    DAGNode(node_id="create_po", node_type="TASK", label="Create PO", agent_family="AEA", task_type="CREATE_PO", estimated_duration_seconds=180),
                    DAGNode(node_id="three_way_match", node_type="TASK", label="3-Way Match", agent_family="VA", task_type="THREE_WAY_MATCH", estimated_duration_seconds=300),
                    DAGNode(node_id="execute_payment", node_type="TASK", label="Execute Payment", agent_family="AEA", task_type="EXECUTE_PAYMENT", estimated_duration_seconds=120),
                    DAGNode(node_id="end", node_type="END", label="End"),
                ],
                edges=[
                    DAGEdge(edge_id="e1", source="start", target="validate_pr"),
                    DAGEdge(edge_id="e2", source="validate_pr", target="check_budget"),
                    DAGEdge(edge_id="e3", source="check_budget", target="select_vendor"),
                    DAGEdge(edge_id="e4", source="select_vendor", target="create_po"),
                    DAGEdge(edge_id="e5", source="create_po", target="three_way_match"),
                    DAGEdge(edge_id="e6", source="three_way_match", target="execute_payment"),
                    DAGEdge(edge_id="e7", source="execute_payment", target="end"),
                ],
                input_schema={
                    "vendor_id": {"type": "string", "required": True},
                    "amount": {"type": "number", "required": True},
                    "currency": {"type": "string", "default": "INR"},
                },
                entry_node="validate_pr",
            ),
        },
        {
            "template_id": "tmpl_onboard_001",
            "name": "Employee Onboarding",
            "description": "Complete new employee onboarding from HR to active status",
            "dag": DAGDefinition(
                nodes=[
                    DAGNode(node_id="start", node_type="START", label="Start"),
                    DAGNode(node_id="validate_hire", node_type="TASK", label="Validate Hire Data", agent_family="DRA", task_type="VALIDATE_HIRE", estimated_duration_seconds=120),
                    DAGNode(node_id="create_accounts", node_type="TASK", label="Create Accounts", agent_family="AEA", task_type="CREATE_ACCOUNTS", estimated_duration_seconds=300),
                    DAGNode(node_id="send_welcome", node_type="TASK", label="Send Welcome Kit", agent_family="AEA", task_type="SEND_WELCOME", estimated_duration_seconds=60),
                    DAGNode(node_id="end", node_type="END", label="End"),
                ],
                edges=[
                    DAGEdge(edge_id="e1", source="start", target="validate_hire"),
                    DAGEdge(edge_id="e2", source="validate_hire", target="create_accounts"),
                    DAGEdge(edge_id="e3", source="create_accounts", target="send_welcome"),
                    DAGEdge(edge_id="e4", source="send_welcome", target="end"),
                ],
                entry_node="validate_hire",
            ),
        },
        {
            "template_id": "tmpl_contract_001",
            "name": "Contract Lifecycle",
            "description": "AI-powered contract review, negotiation, and signature tracking",
            "dag": DAGDefinition(
                nodes=[
                    DAGNode(node_id="start", node_type="START", label="Start"),
                    DAGNode(node_id="ingest", node_type="TASK", label="Ingest Contract", agent_family="DRA", task_type="INGEST_CONTRACT", estimated_duration_seconds=60),
                    DAGNode(node_id="ai_review", node_type="TASK", label="AI Legal Review", agent_family="DMA", task_type="AI_REVIEW", estimated_duration_seconds=1800),
                    DAGNode(node_id="signature", node_type="TASK", label="DocuSign", agent_family="AEA", task_type="PREPARE_SIGNATURE", estimated_duration_seconds=300),
                    DAGNode(node_id="end", node_type="END", label="End"),
                ],
                edges=[
                    DAGEdge(edge_id="e1", source="start", target="ingest"),
                    DAGEdge(edge_id="e2", source="ingest", target="ai_review"),
                    DAGEdge(edge_id="e3", source="ai_review", target="signature"),
                    DAGEdge(edge_id="e4", source="signature", target="end"),
                ],
                entry_node="ingest",
            ),
        },
    ]

    for tmpl_data in templates:
        existing_tmpl = await ProcessTemplate.find_one(ProcessTemplate.template_id == tmpl_data["template_id"])
        if not existing_tmpl:
            tmpl = ProcessTemplate(
                template_id=tmpl_data["template_id"],
                tenant_id=TENANT_ID,
                name=tmpl_data["name"],
                description=tmpl_data.get("description"),
                version=1,
                dag=tmpl_data["dag"],
                sla_config=SLAConfigEmbedded(max_duration_seconds=86400),
                created_by="user_admin_001",
                is_active=True,
            )
            await tmpl.insert()
        print(f"✓ Template: {tmpl_data['name']}")

    # ── 4. Create Agent Instances ─────────────────────────────────────────
    agent_configs = [
        {"family": AgentFamily.MOA, "name": "MOA-Prime"},
        {"family": AgentFamily.DRA, "name": "DRA-Alpha"},
        {"family": AgentFamily.DRA, "name": "DRA-Beta"},
        {"family": AgentFamily.DMA, "name": "DMA-Reasoning"},
        {"family": AgentFamily.AEA, "name": "AEA-Executor"},
        {"family": AgentFamily.VA, "name": "VA-Guardian"},
        {"family": AgentFamily.MIA, "name": "MIA-Intelligence"},
    ]

    for ac in agent_configs:
        agent_id = f"agent_{ac['family'].lower()}_{uuid.uuid4().hex[:8]}"
        existing = await AgentInstance.find_one(AgentInstance.name == ac["name"], AgentInstance.tenant_id == TENANT_ID)
        if not existing:
            inst = AgentInstance(
                agent_id=agent_id,
                tenant_id=TENANT_ID,
                family=ac["family"],
                name=ac["name"],
                status=random.choice([AgentStatus.IDLE, AgentStatus.IDLE, AgentStatus.BUSY]),
                capabilities=["task_execution", "audit_writing"],
                performance_metrics=PerformanceMetrics(
                    tasks_completed=random.randint(10, 200),
                    tasks_failed=random.randint(0, 5),
                    avg_task_duration_seconds=random.uniform(60, 600),
                    avg_confidence=random.uniform(0.75, 0.98),
                    error_rate=random.uniform(0, 0.05),
                    last_24h_throughput=random.randint(5, 50),
                ),
            )
            await inst.insert()
        print(f"✓ Agent: {ac['name']}")

    # ── 5. Create Workflow Runs with Audit Chains ──────────────────────────
    workflow_scenarios = [
        {"template_id": "tmpl_p2p_001", "name": "PO-INR-2024-001", "status": WorkflowStatus.COMPLETED, "health_score": 98.0, "context": {"vendor_id": "V001", "amount": 500000, "currency": "INR"}},
        {"template_id": "tmpl_p2p_001", "name": "PO-INR-2024-002", "status": WorkflowStatus.RUNNING, "health_score": 84.0, "context": {"vendor_id": "V002", "amount": 2000000}},
        {"template_id": "tmpl_onboard_001", "name": "Onboard-Priya-Kumar", "status": WorkflowStatus.RUNNING, "health_score": 92.0, "context": {"employee_name": "Priya Kumar", "department": "Engineering"}},
        {"template_id": "tmpl_contract_001", "name": "Contract-Vendor-ABC", "status": WorkflowStatus.PAUSED, "health_score": 65.0, "breach_probability": 0.55, "context": {"contract_id": "CTR-2024-001"}},
        {"template_id": "tmpl_p2p_001", "name": "PO-INR-2024-003", "status": WorkflowStatus.FAILED, "health_score": 12.0, "context": {"vendor_id": "V003"}},
    ]

    for i, scenario in enumerate(workflow_scenarios):
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        started_at = datetime.utcnow() - timedelta(hours=random.randint(1, 24))
        completed_at = started_at + timedelta(hours=random.randint(2, 8)) if scenario["status"] == WorkflowStatus.COMPLETED else None

        existing_wf = await WorkflowRun.find_one(WorkflowRun.name == scenario["name"])
        if existing_wf:
            workflow_id = existing_wf.workflow_id
            print(f"  Workflow already exists: {scenario['name']}")
            continue

        run = WorkflowRun(
            workflow_id=workflow_id,
            tenant_id=TENANT_ID,
            template_id=scenario["template_id"],
            name=scenario["name"],
            status=scenario["status"],
            context=scenario.get("context", {}),
            health_score=scenario.get("health_score", 100.0),
            breach_probability=scenario.get("breach_probability", 0.1),
            started_at=started_at,
            completed_at=completed_at,
        )
        await run.insert()

        # Create realistic audit trail
        events = [
            ("WORKFLOW_STARTED", "user_admin_001", {"template_id": scenario["template_id"]}),
            ("TASK_ASSIGNED", f"agent_moa_001", {"task_type": "VALIDATE_REQUISITION"}),
            ("DATA_FETCHED", f"agent_dra_001", {"entity_type": "purchase_order", "records": 1}),
            ("AGENT_DECISION_MADE", f"agent_dma_001", {"confidence": 0.92, "decision": "APPROVED"}),
            ("ACTION_EXECUTED", f"agent_aea_001", {"action_type": "CREATE_PO", "idempotency_key": uuid.uuid4().hex}),
        ]
        if scenario["status"] == WorkflowStatus.COMPLETED:
            events.append(("WORKFLOW_COMPLETED", "user_admin_001", {"duration_hours": random.randint(2, 8)}))
        elif scenario["status"] == WorkflowStatus.FAILED:
            events.append(("WORKFLOW_FAILED", f"agent_moa_001", {"reason": "Three-way match failed", "tier": 4}))

        prev_hash = hashlib.sha256(b"ANTIGRAVITY_GENESIS").hexdigest()
        for event_type, actor_id, payload in events:
            import time
            time.sleep(0.1)  # Ensure distinct timestamps
            timestamp = datetime.utcnow()
            curr_hash = hashlib.sha256(
                f"{event_type}{actor_id}{json.dumps(payload, sort_keys=True)}{prev_hash}{timestamp.isoformat()}".encode()
            ).hexdigest()

            record = AuditRecord(
                audit_id=str(uuid.uuid4()),
                tenant_id=TENANT_ID,
                workflow_id=workflow_id,
                event_type=event_type,
                actor_type=ActorType.AGENT if "agent" in actor_id else ActorType.USER,
                actor_id=actor_id,
                payload=payload,
                prev_hash=prev_hash,
                curr_hash=curr_hash,
                created_at=timestamp,
            )
            await record.insert()
            prev_hash = curr_hash

        print(f"✓ Workflow: {scenario['name']} ({scenario['status']})")

    # ── 6. Create Human Tasks ──────────────────────────────────────────────
    human_tasks = [
        {"title": "Review vendor risk assessment", "assignee_id": "user_manager_001", "priority": Priority.HIGH, "status": HumanTaskStatus.PENDING},
        {"title": "Approve payment for PO-2024-001", "assignee_id": "user_admin_001", "priority": Priority.CRITICAL, "status": HumanTaskStatus.PENDING},
        {"title": "Review contract anomalies", "assignee_id": "user_operator_001", "priority": Priority.MEDIUM, "status": HumanTaskStatus.IN_PROGRESS},
        {"title": "Complete 30-day check-in for Priya Kumar", "assignee_id": "user_operator_002", "priority": Priority.LOW, "status": HumanTaskStatus.PENDING},
    ]

    for ht_data in human_tasks:
        ht = HumanTask(
            human_task_id=str(uuid.uuid4()),
            workflow_id=f"wf_{uuid.uuid4().hex[:12]}",
            tenant_id=TENANT_ID,
            assignee_id=ht_data["assignee_id"],
            title=ht_data["title"],
            description=f"Please review and take action on: {ht_data['title']}",
            context_snapshot={"workflow_name": "Demo Workflow", "created_by": "system"},
            status=ht_data["status"],
            priority=ht_data["priority"],
            due_at=datetime.utcnow() + timedelta(hours=random.randint(4, 72)),
        )
        await ht.insert()
        print(f"✓ Human Task: {ht_data['title'][:50]}")

    # ── 7. Create Escalations ──────────────────────────────────────────────
    for j in range(2):
        esc = Escalation(
            escalation_id=str(uuid.uuid4()),
            workflow_id=f"wf_{uuid.uuid4().hex[:12]}",
            tenant_id=TENANT_ID,
            trigger_type="SLA_BREACH",
            risk_score=0.75 + j * 0.1,
            predicted_breach_at=datetime.utcnow() + timedelta(hours=2),
            assigned_to="user_manager_001",
            status=EscalationStatus.OPEN,
            escalation_level=1,
        )
        await esc.insert()
    print(f"✓ Created 2 escalations")

    # ── 8. Create Meetings ─────────────────────────────────────────────────
    meeting = Meeting(
        meeting_id=str(uuid.uuid4()),
        tenant_id=TENANT_ID,
        external_meeting_id="zoom_mtg_001",
        source="ZOOM",
        participants=[
            {"uid": "user_admin_001", "name": "Priya Sharma", "email": "admin@democorp.com"},
            {"uid": "user_manager_001", "name": "Arjun Mehta", "email": "manager@democorp.com"},
        ],
        status="ANALYZED",
        summary_doc={
            "decisions": [{"text": "Approved Q4 vendor consolidation", "maker": "Priya Sharma", "confidence": 0.95}],
            "action_items": [{"description": "Review vendor contracts by Friday", "owner": "Arjun Mehta"}],
        },
        sentiment_timeline=[
            {"timestamp": "09:00", "participant": "Priya Sharma", "score": 0.8},
            {"timestamp": "09:30", "participant": "Arjun Mehta", "score": 0.6},
        ],
        meeting_at=datetime.utcnow() - timedelta(days=1),
    )
    await meeting.insert()
    print(f"✓ Created demo meeting")

    # ── 9. Create Connectors ───────────────────────────────────────────────
    connector_types = ["salesforce", "jira", "slack", "sendgrid"]
    for ct in connector_types:
        existing_c = await Connector.find_one(Connector.system_type == ct, Connector.tenant_id == TENANT_ID)
        if not existing_c:
            from services.encryption_service import encrypt_dict
            conn = Connector(
                connector_id=str(uuid.uuid4()),
                tenant_id=TENANT_ID,
                system_type=ct,
                display_name=ct.title(),
                config_encrypted=encrypt_dict({"api_key": "demo_key_placeholder"}),
                status=ConnectorStatus.ACTIVE,
                last_health_check_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 60)),
            )
            await conn.insert()
        print(f"✓ Connector: {ct}")

    print("\n✅ Seed data complete!")
    print("  Login: demo@antigravity.ai / Demo@1234 (Firebase Auth)")
    print("  Dev bypass available in development mode")


if __name__ == "__main__":
    asyncio.run(seed())
