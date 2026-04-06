"""시간공간 분석 — 이벤트-반응 시차 + 선행지표 + 생명주기"""

from __future__ import annotations

from typing import Any

import numpy as np

from analysis.base import AnalysisSpace


class TemporalSpace(AnalysisSpace):
    """시간 순서 기반 분석을 수행한다."""

    name = "temporal"

    def analyze(self) -> dict[str, Any]:
        event_reactions = self._analyze_event_reactions()
        leading_indicators = self._detect_leading_indicators()
        lifecycle = self._classify_lifecycle()

        return {
            "event_reactions": event_reactions,
            "leading_indicators": leading_indicators,
            "lifecycle_phases": lifecycle,
        }

    def _analyze_event_reactions(self) -> dict[str, Any]:
        """이벤트별 반응 시차를 측정한다."""
        results: dict[str, Any] = {}

        for event in self._data.events_log:
            event_uid = event.get("uid", "")
            event_round = event.get("round", 0)
            reactions: list[dict[str, Any]] = []

            for action in self._data.actions_log:
                action_round = action.get("round", 0)
                if action_round >= event_round:
                    delay = action_round - event_round
                    if delay <= 5:  # 5라운드 이내만
                        reactions.append({
                            "action": action.get("action", ""),
                            "actor": action.get("actor", ""),
                            "actor_name": action.get("actor_name", ""),
                            "delay_rounds": delay,
                        })

            if reactions:
                delays = [r["delay_rounds"] for r in reactions]
                reactions.sort(key=lambda r: r["delay_rounds"])

                results[event_uid] = {
                    "event_name": event.get("name", event_uid),
                    "injection_round": event_round,
                    "reaction_count": len(reactions),
                    "avg_delay": float(np.mean(delays)),
                    "first_reactor": reactions[0] if reactions else None,
                    "cascading_order": [
                        r["actor_name"] or r["actor"] for r in reactions[:10]
                    ],
                }

        return results

    def _detect_leading_indicators(self) -> list[dict[str, Any]]:
        """선행지표를 탐지한다 (교차상관 분석)."""
        indicators: list[dict[str, Any]] = []

        if not self._data.graph:
            return indicators

        # 모든 엔티티의 stance 시계열 수집
        entities = self._data.graph.query(
            "MATCH (n:Entity) RETURN n.uid AS uid, n.name AS name"
        )
        if not entities or len(entities) < 2:
            return indicators

        # 시계열 구축
        series_map: dict[str, list[float]] = {}
        name_map: dict[str, str] = {}
        for ent in entities:
            uid = ent.get("uid", "")
            name_map[uid] = ent.get("name", uid)
            series_map[uid] = self._data.get_stance_series(uid)

        # 최소 3라운드 이상 시계열만 분석
        valid_uids = [
            uid for uid, s in series_map.items()
            if len(s) >= 3 and any(v != 0 for v in s)
        ]

        for i, uid_a in enumerate(valid_uids):
            for uid_b in valid_uids[i + 1:]:
                series_a = np.array(series_map[uid_a])
                series_b = np.array(series_map[uid_b])

                if len(series_a) != len(series_b):
                    min_len = min(len(series_a), len(series_b))
                    series_a = series_a[:min_len]
                    series_b = series_b[:min_len]

                corr, lag = self._cross_correlate(series_a, series_b)

                if abs(corr) > 0.7 and lag != 0:
                    leader = uid_a if lag > 0 else uid_b
                    follower = uid_b if lag > 0 else uid_a
                    indicators.append({
                        "leader": leader,
                        "leader_name": name_map.get(leader, leader),
                        "follower": follower,
                        "follower_name": name_map.get(follower, follower),
                        "correlation": round(float(corr), 3),
                        "lag_rounds": abs(lag),
                    })

        # 상관계수 내림차순 정렬
        indicators.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return indicators[:20]

    def _cross_correlate(
        self, a: np.ndarray, b: np.ndarray
    ) -> tuple[float, int]:
        """두 시계열의 교차상관을 계산한다."""
        n = len(a)
        if n < 3:
            return 0.0, 0

        a_norm = a - np.mean(a)
        b_norm = b - np.mean(b)

        std_a = np.std(a_norm)
        std_b = np.std(b_norm)
        if std_a < 1e-10 or std_b < 1e-10:
            return 0.0, 0

        max_lag = min(3, n // 2)
        best_corr = 0.0
        best_lag = 0

        for lag in range(-max_lag, max_lag + 1):
            if lag >= 0:
                c = np.sum(a_norm[lag:] * b_norm[:n - lag]) / (n * std_a * std_b)
            else:
                c = np.sum(a_norm[:n + lag] * b_norm[-lag:]) / (n * std_a * std_b)

            if abs(c) > abs(best_corr):
                best_corr = float(c)
                best_lag = lag

        return best_corr, best_lag

    def _classify_lifecycle(self) -> dict[str, list[str]]:
        """각 엔티티의 생명주기 단계를 분류한다."""
        lifecycle: dict[str, list[str]] = {}

        if not self._data.graph:
            return lifecycle

        entities = self._data.graph.query(
            "MATCH (n:Entity) RETURN n.uid AS uid"
        )

        for ent in entities or []:
            uid = ent.get("uid", "")
            timeline = self._data.get_entity_timeline(uid)

            phases: list[str] = ["inactive"]
            for entry in timeline:
                if entry.get("source") == "propagation":
                    delta = abs(entry.get("delta", 0))
                    prop = entry.get("property", "")

                    if prop == "volatility" and delta > 0.1:
                        if phases[-1] != "overheated":
                            phases.append("activated")
                            phases.append("overheated")
                    elif prop == "volatility" and delta < -0.05:
                        if phases[-1] == "overheated":
                            phases.append("cooling")

            if phases[-1] in ("cooling", "inactive"):
                phases.append("stable")

            # 중복 제거 (연속 동일 단계)
            deduped = [phases[0]]
            for p in phases[1:]:
                if p != deduped[-1]:
                    deduped.append(p)

            lifecycle[uid] = deduped

        return lifecycle
