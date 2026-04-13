"""시뮬레이션 엔진 — 8-Phase 라운드 루프 오케스트레이터"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel

from comad_eye.graph.community import CommunityDetector
from comad_eye.graph.neo4j_client import Neo4jClient
from comad_eye.ontology.action_registry import ActionRegistry
from comad_eye.ontology.meta_edge_engine import MetaEdgeEngine
from comad_eye.simulation.action_resolver import ActionResolver
from comad_eye.simulation.event_chain import EventChain, SimEvent
from comad_eye.simulation.propagation import PropagationEngine
from comad_eye.simulation.snapshot import SnapshotWriter
from comad_eye.active_metadata import ActiveMetadataBus
from comad_eye.config import SimulationSettings, load_settings

logger = logging.getLogger("comadeye")
console = Console()


@dataclass
class SimulationResult:
    """시뮬레이션 결과 요약."""
    total_rounds: int = 0
    total_events: int = 0
    total_actions: int = 0
    total_meta_edges_fired: int = 0
    total_propagation_effects: int = 0
    blast_radius: dict | None = None
    total_community_migrations: int = 0
    llm_calls: int = 0
    early_stop: bool = False
    early_stop_reason: str = ""


class SimulationEngine:
    """8-Phase 라운드 기반 시뮬레이션 엔진."""

    def __init__(
        self,
        client: Neo4jClient,
        meta_edge_engine: MetaEdgeEngine | None = None,
        action_registry: ActionRegistry | None = None,
        metadata_bus: ActiveMetadataBus | None = None,
        settings: SimulationSettings | None = None,
        snapshot_dir: str | None = None,
    ):
        self._client = client
        self._settings = settings or load_settings().simulation
        self._meta_engine = meta_edge_engine or MetaEdgeEngine()
        self._action_registry = action_registry or ActionRegistry()
        self._metadata_bus = metadata_bus or ActiveMetadataBus()
        self._propagation = PropagationEngine(
            client=client,
            decay=self._settings.propagation_decay,
            max_hops=self._settings.propagation_max_hops,
        )
        self._action_resolver = ActionResolver(
            client=client,
            registry=self._action_registry,
            max_actions_per_entity=self._settings.max_actions_per_entity,
        )
        self._snapshot = SnapshotWriter(client, output_dir=snapshot_dir or "data/snapshots")
        self._community = CommunityDetector(client)
        self._prev_avg_vol: float | None = None  # 이전 라운드 평균 volatility

    def run(self, events: list[SimEvent]) -> SimulationResult:
        """시뮬레이션을 실행한다."""
        max_rounds = self._settings.max_rounds
        event_chain = EventChain(events, max_rounds)
        result = SimulationResult(total_events=event_chain.total_events)

        # 초기 스냅샷
        self._snapshot.save(round_num=0, changes={})

        console.print(Panel(
            f"[bold]ComadEye Simulation[/bold]\n"
            f"Events: {event_chain.total_events} | "
            f"Max Rounds: {max_rounds} | "
            f"LLM Calls: 0",
            title="Simulation Start",
        ))

        total_actions = 0
        total_meta = 0
        total_prop = 0
        total_migrations = 0
        all_effects: list = []

        for round_num in range(1, max_rounds + 1):
            changes: dict[str, Any] = {}

            # Phase A: 이벤트 주입
            injected_events = event_chain.next_events(round_num)
            impacted: list[tuple[str, float]] = []
            if injected_events:
                impacted = self._inject_events(injected_events)
                changes["events"] = injected_events
                changes["impacted"] = impacted

            # Phase B: 영향 전파
            if impacted:
                effects = self._propagation.propagate(impacted)
                all_effects.extend(effects)
                applied = self._propagation.apply_effects(effects)
                changes["propagation"] = applied
                total_prop += len(applied)

            # Phase C: 메타엣지 평가
            meta_results = self._evaluate_meta_edges(changes)
            changes["meta_edges"] = meta_results
            total_meta += len(meta_results)

            # Phase D: Action 해결
            action_log = self._action_resolver.resolve(round_num)
            changes["actions"] = action_log
            total_actions += len(action_log)

            # Phase E: 자연 감쇠
            self._apply_decay()

            # Phase F: 커뮤니티 재계산 (조건부)
            if round_num % self._settings.community_refresh_interval == 0:
                comm_result = self._community.detect()
                migrations = comm_result.get("migrations", [])
                changes["migrations"] = migrations
                total_migrations += len(migrations)

            # Phase G: Active Metadata 전파
            self._propagate_metadata(changes, round_num)

            # Phase H: 스냅샷 저장
            self._snapshot.save(round_num, changes)

            # 불변량 체크
            violations = self._snapshot.check_invariants()
            if violations:
                for v in violations:
                    logger.warning(f"[Round {round_num}] 불변량 위반: {v}")

            # 라운드 요약 출력
            self._print_round_summary(round_num, max_rounds, changes)

            # 종료 조건 체크
            if self._check_convergence(round_num):
                result.early_stop = True
                result.early_stop_reason = "수렴"
                console.print(f"[yellow]수렴 감지: Round {round_num}에서 조기 종료[/yellow]")
                result.total_rounds = round_num
                break
        else:
            result.total_rounds = max_rounds

        result.total_actions = total_actions
        result.total_meta_edges_fired = total_meta
        result.total_propagation_effects = total_prop
        result.total_community_migrations = total_migrations
        result.blast_radius = self._propagation.blast_radius(all_effects) if all_effects else None

        console.print(Panel(
            f"[bold green]Simulation Complete[/bold green]\n"
            f"Rounds: {result.total_rounds} | "
            f"Events: {result.total_events} | "
            f"Actions: {result.total_actions} | "
            f"Meta-edges: {result.total_meta_edges_fired} | "
            f"LLM: 0",
            title="Result",
        ))

        return result

    def _inject_events(
        self, events: list[SimEvent]
    ) -> list[tuple[str, float]]:
        """이벤트를 그래프에 주입하고 직접 영향 노드를 반환한다."""
        impacted: list[tuple[str, float]] = []
        for event in events:
            # 이벤트 노드 활성화
            self._client.update_entity_property(event.uid, "is_active", True)

            # IMPACTS 관계를 통한 직접 영향
            result = self._client.query(
                "MATCH (e:Entity {uid: $uid})-[r:IMPACTS]->(n:Entity) "
                "RETURN n.uid AS uid, r.weight AS weight, n.susceptibility AS susc",
                uid=event.uid,
            )

            for r in result:
                delta = event.magnitude * float(r.get("weight", 1.0)) * float(r.get("susc", 0.5))
                # volatility 증가
                self._client.write(
                    "MATCH (n:Entity {uid: $uid}) "
                    "SET n.volatility = CASE "
                    "  WHEN n.volatility + $delta > 1.0 THEN 1.0 "
                    "  ELSE n.volatility + $delta END",
                    uid=r["uid"],
                    delta=delta,
                )
                impacted.append((r["uid"], delta))

            # REACTS_TO가 없는 경우, INFLUENCES 관계도 확인
            if not result:
                result2 = self._client.query(
                    "MATCH (e:Entity {uid: $uid})-[r:INFLUENCES|REACTS_TO]->(n:Entity) "
                    "RETURN n.uid AS uid, r.weight AS weight, n.susceptibility AS susc",
                    uid=event.uid,
                )
                for r in result2:
                    delta = event.magnitude * float(r.get("weight", 1.0)) * float(r.get("susc", 0.5)) * 0.5
                    impacted.append((r["uid"], delta))

        return impacted

    def _evaluate_meta_edges(
        self, changes: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """메타엣지 규칙을 평가한다."""
        entities_data = [
            r["props"] for r in self._client.get_all_entities()
        ]

        entity_limit = self._settings.meta_edge_entity_limit
        neighbor_limit = self._settings.meta_edge_neighbor_limit

        if len(entities_data) > entity_limit:
            logger.warning(
                "메타엣지 평가: 엔티티 %d개 중 %d개만 평가 (meta_edge_entity_limit)",
                len(entities_data), entity_limit,
            )

        # on_change 트리거
        on_change_results = []
        for prop_change in changes.get("propagation", []):
            prop = prop_change.get("property", "stance")
            source_uid = prop_change.get("target", "")
            source_entity = next(
                (e for e in entities_data if e.get("uid") == source_uid), {}
            )
            neighbors = [
                e for e in entities_data if e.get("uid") != source_uid
            ]
            results = self._meta_engine.evaluate_on_change(
                changed_property=prop,
                source_entity=source_entity,
                target_entities=neighbors[:neighbor_limit],
            )
            on_change_results.extend(results)

        # evaluate 트리거
        eval_results = self._meta_engine.evaluate_all(
            entities=entities_data[:entity_limit],
        )

        return on_change_results + eval_results

    def _apply_decay(self) -> None:
        """자연 감쇠를 적용한다."""
        decay_rate = self._settings.volatility_decay
        self._client.write(
            "MATCH (n:Entity) WHERE n.volatility > 0 "
            "SET n.volatility = n.volatility * (1 - $decay), "
            "    n.price_pressure = 0",
            decay=decay_rate,
        )

    def _propagate_metadata(
        self, changes: dict[str, Any], round_num: int
    ) -> None:
        """Active Metadata를 전파한다."""
        for prop_change in changes.get("propagation", []):
            self._metadata_bus.emit_property_change(
                entity_uid=prop_change.get("target", ""),
                prop=prop_change.get("property", ""),
                old_val=prop_change.get("old", 0),
                new_val=prop_change.get("new", 0),
                round_num=round_num,
                caused_by="propagation",
            )

        for action in changes.get("actions", []):
            for effect in action.get("effects", []):
                if effect.get("type") == "property_change":
                    self._metadata_bus.emit_property_change(
                        entity_uid=effect.get("target", ""),
                        prop=effect.get("property", ""),
                        old_val=effect.get("old", 0),
                        new_val=effect.get("new", 0),
                        round_num=round_num,
                        caused_by=f"action:{action.get('action', '')}",
                    )

    def _check_convergence(self, round_num: int) -> bool:
        """변화율 기반 수렴 조건을 확인한다.

        개선점:
        - min_rounds 이전에는 수렴 판정하지 않음
        - 절대값이 아닌 변화율(delta)로 판정: 이전 라운드 대비 volatility 변화가
          threshold 미만이면 수렴으로 판단
        """
        min_rounds = getattr(self._settings, "min_rounds", 5)
        if round_num < min_rounds:
            return False

        threshold = self._settings.convergence_threshold
        result = self._client.query(
            "MATCH (n:Entity) RETURN avg(n.volatility) AS avg_vol"
        )
        avg_vol = result[0]["avg_vol"] if result else 1.0
        if avg_vol is None:
            avg_vol = 0.0

        # 변화율 기반 수렴: |현재 - 이전| < threshold
        if self._prev_avg_vol is not None:
            delta = abs(avg_vol - self._prev_avg_vol)
            self._prev_avg_vol = avg_vol
            return delta < threshold
        else:
            self._prev_avg_vol = avg_vol
            return False

    def _print_round_summary(
        self,
        round_num: int,
        max_rounds: int,
        changes: dict[str, Any],
    ) -> None:
        """라운드 요약을 Rich로 출력한다."""
        events = changes.get("events", [])
        actions = changes.get("actions", [])
        meta = changes.get("meta_edges", [])
        prop = changes.get("propagation", [])
        migrations = changes.get("migrations", [])

        summary = self._snapshot._get_summary()

        lines = [
            f"[bold]Round {round_num}/{max_rounds}[/bold]",
            f"  Events: {len(events)} | Actions: {len(actions)} | "
            f"Meta-edges: {len(meta)} | Propagation: {len(prop)}",
            f"  Volatility avg={summary.get('avg_volatility', 0):.3f} | "
            f"Stance avg={summary.get('avg_stance', 0):.3f}",
        ]

        if migrations:
            lines.append(f"  Community migrations: {len(migrations)}")

        if actions:
            action_names = [a.get("action", "?") for a in actions[:5]]
            lines.append(f"  Actions: {', '.join(action_names)}")

        console.print("\n".join(lines))
