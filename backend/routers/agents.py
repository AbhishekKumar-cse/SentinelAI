"""
Agents Router — agent fleet management endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


@router.get("/agents", summary="List all agent instances")
async def list_agents(
    request: Request,
    family: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List all agents with their current status and performance metrics."""
    from db.models import AgentInstance, AgentFamily, AgentStatus

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    filters = [AgentInstance.tenant_id == tenant_id]

    if family:
        try:
            filters.append(AgentInstance.family == AgentFamily(family))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid agent family: {family}")

    if status:
        try:
            filters.append(AgentInstance.status == AgentStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    agents = await AgentInstance.find(*filters).to_list()

    return {
        "agents": [
            {
                "agent_id": a.agent_id,
                "family": a.family,
                "name": a.name,
                "status": a.status,
                "current_task_id": a.current_task_id,
                "performance_metrics": a.performance_metrics.model_dump(),
                "last_heartbeat_at": a.last_heartbeat_at.isoformat(),
                "capabilities": a.capabilities,
            }
            for a in agents
        ],
        "count": len(agents),
    }


@router.get("/agents/{agent_id}", summary="Get agent detail")
async def get_agent(agent_id: str, request: Request):
    """Agent detail: current task, 30-day performance history."""
    from db.models import AgentInstance

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    agent = await AgentInstance.find_one(
        AgentInstance.agent_id == agent_id,
        AgentInstance.tenant_id == tenant_id,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id": agent.agent_id,
        "family": agent.family,
        "name": agent.name,
        "status": agent.status,
        "current_task_id": agent.current_task_id,
        "capabilities": agent.capabilities,
        "performance_metrics": agent.performance_metrics.model_dump(),
        "last_heartbeat_at": agent.last_heartbeat_at.isoformat(),
        "host": agent.host,
    }


@router.get("/agents/{agent_id}/decisions", summary="Agent decision history")
async def get_agent_decisions(
    agent_id: str,
    request: Request,
    limit: int = Query(50),
):
    """Paginated decision history for a specific agent."""
    from db.models import DecisionRecord

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    records = await DecisionRecord.find(
        DecisionRecord.agent_id == agent_id,
        DecisionRecord.tenant_id == tenant_id,
    ).sort(-DecisionRecord.created_at).limit(limit).to_list()

    return {
        "decisions": [
            {
                "decision_id": r.decision_id,
                "workflow_id": r.workflow_id,
                "decision_type": r.decision_type,
                "confidence": r.confidence,
                "requires_human_review": r.requires_human_review,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
        "count": len(records),
    }


class AgentStateChange(BaseModel):
    reason: Optional[str] = None


@router.post("/agents/{agent_id}/disable", summary="Disable agent")
async def disable_agent(agent_id: str, body: AgentStateChange, request: Request):
    """Gracefully disable an agent (waits for current task to complete)."""
    from db.models import AgentInstance, AgentStatus

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    agent = await AgentInstance.find_one(
        AgentInstance.agent_id == agent_id,
        AgentInstance.tenant_id == tenant_id,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await agent.set({AgentInstance.status: AgentStatus.DISABLED})
    return {"agent_id": agent_id, "status": "DISABLED"}


@router.post("/agents/{agent_id}/enable", summary="Enable agent")
async def enable_agent(agent_id: str, request: Request):
    """Re-enable a disabled or degraded agent."""
    from db.models import AgentInstance, AgentStatus

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    agent = await AgentInstance.find_one(
        AgentInstance.agent_id == agent_id,
        AgentInstance.tenant_id == tenant_id,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await agent.set({AgentInstance.status: AgentStatus.IDLE})
    return {"agent_id": agent_id, "status": "IDLE"}
