"""계층공간 분석 — 커뮤니티 계층별 변화량 + 전파 방향 감지"""

from __future__ import annotations

from typing import Any

from comad_eye.analysis.base import AnalysisSpace


class HierarchySpace(AnalysisSpace):
    """커뮤니티 계층(C0~C3)별 변화를 분석한다."""

    name = "hierarchy"

    def analyze(self) -> dict[str, Any]:
        tier_analysis = self._analyze_tiers()
        propagation = self._detect_propagation_direction(tier_analysis)

        # 가장 동적인 tier 결정
        tier_deltas = {}
        for tier_key, communities in tier_analysis.items():
            if not isinstance(communities, dict):
                continue
            total = sum(
                abs(c.get("stance_delta", 0)) + abs(c.get("volatility_delta", 0))
                for c in communities.values()
            )
            tier_deltas[tier_key] = total

        most_dynamic = max(tier_deltas, key=tier_deltas.get) if tier_deltas else "C0"

        # 가장 동적인 커뮤니티
        most_dynamic_comm = ""
        max_delta = 0.0
        for communities in tier_analysis.values():
            if not isinstance(communities, dict):
                continue
            for comm_id, metrics in communities.items():
                delta = abs(metrics.get("stance_delta", 0)) + abs(
                    metrics.get("volatility_delta", 0)
                )
                if delta > max_delta:
                    max_delta = delta
                    most_dynamic_comm = comm_id

        return {
            "tier_analysis": tier_analysis,
            "propagation_direction": propagation,
            "most_dynamic_tier": most_dynamic,
            "most_dynamic_community": most_dynamic_comm,
        }

    def _analyze_tiers(self) -> dict[str, Any]:
        """4개 tier별 커뮤니티 변화를 분석한다."""
        result: dict[str, Any] = {}
        graph = self._data.graph

        if graph is None:
            return result

        for tier in range(4):
            tier_key = f"C{tier}"
            result[tier_key] = {}

            # 해당 tier의 커뮤니티 조회
            communities = graph.query(
                "MATCH (n:Entity) WHERE n.community_id IS NOT NULL "
                "AND n.community_tier = $tier "
                "RETURN DISTINCT n.community_id AS cid, "
                "       collect(n.uid) AS members",
                tier=tier,
            )

            if not communities:
                # tier 속성이 없으면 tier=0의 community_id 사용
                if tier == 0:
                    communities = graph.query(
                        "MATCH (n:Entity) WHERE n.community_id IS NOT NULL "
                        "RETURN DISTINCT n.community_id AS cid, "
                        "       collect(n.uid) AS members"
                    )
                else:
                    continue

            for comm in communities:
                cid = str(comm.get("cid", ""))
                members = comm.get("members", [])

                stance_deltas = []
                vol_deltas = []
                action_count = 0

                for uid in members:
                    timeline = self._data.get_entity_timeline(uid)
                    for entry in timeline:
                        if entry.get("property") == "stance":
                            stance_deltas.append(entry.get("delta", 0))
                        elif entry.get("property") == "volatility":
                            vol_deltas.append(entry.get("delta", 0))
                        if entry.get("source") == "action":
                            action_count += 1

                result[tier_key][cid] = {
                    "member_count": len(members),
                    "stance_delta": (
                        sum(stance_deltas) / len(stance_deltas) if stance_deltas else 0
                    ),
                    "volatility_delta": (
                        sum(vol_deltas) / len(vol_deltas) if vol_deltas else 0
                    ),
                    "action_count": action_count,
                    "dominant_event": self._find_dominant_event(members),
                }

        return result

    def _find_dominant_event(self, member_uids: list[str]) -> str:
        """멤버에 가장 큰 영향을 미친 이벤트를 찾는다."""
        event_impacts: dict[str, float] = {}

        for snap in self._data.snapshots:
            changes = snap.get("changes", {})
            for prop_change in changes.get("propagation", []):
                if prop_change.get("target") in member_uids:
                    source = prop_change.get("source", "unknown")
                    delta = abs(prop_change.get("delta", 0))
                    event_impacts[source] = event_impacts.get(source, 0) + delta

        if not event_impacts:
            return ""
        return max(event_impacts, key=event_impacts.get)

    def _detect_propagation_direction(
        self, tier_analysis: dict[str, Any]
    ) -> str:
        """변화의 전파 방향을 감지한다 (top-down / bottom-up / mixed).

        각 tier에서 유의미한 변화(stance_delta + volatility_delta 합산)의 크기를
        비교하여, 상위 tier 변화량이 하위보다 크면 top_down으로 판정한다.
        스냅샷에서 첫 변화 라운드도 참조한다.
        """
        # 방법 1: tier별 총 변화량 비교
        tier_total_delta: dict[int, float] = {}
        for tier in range(4):
            tier_key = f"C{tier}"
            communities = tier_analysis.get(tier_key, {})
            if not isinstance(communities, dict) or not communities:
                continue
            total = sum(
                abs(c.get("stance_delta", 0)) + abs(c.get("volatility_delta", 0))
                for c in communities.values()
            )
            if total > 0.001:
                tier_total_delta[tier] = total

        if len(tier_total_delta) < 2:
            return "mixed"

        # 방법 2: 스냅샷에서 tier별 첫 변화 라운드 추정
        tier_first_round: dict[int, float] = {}
        for snap in self._data.snapshots:
            round_num = snap.get("round", 0)
            if round_num == 0:
                continue
            changes = snap.get("changes", {})
            propagation = changes.get("propagation", [])
            actions = changes.get("actions", [])
            if not propagation and not actions:
                continue
            # 이 라운드에 변화가 있었으면, 아직 기록 안 된 tier에 할당
            for tier in tier_total_delta:
                if tier not in tier_first_round:
                    tier_first_round[tier] = float(round_num)
            if len(tier_first_round) >= len(tier_total_delta):
                break

        # 판정: 변화량 분포 기반
        sorted_by_delta = sorted(tier_total_delta.items(), key=lambda x: x[1], reverse=True)
        top_tier = sorted_by_delta[0][0]
        bottom_tier = sorted_by_delta[-1][0]

        # 상위 tier(번호가 작음)의 변화가 더 크면 top_down
        if top_tier < bottom_tier:
            return "top_down"
        elif top_tier > bottom_tier:
            return "bottom_up"
        return "mixed"
