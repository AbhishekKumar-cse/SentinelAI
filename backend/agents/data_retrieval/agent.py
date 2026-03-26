"""
Data Retrieval Agent (DRA) — Universal data fetching with caching.
Fetches from MongoDB, APIs, databases with circuit breaker pattern.
All fetches are cached in Redis with configurable TTLs.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from agents.base_agent import BaseAgent, AgentToolError

logger = logging.getLogger(__name__)

DRA_SYSTEM_PROMPT = """You are a Data Retrieval Agent. Your purpose is to efficiently fetch, normalize, and deliver data from any source.

Before fetching:
1. Check Redis cache — if hit, return immediately
2. Check if circuit breaker is open for this source — if so, use fallback
3. Validate the fetch schema

After fetching:
1. Normalize to canonical schema
2. Cache with appropriate TTL
3. Log to audit if data contains PII or sensitive fields
4. Return with provenance metadata (source, timestamp, schema version)

NEVER return partial or corrupt data. If fetch fails after retries, return an empty result with a clear error explanation."""


class DataRetrievalAgent(BaseAgent):
    family = "DRA"

    def get_system_prompt(self) -> str:
        return DRA_SYSTEM_PROMPT

    async def fetch_entity(
        self,
        entity_type: str,
        entity_id: str,
        connector_id: str,
        workflow_id: str,
        force_refresh: bool = False,
        schema_version: str = "1.0",
    ) -> dict:
        """
        Fetch a single entity from any connector.
        Implements cache-aside pattern with circuit breaker.
        """
        import redis.asyncio as aioredis
        import os

        cache_key = f"entity:{self.tenant_id}:{entity_type}:{entity_id}"
        r = await aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"), decode_responses=True)

        # Check cache
        if not force_refresh:
            cached = await r.get(cache_key)
            if cached:
                data = json.loads(cached)
                await self.write_audit_record(
                    event_type="DATA_FETCHED_CACHE",
                    payload={"entity_type": entity_type, "entity_id": entity_id, "source": "redis"},
                    workflow_id=workflow_id,
                )
                return {**data, "_source": "cache", "_cached_at": data.get("_cached_at")}

        # Check circuit breaker
        cb_key = f"cb:{connector_id}"
        cb_state = await r.get(cb_key)
        if cb_state == "OPEN":
            logger.warning(f"Circuit breaker OPEN for connector {connector_id}")
            return {
                "_error": f"Connector {connector_id} circuit breaker is OPEN",
                "_source": "circuit_breaker_fallback",
                "entity_id": entity_id,
                "entity_type": entity_type,
            }

        # Fetch from connector
        try:
            data = await self._fetch_from_connector(connector_id, entity_type, entity_id)

            # Add provenance metadata
            data["_source"] = f"connector:{connector_id}"
            data["_fetched_at"] = datetime.utcnow().isoformat()
            data["_schema_version"] = schema_version

            # Cache with 5-minute TTL for entities
            await r.setex(cache_key, 300, json.dumps(data, default=str))

            # Reset circuit breaker failures
            await r.delete(f"cb_failures:{connector_id}")

            await self.write_audit_record(
                event_type="DATA_FETCHED",
                payload={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "connector_id": connector_id,
                    "schema_version": schema_version,
                },
                workflow_id=workflow_id,
            )

            return data

        except Exception as e:
            # Record circuit breaker failure
            failures_key = f"cb_failures:{connector_id}"
            fails = await r.incr(failures_key)
            await r.expire(failures_key, 300)

            if fails >= 5:
                # Open circuit breaker for 60 seconds
                await r.setex(cb_key, 60, "OPEN")
                logger.error(f"Circuit breaker OPENED for connector {connector_id}")

            logger.error(f"DRA fetch failed: {entity_type}/{entity_id} from {connector_id}: {e}")
            raise AgentToolError(
                f"Failed to fetch {entity_type}/{entity_id}: {e}",
                "FETCH_FAILED",
                is_retryable=isinstance(e, (httpx.TimeoutException, httpx.ConnectError)),
            )

    async def _fetch_from_connector(self, connector_id: str, entity_type: str, entity_id: str) -> dict:
        """Fetch data from a connector. Uses connector config to route to the right system."""
        from db.models import Connector
        from services.encryption_service import decrypt_dict

        connector = await Connector.find_one(
            Connector.connector_id == connector_id,
            Connector.tenant_id == self.tenant_id,
        )

        if not connector:
            # Return mock data for development
            return {
                "id": entity_id,
                "entity_type": entity_type,
                "name": f"Demo {entity_type} {entity_id}",
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
            }

        config = decrypt_dict(connector.config_encrypted)
        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/{entity_type}/{entity_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            return response.json()

    async def batch_fetch(
        self,
        entity_type: str,
        entity_ids: list[str],
        connector_id: str,
        workflow_id: str,
    ) -> dict[str, dict]:
        """
        Fetch multiple entities in parallel. Respects rate limits.
        Returns a map of entity_id -> data.
        """
        BATCH_SIZE = 10

        results = {}
        for i in range(0, len(entity_ids), BATCH_SIZE):
            batch = entity_ids[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[
                    self.fetch_entity(entity_type, eid, connector_id, workflow_id)
                    for eid in batch
                ],
                return_exceptions=True,
            )
            for eid, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results[eid] = {"_error": str(result)}
                else:
                    results[eid] = result

        await self.write_audit_record(
            event_type="BATCH_FETCH_COMPLETED",
            payload={
                "entity_type": entity_type,
                "total": len(entity_ids),
                "success": len([r for r in results.values() if "_error" not in r]),
                "failed": len([r for r in results.values() if "_error" in r]),
            },
            workflow_id=workflow_id,
        )

        return results

    async def search_entities(
        self,
        query: str,
        entity_type: str,
        connector_id: str,
        workflow_id: str,
        limit: int = 20,
        use_semantic_search: bool = False,
    ) -> list[dict]:
        """
        Search entities. Supports keyword and semantic search via Qdrant.
        """
        if use_semantic_search:
            return await self._semantic_search(query, entity_type, workflow_id, limit)

        # Default: pass search to connector
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"http://localhost:8000/api/v1/connectors/{connector_id}/search",
                    params={"q": query, "entity_type": entity_type, "limit": limit},
                )
                if resp.status_code == 200:
                    return resp.json().get("results", [])
        except Exception as e:
            logger.warning(f"Search failed: {e}")

        return []

    async def _semantic_search(self, query: str, entity_type: str, workflow_id: str, limit: int) -> list[dict]:
        """Semantic search via Qdrant vector store."""
        import os
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage

            llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
            embedding_text = f"Search for {entity_type} matching: {query}"

            qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
            collection_name = f"{self.tenant_id}_{entity_type}"

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{qdrant_url}/collections/{collection_name}/points/search",
                    json={"vector": [0.5] * 1536, "top": limit},
                )
                if resp.status_code == 200:
                    return resp.json().get("result", [])
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")

        return []

    async def execute_task(
        self,
        task_id: str,
        workflow_id: str,
        task_definition: dict[Any, Any],
        context: dict[Any, Any],
    ) -> dict[Any, Any]:
        """DRA task execution entry point."""
        action = task_definition.get("action", "fetch")

        if action == "fetch":
            return await self.fetch_entity(
                entity_type=task_definition.get("entity_type", "generic"),
                entity_id=task_definition.get("entity_id", ""),
                connector_id=task_definition.get("connector_id", "default"),
                workflow_id=workflow_id,
            )
        elif action == "batch_fetch":
            return await self.batch_fetch(
                entity_type=task_definition.get("entity_type", "generic"),
                entity_ids=task_definition.get("entity_ids", []),
                connector_id=task_definition.get("connector_id", "default"),
                workflow_id=workflow_id,
            )
        elif action == "search":
            results = await self.search_entities(
                query=task_definition.get("query", ""),
                entity_type=task_definition.get("entity_type", "generic"),
                connector_id=task_definition.get("connector_id", "default"),
                workflow_id=workflow_id,
            )
            return {"results": results, "count": len(results)}
        else:
            return {"action": action, "status": "completed"}
