"""
Analytics Router — SLA dashboards, agent performance, error rates, throughput.
"""
from typing import Optional
from fastapi import APIRouter, Request, Query
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/analytics/sla", summary="SLA adherence time series")
async def get_sla_analytics(
    request: Request,
    template_id: Optional[str] = Query(None),
    time_range_hours: int = Query(24, ge=1, le=720),
    granularity: str = Query("hour", regex="^(hour|day)$"),
):
    """SLA adherence percentage over time."""
    from db.models import WorkflowRun, WorkflowStatus, SLAStatus
    from collections import defaultdict

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    since = datetime.utcnow() - timedelta(hours=time_range_hours)

    filters = [
        WorkflowRun.tenant_id == tenant_id,
        WorkflowRun.started_at >= since,
    ]
    if template_id:
        filters.append(WorkflowRun.template_id == template_id)

    runs = await WorkflowRun.find(*filters).to_list()

    # Group by time bucket
    buckets = defaultdict(lambda: {"total": 0, "on_track": 0})
    for run in runs:
        if run.started_at:
            if granularity == "hour":
                bucket = run.started_at.strftime("%Y-%m-%dT%H:00:00Z")
            else:
                bucket = run.started_at.strftime("%Y-%m-%dT00:00:00Z")

            buckets[bucket]["total"] += 1
            if run.sla_status == SLAStatus.ON_TRACK:
                buckets[bucket]["on_track"] += 1

    series = []
    for timestamp in sorted(buckets.keys()):
        b = buckets[timestamp]
        adherence = (b["on_track"] / b["total"] * 100) if b["total"] > 0 else 100
        series.append({
            "timestamp": timestamp,
            "adherence_pct": round(adherence, 1),
            "total_workflows": b["total"],
            "on_track": b["on_track"],
        })

    return {"series": series, "granularity": granularity, "time_range_hours": time_range_hours}


@router.get("/analytics/agents", summary="Agent performance metrics")
async def get_agent_analytics(request: Request):
    """Per-family agent performance: throughput, duration, error rate, confidence."""
    from db.models import AgentInstance, DecisionRecord, AgentFamily
    from collections import defaultdict

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    agents = await AgentInstance.find(AgentInstance.tenant_id == tenant_id).to_list()

    family_stats = defaultdict(lambda: {
        "agent_count": 0,
        "busy_count": 0,
        "avg_duration_seconds": 0,
        "error_rate": 0,
        "avg_confidence": None,
    })

    for agent in agents:
        fam = str(agent.family)
        family_stats[fam]["agent_count"] += 1
        metrics = agent.performance_metrics
        family_stats[fam]["avg_duration_seconds"] = metrics.avg_task_duration_seconds
        family_stats[fam]["error_rate"] = metrics.error_rate

    # Add DMA confidence stats
    since = datetime.utcnow() - timedelta(days=30)
    decisions = await DecisionRecord.find(
        DecisionRecord.tenant_id == tenant_id,
        DecisionRecord.created_at >= since,
    ).to_list()

    if decisions:
        avg_conf = sum(d.confidence for d in decisions) / len(decisions)
        family_stats["DMA"]["avg_confidence"] = round(avg_conf, 3)

    return {
        "families": [
            {"family": fam, **stats}
            for fam, stats in family_stats.items()
        ]
    }


@router.get("/analytics/errors", summary="Error rate breakdown")
async def get_error_analytics(
    request: Request,
    time_range_hours: int = Query(24),
):
    """Error rate breakdown by type and agent family."""
    from db.models import WorkflowTask, TaskStatus

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    since = datetime.utcnow() - timedelta(hours=time_range_hours)

    tasks = await WorkflowTask.find(
        WorkflowTask.tenant_id == tenant_id,
        WorkflowTask.created_at >= since,
    ).to_list()

    from collections import Counter
    error_types = Counter(t.last_error[:50] if t.last_error else "NO_ERROR" for t in tasks if t.status == TaskStatus.FAILED)

    return {
        "total_tasks": len(tasks),
        "failed_tasks": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
        "error_rate_pct": round(sum(1 for t in tasks if t.status == TaskStatus.FAILED) / max(len(tasks), 1) * 100, 1),
        "error_breakdown": dict(error_types.most_common(10)),
        "time_range_hours": time_range_hours,
    }


@router.get("/analytics/throughput", summary="Workflow completion rates over time")
async def get_throughput(
    request: Request,
    time_range_hours: int = Query(168),  # 7 days default
    granularity: str = Query("day"),
):
    """Workflow completion rates over time, stacked by template."""
    from db.models import WorkflowRun, WorkflowStatus
    from collections import defaultdict

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    since = datetime.utcnow() - timedelta(hours=time_range_hours)

    runs = await WorkflowRun.find(
        WorkflowRun.tenant_id == tenant_id,
        WorkflowRun.completed_at >= since,
        WorkflowRun.status == WorkflowStatus.COMPLETED,
    ).to_list()

    buckets = defaultdict(lambda: defaultdict(int))
    for run in runs:
        if run.completed_at:
            bucket = run.completed_at.strftime("%Y-%m-%d")
            buckets[bucket][run.template_id] += 1

    series = []
    for date in sorted(buckets.keys()):
        entry = {"date": date}
        entry.update(buckets[date])
        entry["total"] = sum(buckets[date].values())
        series.append(entry)

    return {"series": series, "granularity": granularity}


@router.get("/analytics/decisions", summary="Decision quality over time")
async def get_decision_analytics(
    request: Request,
    time_range_hours: int = Query(168),
):
    """Decision quality: avg confidence, human review rate, override rate."""
    from db.models import DecisionRecord

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    since = datetime.utcnow() - timedelta(hours=time_range_hours)

    decisions = await DecisionRecord.find(
        DecisionRecord.tenant_id == tenant_id,
        DecisionRecord.created_at >= since,
    ).to_list()

    total = len(decisions)
    if total == 0:
        return {"total": 0, "avg_confidence": 0, "human_review_rate": 0}

    avg_confidence = sum(d.confidence for d in decisions) / total
    human_review_count = sum(1 for d in decisions if d.requires_human_review)
    override_count = sum(1 for d in decisions if d.human_override)

    return {
        "total_decisions": total,
        "avg_confidence": round(avg_confidence, 3),
        "human_review_rate": round(human_review_count / total, 3),
        "override_rate": round(override_count / total, 3),
        "high_confidence_count": sum(1 for d in decisions if d.confidence >= 0.8),
        "low_confidence_count": sum(1 for d in decisions if d.confidence < 0.6),
    }
