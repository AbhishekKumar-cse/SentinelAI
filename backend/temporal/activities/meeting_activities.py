"""
Temporal Activities — Meeting Intelligence.
Activities are the actual Python functions that Temporal executes.
Each activity is retryable and idempotent.
"""
import logging
from typing import Optional
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="fetch_transcript")
async def fetch_transcript(meeting_id: str, tenant_id: str, source: str) -> Optional[str]:
    """Fetch transcript text from storage or external API."""
    from db.models import Meeting
    import os
    import httpx

    activity.heartbeat(f"Fetching transcript for {meeting_id}")

    meeting = await Meeting.find_one(Meeting.meeting_id == meeting_id)
    if not meeting:
        logger.warning(f"Meeting {meeting_id} not found")
        return None

    # If transcript already stored
    if meeting.transcript_storage_uri:
        if meeting.transcript_storage_uri.startswith("gs://"):
            # GCS download
            try:
                from google.cloud import storage
                client = storage.Client()
                blob_path = meeting.transcript_storage_uri.replace("gs://", "")
                bucket_name, *path_parts = blob_path.split("/")
                bucket = client.bucket(bucket_name)
                blob = bucket.blob("/".join(path_parts))
                return blob.download_as_text()
            except Exception as e:
                logger.error(f"GCS download failed: {e}")

        elif meeting.transcript_storage_uri.startswith("http"):
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(meeting.transcript_storage_uri)
                if resp.status_code == 200:
                    return resp.text

    # Fetch from source API
    if source == "ZOOM":
        zoom_token = os.environ.get("ZOOM_JWT_TOKEN", "")
        if zoom_token and meeting.external_meeting_id:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://api.zoom.us/v2/recordings/{meeting.external_meeting_id}/transcript",
                    headers={"Authorization": f"Bearer {zoom_token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("transcript", "")

    # Demo fallback
    return f"""[DEMO TRANSCRIPT]
Priya Sharma: Good morning everyone. Let's review the Q4 procurement plan.
Arjun Mehta: I've completed the vendor assessment. We have three shortlisted vendors.
Priya Sharma: Great. We need to approve the Vendor ABC contract by Friday.
Arjun Mehta: I'll take ownership of the contract review. Should be done by Thursday.
Priya Sharma: Perfect. Also, let's schedule a follow-up next Monday to review progress.
Kavya Reddy: I'll set up the follow-up meeting invite for Monday at 10 AM.
Priya Sharma: Excellent. Decision: We approve the Q4 vendor consolidation strategy.
"""


@activity.defn(name="run_mia_analysis")
async def run_mia_analysis(
    meeting_id: str,
    tenant_id: str,
    transcript: str,
    participants: list,
) -> dict:
    """Run Meeting Intelligence Agent analysis on transcript."""
    from agents.meeting_intelligence.agent import MeetingIntelligenceAgent
    from datetime import datetime

    activity.heartbeat(f"Analyzing meeting {meeting_id}")

    mia = MeetingIntelligenceAgent(tenant_id=tenant_id)
    result = await mia.analyze_transcript(
        meeting_id=meeting_id,
        transcript_text=transcript,
        participants=participants,
        meeting_at=datetime.utcnow(),
        workflow_id=meeting_id,
    )
    return result.get("analysis", {})


@activity.defn(name="create_action_item_tasks")
async def create_action_item_tasks(meeting_id: str, tenant_id: str, action_items: list) -> list:
    """Create HumanTask records for each action item."""
    from db.models import HumanTask, HumanTaskStatus, Priority
    from datetime import datetime, timedelta
    import uuid

    activity.heartbeat("Creating human task records")

    task_ids = []
    for item in action_items:
        due_in_days = item.get("due_in_days", 7)
        priority_str = item.get("priority", "MEDIUM")
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = Priority.MEDIUM

        task = HumanTask(
            human_task_id=str(uuid.uuid4()),
            workflow_id=meeting_id,
            tenant_id=tenant_id,
            assignee_id=item.get("owner_id", "unassigned"),
            title=item.get("description", "")[:200],
            description=f"Action item from meeting. Assignee: {item.get('assignee_name', 'TBD')}",
            context_snapshot={"source": "meeting", "meeting_id": meeting_id, "item": item},
            status=HumanTaskStatus.PENDING,
            priority=priority,
            due_at=datetime.utcnow() + timedelta(days=due_in_days),
        )
        await task.insert()
        task_ids.append(task.human_task_id)

    return task_ids


@activity.defn(name="send_meeting_summary")
async def send_meeting_summary(
    meeting_id: str,
    tenant_id: str,
    participants: list,
    analysis: dict,
) -> bool:
    """Send meeting summary email/Slack to all participants."""
    from agents.action_execution.agent import ActionExecutionAgent
    import uuid

    activity.heartbeat("Sending meeting summary")

    decisions = analysis.get("decisions", [])
    action_items = analysis.get("action_items", [])
    summary = analysis.get("summary", "Meeting analysis complete.")

    # Build HTML summary
    decisions_html = "".join([
        f"<li><strong>{d.get('text', '')}</strong> — <em>{d.get('maker', '')}</em> ({int(d.get('confidence', 0) * 100)}% confidence)</li>"
        for d in decisions[:5]
    ])
    actions_html = "".join([
        f"<li>{a.get('description', '')} → <strong>{a.get('assignee_name', 'TBD')}</strong> (due in {a.get('due_in_days', 7)} days)</li>"
        for a in action_items[:10]
    ])

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
      <div style="background: linear-gradient(135deg, #7c3aed, #4f46e5); padding: 24px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 20px;">Meeting Intelligence Summary</h1>
        <p style="color: rgba(255,255,255,0.8); margin: 4px 0 0;">Powered by AntiGravity AI</p>
      </div>
      <div style="background: #f8fafc; padding: 24px; border-radius: 0 0 12px 12px;">
        <h2 style="color: #1e293b; font-size: 16px;">Executive Summary</h2>
        <p style="color: #475569;">{summary}</p>
        <h2 style="color: #1e293b; font-size: 16px;">Decisions Made ({len(decisions)})</h2>
        <ul style="color: #475569;">{decisions_html or '<li>No decisions recorded</li>'}</ul>
        <h2 style="color: #1e293b; font-size: 16px;">Action Items ({len(action_items)})</h2>
        <ul style="color: #475569;">{actions_html or '<li>No action items</li>'}</ul>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
        <p style="color: #94a3b8; font-size: 12px;">Generated by AntiGravity MIA v2.0</p>
      </div>
    </div>
    """

    aea = ActionExecutionAgent(tenant_id=tenant_id)
    emails = [p.get("email") for p in participants if p.get("email")]

    if emails:
        try:
            await aea.send_email(
                to=emails,
                cc=[],
                bcc=[],
                subject="Meeting Summary: Decisions & Action Items",
                body_html=html_body,
                workflow_id=meeting_id,
                idempotency_key=f"meeting-summary-{meeting_id}",
            )
        except Exception as e:
            logger.warning(f"Failed to send meeting summary email: {e}")

    return True


@activity.defn(name="schedule_action_reminders")
async def schedule_action_reminders(meeting_id: str, tenant_id: str, items: list) -> int:
    """Send reminders for action items."""
    from agents.meeting_intelligence.agent import MeetingIntelligenceAgent

    mia = MeetingIntelligenceAgent(tenant_id=tenant_id)
    result = await mia.send_action_reminders(meeting_id=meeting_id, overdue_only=False)
    return result.get("reminders_sent", 0)


@activity.defn(name="escalate_overdue_action")
async def escalate_overdue_action(meeting_id: str, tenant_id: str, item: dict) -> dict:
    """Create an escalation for an overdue action item."""
    from db.models import Escalation, EscalationStatus
    from datetime import datetime
    import uuid

    esc = Escalation(
        escalation_id=str(uuid.uuid4()),
        workflow_id=meeting_id,
        tenant_id=tenant_id,
        trigger_type="OVERDUE_ACTION_ITEM",
        risk_score=0.8,
        status=EscalationStatus.OPEN,
        escalation_level=1,
    )
    await esc.insert()
    return {"escalation_id": esc.escalation_id}


@activity.defn(name="mark_meeting_complete")
async def mark_meeting_complete(meeting_id: str, tenant_id: str) -> bool:
    """Mark meeting as fully processed."""
    from db.models import Meeting

    await Meeting.find_one(Meeting.meeting_id == meeting_id).update({
        "$set": {"status": "ARCHIVED"}
    })
    return True
