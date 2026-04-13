"""Impact Analyzer — Manifest 의존성 그래프 기반 변경 영향 분석"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx
from rich.console import Console
from rich.tree import Tree

from comad_eye.config import load_yaml, project_root


@dataclass
class ImpactReport:
    """변경 영향 분석 결과."""
    changed: str
    directly_affected: list[str] = field(default_factory=list)
    indirectly_affected: list[str] = field(default_factory=list)
    total_scope: int = 0
    total_capabilities: int = 0
    cmr_reassessment: list[dict[str, Any]] = field(default_factory=list)
    depth_map: dict[int, list[str]] = field(default_factory=dict)


class ImpactAnalyzer:
    """Manifest 의존성 그래프에서 변경 영향 범위를 분석한다."""

    def __init__(
        self,
        manifest_path: str | None = None,
        cmr_path: str | None = None,
    ):
        root = project_root()
        self._manifest = load_yaml(
            manifest_path or str(root / "config" / "manifest.yaml")
        )
        self._cmr = load_yaml(cmr_path or str(root / "config" / "cmr.yaml"))
        self._graph = self._build_dependency_graph()

    def _build_dependency_graph(self) -> nx.DiGraph:
        """Manifest에서 의존성 그래프를 구축한다."""
        g = nx.DiGraph()
        packages = self._manifest.get("packages", {})

        # 패키지 → 능력 관계 추가
        for pkg_name, pkg_data in packages.items():
            g.add_node(pkg_name, node_type="package")
            for cap in pkg_data.get("capabilities", []):
                g.add_node(cap, node_type="capability")
                g.add_edge(pkg_name, cap, relation="contains")

            # 패키지 간 의존성
            for dep in pkg_data.get("depends_on", []):
                g.add_edge(pkg_name, dep, relation="depends_on")
                # 능력 → 의존 패키지의 능력 간 간접 의존
                for cap in pkg_data.get("capabilities", []):
                    if dep in packages:
                        for dep_cap in packages[dep].get("capabilities", []):
                            g.add_edge(cap, dep_cap, relation="indirect_depends")

        return g

    def analyze(self, changed_component: str) -> ImpactReport:
        """변경된 컴포넌트의 영향 범위를 분석한다."""
        if changed_component not in self._graph:
            # 설정 파일명으로 매핑 시도
            component = self._resolve_config_to_capability(changed_component)
            if component is None:
                return ImpactReport(
                    changed=changed_component,
                    total_capabilities=self._graph.number_of_nodes(),
                )
            changed_component = component

        # 역방향 탐색: 이 컴포넌트에 의존하는 모든 것
        reverse_graph = self._graph.reverse()
        if changed_component in reverse_graph:
            affected = nx.descendants(reverse_graph, changed_component)
        else:
            affected = set()

        # depth별 분류
        depth_map: dict[int, list[str]] = {}
        for node in affected:
            try:
                path = nx.shortest_path(
                    reverse_graph, changed_component, node
                )
                depth = len(path) - 1
            except nx.NetworkXNoPath:
                depth = 99
            depth_map.setdefault(depth, []).append(node)

        directly = depth_map.get(1, [])
        indirectly = [
            n for d, nodes in depth_map.items()
            if d > 1 for n in nodes
        ]

        # CMR 재평가 대상
        registry = self._cmr.get("registry", {})
        reassessment = []
        for node in affected:
            if node in registry:
                reassessment.append({
                    "capability": node,
                    "current_level": registry[node].get("level", 0),
                })

        return ImpactReport(
            changed=changed_component,
            directly_affected=directly,
            indirectly_affected=indirectly,
            total_scope=len(affected),
            total_capabilities=self._graph.number_of_nodes(),
            cmr_reassessment=reassessment,
            depth_map=depth_map,
        )

    def _resolve_config_to_capability(self, config_name: str) -> str | None:
        """설정 파일명을 관련 Capability로 매핑한다."""
        mapping = {
            "meta_edges.yaml": "meta_edge_engine",
            "action_types.yaml": "action_registry",
            "propagation_rules.yaml": "propagation_engine",
            "glossary.yaml": "entity_extraction",
            "bindings.yaml": "active_metadata_bus",
        }
        # 파일명에서 config/ 접두사 제거
        clean = config_name.replace("config/", "")
        return mapping.get(clean)

    def render(self, report: ImpactReport, console: Console | None = None) -> None:
        """Impact Analysis 결과를 Rich Tree로 출력한다."""
        console = console or Console()

        tree = Tree(
            f"[bold]Impact Analysis: {report.changed}[/bold] "
            f"({report.total_scope}/{report.total_capabilities} affected)"
        )

        for depth in sorted(report.depth_map.keys()):
            nodes = report.depth_map[depth]
            label = "직접 영향" if depth == 1 else f"간접 영향 (depth {depth})"
            branch = tree.add(f"[bold]{label}[/bold]")
            for node in nodes:
                cmr = self._get_cmr_level(node)
                cmr_badge = self._cmr_badge(cmr)
                branch.add(f"{node} {cmr_badge}")

        if report.cmr_reassessment:
            reeval = tree.add("[bold yellow]CMR 재평가 필요[/bold yellow]")
            for item in report.cmr_reassessment:
                reeval.add(
                    f"{item['capability']} (현재 Level {item['current_level']})"
                )

        console.print(tree)

    def _get_cmr_level(self, capability: str) -> int:
        registry = self._cmr.get("registry", {})
        return registry.get(capability, {}).get("level", 0)

    @staticmethod
    def _cmr_badge(level: int) -> str:
        badges = {
            0: "[dim]?[/dim]",
            1: "[red]CMR 1[/red]",
            2: "[yellow]CMR 2[/yellow]",
            3: "[yellow]CMR 3[/yellow]",
            4: "[green]CMR 4[/green]",
            5: "[blue]CMR 5[/blue]",
        }
        return badges.get(level, "[dim]?[/dim]")
