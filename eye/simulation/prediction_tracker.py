"""Prediction tracking for closed-loop learning (LeCun improvement).

Records predictions with verification deadlines. Future verification
compares predictions against actual outcomes to update model confidence.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("comadeye")

PREDICTIONS_DIR = Path("data/predictions")


def record_prediction(
    prediction_id: str,
    content: str,
    confidence: float,
    horizon_days: int = 90,
    source_analysis: str = "",
    related_entities: list[str] | None = None,
) -> dict:
    """Record a prediction with verification deadline."""
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "prediction_id": prediction_id,
        "content": content,
        "confidence": confidence,
        "predicted_at": datetime.now().isoformat(),
        "verify_by": (datetime.now() + timedelta(days=horizon_days)).isoformat(),
        "source_analysis": source_analysis,
        "related_entities": related_entities or [],
        "verified": False,
        "outcome": None,
        "accuracy": None,
    }
    path = PREDICTIONS_DIR / f"{prediction_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    logger.info("Prediction recorded: %s (verify by %s)", prediction_id, record["verify_by"])
    return record


def get_pending_verifications() -> list[dict]:
    """Get predictions past their verify_by date that haven't been verified."""
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    pending = []
    now = datetime.now()
    for f in PREDICTIONS_DIR.glob("*.json"):
        rec = json.loads(f.read_text())
        if not rec["verified"] and datetime.fromisoformat(rec["verify_by"]) <= now:
            pending.append(rec)
    return sorted(pending, key=lambda r: r["verify_by"])


def verify_prediction(
    prediction_id: str,
    outcome: str,
    accuracy: float,
) -> dict:
    """Mark a prediction as verified with outcome."""
    path = PREDICTIONS_DIR / f"{prediction_id}.json"
    rec = json.loads(path.read_text())
    rec["verified"] = True
    rec["outcome"] = outcome
    rec["accuracy"] = accuracy
    rec["verified_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    logger.info("Prediction verified: %s (accuracy=%.3f)", prediction_id, accuracy)
    return rec


def get_accuracy_stats() -> dict:
    """Get overall prediction accuracy statistics."""
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    verified = []
    for f in PREDICTIONS_DIR.glob("*.json"):
        rec = json.loads(f.read_text())
        if rec["verified"]:
            verified.append(rec)
    if not verified:
        return {"total_verified": 0, "avg_accuracy": None}
    avg = sum(r["accuracy"] for r in verified) / len(verified)
    return {
        "total_verified": len(verified),
        "avg_accuracy": round(avg, 3),
        "total_pending": len(list(PREDICTIONS_DIR.glob("*.json"))) - len(verified),
    }
