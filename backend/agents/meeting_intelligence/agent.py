"""
Meeting Intelligence Agent (MIA) — Turns meeting recordings into structured wisdom.
Processes Zoom/Teams/Google Meet transcripts via LLM pipeline.
Extracts: decisions, action items, sentiment, blockers, follow-ups.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

MIA_SYSTEM_PROMPT = """You are a Meeting Intelligence Agent. You process meeting transcripts and extract structured, actionable intelligence.

For every transcript you analyze, extract:
1. DECISIONS: Every decision made, with the decision-maker's name, confidence level, and any dissenting views
2. ACTION ITEMS: Every commitment made, with assignee, due date (or relative duration), priority
3. BLOCKERS: Everything blocking progress
4. SENTIMENT: Participant sentiment over time (positive/negative/neutral)
5. KEY DISCUSSIONS: Major topics covered with context
6. FOLLOW-UP MEETINGS: Any agreed follow-up with attendees and dates

Format all output as structured JSON. For dates, if no specific date is given, use context clues (e.g., "by end of day" = today, "next week" = 7 days) and flag them as ESTIMATED."""


class MeetingIntelligenceAgent(BaseAgent):
    family = "MIA"

    def get_system_prompt(self) -> str:
        return MIA_SYSTEM_PROMPT

    async def analyze_transcript(
        self,
        meeting_id: str,
        transcript_text: str,
        participants: list[dict],
        meeting_at: Optional[datetime] = None,
        workflow_id: Optional[str] = None,
    ) -> dict:
        """
        Full meeting intelligence extraction pipeline.
        Returns structured intelligence including decisions, actions, sentiment.
        """
        from db.models import Meeting, ActionItem, Priority

        llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0, max_tokens=8192)

        participant_names = [p.get("name", p.get("uid", "Unknown")) for p in participants]

        prompt = f"""Analyze this meeting transcript and extract structured intelligence.
Meeting participants: {", ".join(participant_names)}
Meeting date: {(meeting_at or datetime.utcnow()).strftime("%Y-%m-%d")}

TRANSCRIPT:
{transcript_text[:8000]}

Return your analysis as valid JSON with this exact structure:
{{
  "summary": "2-3 sentence executive summary",
  "key_topics": ["list of main topics covered"],
  "decisions": [
    {{
      "text": "the decision made",
      "maker": "person who made it",
      "confidence": 0.9,
      "context": "brief context",
      "dissenting_views": []
    }}
  ],
  "action_items": [
    {{
      "description": "what needs to be done",
      "assignee_name": "person responsible",
      "due_in_days": 7,
      "priority": "HIGH|MEDIUM|LOW",
      "is_recurring": false
    }}
  ],
  "blockers": ["list of blockers mentioned"],
  "sentiment_timeline": [
    {{
      "timestamp": "approximate time in meeting",
      "participant": "name",
      "sentiment": "positive|negative|neutral",
      "score": 0.8
    }}
  ],
  "follow_up_meetings": [
    {{
      "title": "meeting title",
      "attendees": ["names"],
      "suggested_date": "description",
      "duration_minutes": 30
    }}
  ]
}}"""

        import json as json_module
        import re

        try:
            response = await llm.ainvoke([
                SystemMessage(content=self.get_system_prompt()),
                HumanMessage(content=prompt),
            ])

            content = response.content

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                intelligence = json_module.loads(json_match.group())
            else:
                raise ValueError("No JSON found in LLM response")

        except Exception as e:
            logger.error(f"MIA analysis failed: {e}")
            # Fallback structure
            intelligence = {
                "summary": "Meeting analysis failed. Manual review required.",
                "key_topics": [],
                "decisions": [],
                "action_items": [],
                "blockers": [],
                "sentiment_timeline": [],
                "follow_up_meetings": [],
                "_error": str(e),
            }

        # Compute overall sentiment
        sentiments = intelligence.get("sentiment_timeline", [])
        avg_sentiment = (
            sum(s.get("score", 0.5) for s in sentiments) / max(len(sentiments), 1)
            if sentiments else 0.5
        )
        intelligence["overall_sentiment_score"] = avg_sentiment

        # Update Meeting document
        await Meeting.find_one(Meeting.meeting_id == meeting_id).update({
            "$set": {
                "status": "ANALYZED" if "_error" not in intelligence else "ANALYSIS_FAILED",
                "summary_doc": intelligence,
                "sentiment_timeline": intelligence.get("sentiment_timeline", []),
            }
        })

        # Create ActionItem documents for each extracted action
        action_items = []
        meeting_date = meeting_at or datetime.utcnow()

        for action_data in intelligence.get("action_items", []):
            # Match assignee to user if possible
            assignee_uid = self._match_participant(
                action_data.get("assignee_name", ""),
                participants,
            )
            due_at = meeting_date + timedelta(days=action_data.get("due_in_days", 7))

            priority_str = action_data.get("priority", "MEDIUM")
            try:
                priority = Priority(priority_str)
            except ValueError:
                priority = Priority.MEDIUM

            action_item = ActionItem(
                action_item_id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                tenant_id=self.tenant_id,
                description=action_data.get("description", ""),
                assignee_name=action_data.get("assignee_name", ""),
                owner_id=assignee_uid,
                due_at=due_at,
                priority=priority,
                status="OPEN",
            )
            action_items.append(action_item)

        if action_items:
            await ActionItem.insert_many(action_items)

        await self.write_audit_record(
            event_type="MEETING_ANALYZED",
            payload={
                "meeting_id": meeting_id,
                "decisions_count": len(intelligence.get("decisions", [])),
                "action_items_count": len(action_items),
                "sentiment_score": avg_sentiment,
            },
            workflow_id=workflow_id or meeting_id,
        )

        await self.emit_kafka_event(
            topic="meetings.events",
            event_type="MeetingAnalyzed",
            data={
                "meeting_id": meeting_id,
                "action_items_count": len(action_items),
                "decisions_count": len(intelligence.get("decisions", [])),
            },
            workflow_id=workflow_id,
        )

        # Auto-create follow-up workflows for critical action items
        critical_actions = [a for a in action_items if a.priority == Priority.CRITICAL]
        if critical_actions:
            await self._create_followup_workflows(critical_actions, meeting_id)

        return {
            "meeting_id": meeting_id,
            "analysis": intelligence,
            "action_items_created": len(action_items),
            "critical_actions": len(critical_actions),
        }

    def _match_participant(self, name: str, participants: list[dict]) -> Optional[str]:
        """Fuzzy match a name string to a participant uid."""
        if not name:
            return None
        name_lower = name.lower()
        for p in participants:
            p_name = p.get("name", "").lower()
            if name_lower in p_name or p_name in name_lower:
                return p.get("uid")
        return None

    async def _create_followup_workflows(self, actions: list, meeting_id: str):
        """Create Temporal workflow tasks for critical action items."""
        from kafka.producer import publish

        for action in actions:
            await publish(
                topic="workflow.events",
                event_type="ActionItemWorkflowRequired",
                data={
                    "action_item_id": action.action_item_id,
                    "description": action.description,
                    "due_at": action.due_at.isoformat(),
                    "meeting_id": meeting_id,
                },
                tenant_id=self.tenant_id,
            )

    async def send_action_reminders(
        self,
        meeting_id: str,
        overdue_only: bool = False,
    ) -> dict:
        """
        Send reminder notifications for open action items.
        Called by the Temporal cron scheduler.
        """
        from db.models import ActionItem
        from agents.action_execution.agent import ActionExecutionAgent

        filters = [
            ActionItem.meeting_id == meeting_id,
            ActionItem.status == "OPEN",
        ]
        if overdue_only:
            filters.append(ActionItem.due_at <= datetime.utcnow())

        action_items = await ActionItem.find(*filters).to_list()

        aea = ActionExecutionAgent(tenant_id=self.tenant_id)
        reminders_sent = 0

        for item in action_items:
            if item.owner_id:
                try:
                    await aea.send_email(
                        to=[item.owner_id],
                        cc=[],
                        bcc=[],
                        subject=f"Action Item Reminder: {item.description[:80]}",
                        body_html=f"""
                        <h2>Action Item Reminder</h2>
                        <p><strong>{item.description}</strong></p>
                        <p>Due: {item.due_at.strftime('%Y-%m-%d') if item.due_at else 'No due date'}</p>
                        <p>Priority: {item.priority}</p>
                        """,
                        workflow_id=meeting_id,
                    )
                    await item.set({ActionItem.reminder_count: (item.reminder_count or 0) + 1})
                    reminders_sent += 1
                except Exception as e:
                    logger.warning(f"Reminder failed for action {item.action_item_id}: {e}")

        return {
            "reminders_sent": reminders_sent,
            "total_open_actions": len(action_items),
        }

    async def execute_task(
        self,
        task_id: str,
        workflow_id: str,
        task_definition: dict[Any, Any],
        context: dict[Any, Any],
    ) -> dict[Any, Any]:
        """MIA task execution entry point."""
        action = task_definition.get("action", "analyze")

        if action == "analyze":
            return await self.analyze_transcript(
                meeting_id=task_definition.get("meeting_id", task_id),
                transcript_text=task_definition.get("transcript_text", ""),
                participants=task_definition.get("participants", []),
                meeting_at=context.get("meeting_at"),
                workflow_id=workflow_id,
            )
        elif action == "send_reminders":
            return await self.send_action_reminders(
                meeting_id=task_definition.get("meeting_id", ""),
                overdue_only=task_definition.get("overdue_only", False),
            )
        else:
            return {"action": action, "status": "completed"}
