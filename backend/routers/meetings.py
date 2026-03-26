"""
Meetings Router — Meeting Intelligence Agent endpoints.
"""
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


class IngestMeetingRequest(BaseModel):
    external_meeting_id: Optional[str] = None
    source: str = "MANUAL"  # ZOOM | TEAMS | GOOGLE_MEET | MANUAL
    transcript_text: str
    recording_url: Optional[str] = None
    participants: List[dict] = Field(default_factory=list)
    meeting_at: Optional[datetime] = None


@router.post("/meetings/ingest", summary="Submit meeting transcript for analysis")
async def ingest_meeting(body: IngestMeetingRequest, request: Request):
    """
    Submit a meeting transcript for MIA processing.
    Triggers the MeetingIntelligenceWorkflow.
    """
    from db.models import Meeting
    from kafka.producer import publish

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    meeting_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    meeting = Meeting(
        meeting_id=meeting_id,
        tenant_id=tenant_id,
        external_meeting_id=body.external_meeting_id,
        source=body.source,
        participants=body.participants,
        status="PROCESSING",
        meeting_at=body.meeting_at or datetime.utcnow(),
        workflow_id=workflow_id,
    )
    await meeting.insert()

    # Emit to Kafka to trigger MeetingIntelligenceWorkflow
    await publish(
        topic="meetings.events",
        event_type="MeetingIngested",
        data={
            "meeting_id": meeting_id,
            "workflow_id": workflow_id,
            "source": body.source,
            "transcript_length": len(body.transcript_text),
            "participant_count": len(body.participants),
        },
        tenant_id=tenant_id,
        workflow_id=workflow_id,
    )

    return {
        "meeting_id": meeting_id,
        "workflow_id": workflow_id,
        "status": "PROCESSING",
        "message": "Meeting submitted for analysis",
    }


@router.get("/meetings", summary="List meetings")
async def list_meetings(
    request: Request,
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Paginated meeting list."""
    from db.models import Meeting

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    filters = [Meeting.tenant_id == tenant_id]

    if source:
        filters.append(Meeting.source == source)
    if status:
        filters.append(Meeting.status == status)

    meetings = await Meeting.find(*filters).sort(-Meeting.created_at).limit(limit).to_list()

    return {
        "meetings": [
            {
                "meeting_id": m.meeting_id,
                "source": m.source,
                "status": m.status,
                "participant_count": len(m.participants),
                "meeting_at": m.meeting_at.isoformat() if m.meeting_at else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in meetings
        ],
        "count": len(meetings),
    }


@router.get("/meetings/{meeting_id}", summary="Meeting intelligence detail")
async def get_meeting(meeting_id: str, request: Request):
    """Full meeting intelligence: decisions, actions, sentiment, summary."""
    from db.models import Meeting, ActionItem

    tenant_id = getattr(request.state, "tenant_id", "dev_tenant_001")
    meeting = await Meeting.find_one(
        Meeting.meeting_id == meeting_id,
        Meeting.tenant_id == tenant_id,
    )
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    action_items = await ActionItem.find(
        ActionItem.meeting_id == meeting_id,
    ).to_list()

    return {
        "meeting_id": meeting.meeting_id,
        "source": meeting.source,
        "status": meeting.status,
        "participants": meeting.participants,
        "meeting_at": meeting.meeting_at.isoformat() if meeting.meeting_at else None,
        "summary_doc": meeting.summary_doc,
        "sentiment_timeline": meeting.sentiment_timeline,
        "action_items": [
            {
                "action_item_id": a.action_item_id,
                "description": a.description,
                "owner_id": a.owner_id,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "priority": a.priority,
                "status": a.status,
            }
            for a in action_items
        ],
    }


@router.get("/meetings/{meeting_id}/actions", summary="Meeting action items")
async def get_meeting_actions(meeting_id: str, request: Request):
    """Action items for a meeting with completion status."""
    from db.models import ActionItem

    action_items = await ActionItem.find(
        ActionItem.meeting_id == meeting_id,
    ).sort(-ActionItem.created_at).to_list()

    return {
        "actions": [
            {
                "action_item_id": a.action_item_id,
                "description": a.description,
                "owner_id": a.owner_id,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "priority": a.priority,
                "status": a.status,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "reminder_count": a.reminder_count,
                "linked_workflow_id": a.linked_workflow_id,
            }
            for a in action_items
        ],
        "count": len(action_items),
    }
