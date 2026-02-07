"""
Neo4j Knowledge Graph Client
Singleton driver for the Neo4j graph database used by the agent system.
Provides read/write query helpers with automatic session management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.config import config

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thread-safe singleton wrapper around the Neo4j Python driver."""

    _instance: Optional[Neo4jClient] = None

    def __init__(self) -> None:
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        )
        logger.info("Neo4j driver initialised (%s)", config.NEO4J_URI)

    # ── Query helpers ─────────────────────────────────────────────

    def execute_write(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            return session.execute_write(
                lambda tx: tx.run(query, params or {}).data()
            )

    def execute_read(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            return session.execute_read(
                lambda tx: tx.run(query, params or {}).data()
            )

    # ── Lifecycle ─────────────────────────────────────────────────

    def verify_connectivity(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning("Neo4j connectivity check failed: %s", exc)
            return False

    def close(self) -> None:
        self.driver.close()
        logger.info("Neo4j driver closed")


def get_neo4j_client() -> Neo4jClient:
    """Return (or create) the singleton Neo4jClient."""
    if Neo4jClient._instance is None:
        Neo4jClient._instance = Neo4jClient()
    return Neo4jClient._instance
