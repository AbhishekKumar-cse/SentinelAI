"""
MongoDB async client initialization using Motor + Beanie ODM.
Supports MongoDB Atlas (production) and local replica set (development).
Change streams require replica set mode even in dev.
"""
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

logger = logging.getLogger(__name__)

# Global client instance
_client: AsyncIOMotorClient | None = None
_db = None


def get_client() -> AsyncIOMotorClient:
    """Return the Motor client singleton."""
    if _client is None:
        raise RuntimeError("MongoDB client not initialized. Call init_mongodb() first.")
    return _client


def get_db():
    """Return the active database."""
    if _db is None:
        raise RuntimeError("MongoDB database not initialized. Call init_mongodb() first.")
    return _db


async def init_mongodb():
    """
    Initialize Motor client and Beanie ODM.
    Called during FastAPI lifespan startup.
    """
    global _client, _db

    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0")
    environment = os.environ.get("ENVIRONMENT", "development")
    db_name = f"antigravity_{environment}"

    logger.info(f"Connecting to MongoDB database: {db_name}")

    _client = AsyncIOMotorClient(
        mongo_uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
        maxPoolSize=50,
        minPoolSize=5,
    )
    _db = _client[db_name]

    # Import here to avoid circular imports
    from db.models import (
        Tenant,
        User,
        ProcessTemplate,
        WorkflowRun,
        WorkflowTask,
        AgentInstance,
        AuditRecord,
        DecisionRecord,
        ActionRecord,
        HumanTask,
        Escalation,
        Meeting,
        ActionItem,
        Connector,
        NotificationLog,
        APIKey,
        SLAConfig,
        VectorNamespace,
        RulesEngine,
        ActionRegistry,
        AgentMemory,
        VerificationRecord,
        PIIToken,
    )

    await init_beanie(
        database=_db,
        document_models=[
            Tenant,
            User,
            ProcessTemplate,
            WorkflowRun,
            WorkflowTask,
            AgentInstance,
            AuditRecord,
            DecisionRecord,
            ActionRecord,
            HumanTask,
            Escalation,
            Meeting,
            ActionItem,
            Connector,
            NotificationLog,
            APIKey,
            SLAConfig,
            VectorNamespace,
            RulesEngine,
            ActionRegistry,
            AgentMemory,
            VerificationRecord,
            PIIToken,
        ],
    )

    logger.info("MongoDB initialized successfully")


async def close_mongodb():
    """Close the Motor client. Called during FastAPI lifespan shutdown."""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")
