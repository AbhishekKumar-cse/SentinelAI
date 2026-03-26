"""
Kafka producer singleton with CloudEvents envelope.
Supports Confluent Cloud (SASL_SSL) and local dev (PLAINTEXT).
All messages include standard CloudEvents 1.0 envelope.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)

# ─── Kafka Topics ─────────────────────────────────────────────────────────────
TOPICS = {
    "workflow.events": "Workflow lifecycle events",
    "workflow.tasks": "Task assignment and status changes",
    "agent.decisions": "DMA decision events",
    "agent.actions": "AEA action execution events",
    "agent.heartbeats": "Agent liveness heartbeats",
    "human.tasks": "Human task assignments",
    "meetings.events": "Meeting processing events",
    "audit.stream": "Audit record stream",
    "escalations": "Escalation triggers",
    "notifications": "Outbound notification requests",
}

_producer: Optional[Producer] = None


def _get_kafka_config() -> dict:
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    security_protocol = os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    sasl_username = os.environ.get("KAFKA_SASL_USERNAME", "")
    sasl_password = os.environ.get("KAFKA_SASL_PASSWORD", "")

    config = {
        "bootstrap.servers": bootstrap_servers,
        "security.protocol": security_protocol,
        "acks": "all",
        "retries": 5,
        "retry.backoff.ms": 500,
        "enable.idempotence": True,
        "delivery.timeout.ms": 30000,
    }

    if security_protocol in {"SASL_SSL", "SASL_PLAINTEXT"} and sasl_username:
        config.update({
            "sasl.mechanisms": os.environ.get("KAFKA_SASL_MECHANISM", "PLAIN"),
            "sasl.username": sasl_username,
            "sasl.password": sasl_password,
        })

    return config


def get_producer() -> Producer:
    """Return the Kafka producer singleton."""
    global _producer
    if _producer is None:
        _producer = Producer(_get_kafka_config())
        logger.info("Kafka producer initialized")
    return _producer


def _delivery_callback(err, msg):
    """Kafka delivery callback for monitoring."""
    if err:
        logger.error(f"Kafka delivery failed: {err}: {msg.topic()}")
    else:
        logger.debug(f"Kafka message delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")


def _build_cloud_event(
    event_type: str,
    source: str,
    data: dict,
    tenant_id: str,
    workflow_id: Optional[str] = None,
) -> dict:
    """Wrap a payload in a CloudEvents 1.0 envelope."""
    return {
        "specversion": "1.0",
        "id": str(uuid.uuid4()),
        "source": f"antigravity/{source}",
        "type": f"ai.antigravity.{event_type}",
        "time": datetime.now(timezone.utc).isoformat(),
        "datacontenttype": "application/json",
        "tenantid": tenant_id,
        "workflowid": workflow_id or "",
        "data": data,
    }


async def publish(
    topic: str,
    event_type: str,
    data: dict[str, Any],
    tenant_id: str,
    workflow_id: Optional[str] = None,
    source: str = "backend",
    key: Optional[str] = None,
) -> None:
    """
    Publish a message to a Kafka topic (async fire-and-forget).
    Wraps the data in a CloudEvents envelope.
    """
    try:
        producer = get_producer()
        event = _build_cloud_event(event_type, source, data, tenant_id, workflow_id)
        message_bytes = json.dumps(event).encode("utf-8")
        message_key = (key or workflow_id or tenant_id).encode("utf-8")

        producer.produce(
            topic=topic,
            key=message_key,
            value=message_bytes,
            callback=_delivery_callback,
        )
        # Non-blocking — don't wait for delivery confirmation
        producer.poll(0)

    except Exception as e:
        logger.error(f"Kafka publish failed for topic {topic}: {e}")
        # Don't raise — Kafka failures should not block business logic


def flush():
    """Flush any pending messages. Call on graceful shutdown."""
    global _producer
    if _producer:
        _producer.flush(timeout=10)
        logger.info("Kafka producer flushed")


async def ensure_topics_exist():
    """Create all required Kafka topics if they don't exist."""
    try:
        config = _get_kafka_config()
        admin_config = {"bootstrap.servers": config["bootstrap.servers"]}
        if "sasl.username" in config:
            admin_config.update({
                "security.protocol": config["security.protocol"],
                "sasl.mechanisms": config.get("sasl.mechanisms", "PLAIN"),
                "sasl.username": config["sasl.username"],
                "sasl.password": config["sasl.password"],
            })

        admin = AdminClient(admin_config)

        # Get existing topics
        metadata = admin.list_topics(timeout=10)
        existing_topics = set(metadata.topics.keys())

        # Create missing topics
        new_topics = []
        for topic_name, description in TOPICS.items():
            if topic_name not in existing_topics:
                new_topics.append(NewTopic(
                    topic_name,
                    num_partitions=3,
                    replication_factor=1,
                    config={"retention.ms": str(7 * 24 * 60 * 60 * 1000)},  # 7 days
                ))

        if new_topics:
            results = admin.create_topics(new_topics)
            for topic, future in results.items():
                try:
                    future.result()
                    logger.info(f"Created Kafka topic: {topic}")
                except Exception as e:
                    logger.warning(f"Topic {topic} creation: {e}")
        else:
            logger.info("All Kafka topics already exist")

    except Exception as e:
        logger.error(f"Failed to ensure Kafka topics: {e}")
        # Don't raise — topics may already exist
