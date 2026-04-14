"""Neo4j 클라이언트 — 드라이버 래퍼 + Cypher 쿼리 실행"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import GraphDatabase, ManagedTransaction

from comad_eye.cache import graph_counts_cache, graph_stats_cache
from comad_eye.config import Neo4jSettings, load_settings

logger = logging.getLogger("comadeye")

# Allowlist for dynamic property names to prevent Cypher injection
_SAFE_PROPERTY_NAMES = frozenset({
    # Entity core properties
    "stance", "volatility", "influence_score", "community_id",
    "description", "name", "object_type", "magnitude",
    "action_bias", "resilience", "adaptability",
    # Simulation engine properties
    "is_active", "activity_level", "susceptibility",
    # Propagation properties (from propagation_rules.yaml)
    "event_activation",
    # Community / summary properties
    "community_summary",
})


def _validate_property_name(prop: str) -> str:
    """Validate that a property name is safe for Cypher interpolation."""
    if prop not in _SAFE_PROPERTY_NAMES:
        raise ValueError(f"Unsafe property name for Cypher query: '{prop}'")
    return prop


class Neo4jClient:
    """Neo4j 그래프 데이터베이스 클라이언트."""

    def __init__(self, settings: Neo4jSettings | None = None):
        self._settings = settings or load_settings().neo4j
        self._driver = GraphDatabase.driver(
            self._settings.uri,
            auth=(self._settings.user, self._settings.password),
        )
        self._database = self._settings.database

    def close(self) -> None:
        self._driver.close()

    def verify_connectivity(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Neo4j 연결 실패: {e}")
            return False

    def query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """읽기 전용 Cypher 쿼리를 실행한다."""
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def write(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """쓰기 Cypher 쿼리를 실행한다."""
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def write_tx(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """트랜잭션 내에서 쓰기 Cypher를 실행한다."""
        with self._driver.session(database=self._database) as session:
            def _tx_fn(tx: ManagedTransaction) -> list[dict[str, Any]]:
                result = tx.run(cypher, **params)
                return [dict(record) for record in result]
            return session.execute_write(_tx_fn)

    def setup_schema(self) -> None:
        """인덱스와 제약 조건을 생성한다."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.uid IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.object_type)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.community_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.influence_score)",
        ]
        for stmt in constraints + indexes:
            try:
                self.write(stmt)
            except Exception as e:
                logger.warning(f"스키마 생성 경고: {e}")
        self.invalidate_cache()

    def clear_all(self) -> None:
        """모든 노드와 관계를 삭제한다."""
        self.write("MATCH (n) DETACH DELETE n")
        self.invalidate_cache()

    def invalidate_cache(self) -> None:
        """캐시된 그래프 데이터를 모두 무효화한다."""
        graph_stats_cache.clear()
        graph_counts_cache.clear()

    def node_count(self) -> int:
        from comad_eye.cache import _SENTINEL
        cache_key = "node_count"
        cached = graph_counts_cache.get_or_sentinel(cache_key)
        if cached is not _SENTINEL:
            return cached
        result = self.query("MATCH (n:Entity) RETURN count(n) AS cnt")
        count = result[0]["cnt"] if result else 0
        graph_counts_cache.set(cache_key, count)
        return count

    def edge_count(self, active_only: bool = True) -> int:
        cache_key = f"edge_count:{active_only}"
        from comad_eye.cache import _SENTINEL
        cached = graph_counts_cache.get_or_sentinel(cache_key)
        if cached is not _SENTINEL:
            return cached
        if active_only:
            result = self.query(
                "MATCH ()-[r]->() WHERE r.expired_at IS NULL RETURN count(r) AS cnt"
            )
        else:
            result = self.query("MATCH ()-[r]->() RETURN count(r) AS cnt")
        count = result[0]["cnt"] if result else 0
        graph_counts_cache.set(cache_key, count)
        return count

    def get_entity(self, uid: str) -> dict[str, Any] | None:
        result = self.query(
            "MATCH (n:Entity {uid: $uid}) RETURN properties(n) AS props",
            uid=uid,
        )
        return result[0]["props"] if result else None

    def get_all_entities(self) -> list[dict[str, Any]]:
        return self.query(
            "MATCH (n:Entity) RETURN properties(n) AS props ORDER BY n.influence_score DESC"
        )

    def get_neighbors(
        self, uid: str, active_only: bool = True
    ) -> list[dict[str, Any]]:
        where_clause = "AND r.expired_at IS NULL" if active_only else ""
        return self.query(
            f"MATCH (n:Entity {{uid: $uid}})-[r]->(m:Entity) "
            f"WHERE true {where_clause} "
            f"RETURN m.uid AS uid, type(r) AS rel_type, r.weight AS weight, "
            f"properties(m) AS props",
            uid=uid,
        )

    def update_entity_property(
        self, uid: str, prop: str, value: Any
    ) -> None:
        safe_prop = _validate_property_name(prop)
        self.write(
            f"MATCH (n:Entity {{uid: $uid}}) SET n.{safe_prop} = $value",
            uid=uid,
            value=value,
        )

    def get_graph_stats(self) -> dict[str, Any]:
        """그래프 통계를 반환한다 (TTL 60 s 캐시)."""
        from comad_eye.cache import _SENTINEL
        cache_key = "graph_stats"
        cached = graph_stats_cache.get_or_sentinel(cache_key)
        if cached is not _SENTINEL:
            return cached

        stats: dict[str, Any] = {}
        stats["node_count"] = self.node_count()
        stats["edge_count"] = self.edge_count()

        # 관계 유형 분포
        rel_dist = self.query(
            "MATCH ()-[r]->() WHERE r.expired_at IS NULL "
            "RETURN type(r) AS rel_type, count(r) AS cnt "
            "ORDER BY cnt DESC"
        )
        stats["relationship_distribution"] = {
            r["rel_type"]: r["cnt"] for r in rel_dist
        }

        # 평균 속성
        avg = self.query(
            "MATCH (n:Entity) RETURN "
            "avg(n.volatility) AS avg_vol, "
            "avg(n.stance) AS avg_stance, "
            "avg(n.influence_score) AS avg_influence"
        )
        if avg:
            stats["avg_volatility"] = avg[0].get("avg_vol", 0)
            stats["avg_stance"] = avg[0].get("avg_stance", 0)
            stats["avg_influence"] = avg[0].get("avg_influence", 0)

        graph_stats_cache.set(cache_key, stats)
        return stats
