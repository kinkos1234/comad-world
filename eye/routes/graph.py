"""Graph routes — entity listing and detail via Neo4j."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from comad_eye.config import load_settings

logger = logging.getLogger("comadeye")

router = APIRouter()


def _get_client():
    from comad_eye.graph.neo4j_client import Neo4jClient
    s = load_settings()
    return Neo4jClient(settings=s.neo4j)


@router.get("/graph/entities")
async def list_entities(limit: int = 200, offset: int = 0):
    """Return entities with core properties (paginated, default top 200 by influence)."""
    limit = min(max(1, limit), 500)
    offset = max(0, offset)
    client = _get_client()
    try:
        rows = client.query(
            "MATCH (n:Entity) "
            "RETURN n.uid AS uid, n.name AS name, n.object_type AS object_type, "
            "n.stance AS stance, n.volatility AS volatility, "
            "n.influence_score AS influence_score, n.community_id AS community_id "
            "ORDER BY n.influence_score DESC "
            "SKIP $offset LIMIT $limit",
            offset=offset, limit=limit,
        ) or []
        return rows
    finally:
        client.close()


@router.get("/graph/relationships")
async def list_relationships():
    """Return all relationships between entities."""
    client = _get_client()
    try:
        rows = client.query(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "RETURN a.uid AS source, b.uid AS target, "
            "type(r) AS rel_type, r.weight AS weight "
            "LIMIT 500"
        ) or []
        return [
            {
                "source": row["source"],
                "target": row["target"],
                "rel_type": row.get("rel_type", ""),
                "weight": float(row.get("weight") or 1.0),
            }
            for row in rows
        ]
    finally:
        client.close()


@router.get("/graph/entity/{uid}")
async def get_entity(uid: str, job_id: str | None = None):
    """Return entity detail with relationships and timeline."""
    client = _get_client()
    try:
        rows = client.query(
            "MATCH (n:Entity {uid: $uid}) "
            "OPTIONAL MATCH (n)-[r]-(m:Entity) "
            "RETURN n.uid AS uid, n.name AS name, n.object_type AS object_type, "
            "n.stance AS stance, n.volatility AS volatility, "
            "n.influence_score AS influence_score, n.community_id AS community_id, "
            "n.description AS description, "
            "collect(DISTINCT {related_uid: m.uid, related_name: m.name, "
            "relation: type(r), weight: r.weight}) AS relationships",
            uid=uid,
        ) or []

        if not rows:
            raise HTTPException(404, f"Entity not found: {uid}")

        entity = rows[0]

        # Timeline from snapshots — use job-scoped directory if available
        import json
        from pathlib import Path
        timeline = []
        snapshot_dir = Path(f"data/jobs/{job_id}/pipeline/snapshots") if job_id else None
        if not snapshot_dir or not snapshot_dir.exists():
            snapshot_dir = Path("data/snapshots")
        if snapshot_dir.exists():
            for snap_file in sorted(snapshot_dir.glob("round_*.json")):
                try:
                    with open(snap_file, encoding="utf-8") as f:
                        snap = json.load(f)
                    for ent in snap.get("entities", []):
                        if ent.get("uid") == uid:
                            timeline.append({
                                "round": snap.get("round", 0),
                                "stance": ent.get("stance", 0),
                                "volatility": ent.get("volatility", 0),
                            })
                            break
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Failed to read snapshot %s: %s", snap_file, e)

        entity["timeline"] = timeline
        return entity
    finally:
        client.close()
