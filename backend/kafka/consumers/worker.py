"""
Kafka Consumer Workers — one consumer group per topic.
Uses confluent-kafka async consumer with manual commit for at-least-once delivery.
Each message is dispatched to the appropriate handler coroutine.
Run: python -m kafka.consumers.worker
"""
import asyncio
import json
import logging
import os
import signal
from datetime import datetime
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class KafkaConsumerWorker:
    """
    Async Kafka consumer that dispatches events to handler functions.
    Implements graceful shutdown on SIGTERM/SIGINT.
    """

    def __init__(
        self,
        group_id: str,
        topics: list[str],
        handler: Callable[[dict], Awaitable[None]],
    ):
        self.group_id = group_id
        self.topics = topics
        self.handler = handler
        self._running = False
        self._consumer = None

    def _build_config(self) -> dict:
        conf = {
            "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            "group.id": self.group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 30000,
        }

        # Confluent Cloud SASL config
        if os.environ.get("KAFKA_SASL_USERNAME"):
            conf.update({
                "security.protocol": "SASL_SSL",
                "sasl.mechanisms": "PLAIN",
                "sasl.username": os.environ.get("KAFKA_SASL_USERNAME", ""),
                "sasl.password": os.environ.get("KAFKA_SASL_PASSWORD", ""),
            })

        return conf

    async def start(self):
        """Start the consumer loop."""
        from confluent_kafka import Consumer, KafkaException

        self._running = True
        config = self._build_config()

        self._consumer = Consumer(config)
        self._consumer.subscribe(self.topics)

        logger.info(f"Consumer {self.group_id} started, subscribed to: {self.topics}")

        loop = asyncio.get_event_loop()

        def _handle_shutdown(signum, frame):
            logger.info(f"Consumer {self.group_id} shutting down...")
            self._running = False

        signal.signal(signal.SIGTERM, _handle_shutdown)
        signal.signal(signal.SIGINT, _handle_shutdown)

        try:
            while self._running:
                # Poll in executor to avoid blocking the event loop
                msg = await loop.run_in_executor(
                    None,
                    lambda: self._consumer.poll(timeout=1.0),
                )

                if msg is None:
                    continue

                if msg.error():
                    from confluent_kafka import KafkaError
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error(f"Consumer error: {msg.error()}")
                    continue

                # Decode CloudEvent
                try:
                    raw = json.loads(msg.value().decode("utf-8"))
                    # Handle both plain dict and CloudEvent envelope
                    if "data" in raw and "type" in raw:
                        event_type = raw.get("type", "")
                        event_data = raw.get("data", raw)
                        event_data["_event_type"] = event_type
                        event_data["_topic"] = msg.topic()
                        event_data["_partition"] = msg.partition()
                        event_data["_offset"] = msg.offset()
                    else:
                        event_data = raw

                    await self.handler(event_data)
                    self._consumer.commit(msg)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                    self._consumer.commit(msg)  # Commit bad messages to avoid poison pill
                except Exception as e:
                    logger.error(f"Handler error: {e}", exc_info=True)
                    # Don't commit — will retry on restart

        finally:
            self._consumer.close()
            logger.info(f"Consumer {self.group_id} stopped")

    def stop(self):
        self._running = False


# ─── Event Handlers ───────────────────────────────────────────────────────────

async def handle_workflow_event(event: dict):
    """Handle events on the workflow.events topic."""
    event_type = event.get("_event_type", event.get("event_type", ""))
    workflow_id = event.get("workflow_id", "")
    tenant_id = event.get("tenant_id", "")

    logger.info(f"workflow.events: {event_type} workflow={workflow_id}")

    if event_type == "WorkflowLaunched":
        # Trigger SLA monitor child workflow
        from temporal.worker import TEMPORAL_HOST, TEMPORAL_NAMESPACE
        from temporalio.client import Client

        try:
            client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
            await client.start_workflow(
                "SLAMonitorWorkflow",
                args=[{"workflow_id": workflow_id, "tenant_id": tenant_id}],
                id=f"sla-{workflow_id}",
                task_queue="antigravity-workers",
            )
            logger.info(f"SLA monitor started for {workflow_id}")
        except Exception as e:
            logger.warning(f"Failed to start SLA monitor: {e}")

    elif event_type == "ActionItemWorkflowRequired":
        logger.info(f"Action item workflow required: {event.get('action_item_id')}")


async def handle_meeting_event(event: dict):
    """Handle meeting.events — trigger MIA workflow on ingestion."""
    event_type = event.get("_event_type", event.get("event_type", ""))
    meeting_id = event.get("meeting_id", "")
    tenant_id = event.get("tenant_id", "")

    logger.info(f"meetings.events: {event_type} meeting={meeting_id}")

    if event_type == "MeetingIngested":
        # Launch MeetingIntelligenceWorkflow via Temporal
        from temporalio.client import Client

        temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
        try:
            client = await Client.connect(temporal_host)
            await client.start_workflow(
                "MeetingIntelligenceWorkflow",
                args=[{
                    "meeting_id": meeting_id,
                    "tenant_id": tenant_id,
                    "participants": event.get("participants", []),
                    "source": event.get("source", "MANUAL"),
                }],
                id=f"mia-{meeting_id}",
                task_queue="antigravity-workers",
            )
            logger.info(f"MIA workflow launched for meeting {meeting_id}")
        except Exception as e:
            logger.warning(f"Failed to launch MIA workflow: {e}")


async def handle_human_task_event(event: dict):
    """Handle human.tasks — route to appropriate assignee, send notifications."""
    event_type = event.get("_event_type", event.get("event_type", ""))
    logger.info(f"human.tasks: {event_type}")

    if event_type == "HumanTaskCompleted":
        # Signal the parent Temporal workflow
        human_task_id = event.get("human_task_id", "")
        workflow_id = event.get("workflow_id", "")
        resolution = event.get("resolution", {})

        from temporalio.client import Client
        temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
        try:
            client = await Client.connect(temporal_host)
            handle = client.get_workflow_handle(f"escalation-{workflow_id}")
            await handle.signal("task_completed", resolution)
            logger.info(f"Signaled workflow {workflow_id} task completion")
        except Exception as e:
            logger.warning(f"Failed to signal workflow: {e}")


async def handle_audit_event(event: dict):
    """Handle audit.stream — real-time compliance monitoring."""
    event_type = event.get("event_type", "")
    workflow_id = event.get("workflow_id", "")

    # Detect compliance-critical events
    critical_events = {"PAYMENT_EXECUTED", "PO_CREATED", "APPROVAL_OVERRIDDEN", "DATA_BREACH_DETECTED"}
    if event_type in critical_events:
        logger.warning(f"COMPLIANCE: {event_type} in workflow {workflow_id}")
        # TODO: Forward to compliance SIEM


async def handle_escalation_event(event: dict):
    """Handle escalations — trigger HumanEscalationWorkflow."""
    event_type = event.get("_event_type", event.get("event_type", ""))
    escalation_id = event.get("escalation_id", "")
    workflow_id = event.get("workflow_id", "")
    tenant_id = event.get("tenant_id", "")

    logger.info(f"escalations: {event_type} escalation={escalation_id}")

    if event_type in ("EscalationTriggered", "VerificationFailed", "AgentFailure"):
        from temporalio.client import Client
        temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")

        try:
            client = await Client.connect(temporal_host)
            await client.start_workflow(
                "HumanEscalationWorkflow",
                args=[{
                    "workflow_id": workflow_id,
                    "tenant_id": tenant_id,
                    "escalation_id": escalation_id,
                    "task_config": {
                        "title": f"⚠️ Escalation: {event_type}",
                        "description": f"Workflow {workflow_id} requires immediate attention.",
                        "priority": "CRITICAL",
                        "due_hours": 2,
                    },
                }],
                id=f"escalation-{workflow_id}-{escalation_id}",
                task_queue="antigravity-workers",
            )
        except Exception as e:
            logger.warning(f"Failed to start escalation workflow: {e}")


async def run_all_consumers():
    """Start all topic consumers in parallel."""
    # Initialize MongoDB
    from db.mongodb import init_mongodb
    os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0")
    await init_mongodb()

    consumers = [
        KafkaConsumerWorker("ag-workflow-consumer", ["workflow.events"], handle_workflow_event),
        KafkaConsumerWorker("ag-meeting-consumer", ["meetings.events"], handle_meeting_event),
        KafkaConsumerWorker("ag-human-task-consumer", ["human.tasks"], handle_human_task_event),
        KafkaConsumerWorker("ag-audit-consumer", ["audit.stream"], handle_audit_event),
        KafkaConsumerWorker("ag-escalation-consumer", ["escalations", "agent.actions"], handle_escalation_event),
    ]

    logger.info(f"Starting {len(consumers)} Kafka consumers")
    await asyncio.gather(*[c.start() for c in consumers])


if __name__ == "__main__":
    asyncio.run(run_all_consumers())
