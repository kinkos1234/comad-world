"""이벤트 체인 — 이벤트 큐 관리 + 라운드 배정"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimEvent:
    """시뮬레이션 이벤트."""
    uid: str
    name: str
    magnitude: float = 0.5
    round: int = 1
    is_active: bool = False
    properties: dict[str, Any] = field(default_factory=dict)


class EventChain:
    """이벤트 시퀀스를 관리하고 라운드별로 주입한다."""

    def __init__(self, events: list[SimEvent], max_rounds: int = 10):
        self._all_events = list(events)
        self._assign_rounds(max_rounds)
        self._queue: deque[SimEvent] = deque(
            sorted(self._all_events, key=lambda e: e.round)
        )
        self._injected: list[SimEvent] = []

    def _assign_rounds(self, max_rounds: int) -> None:
        """이벤트에 라운드를 배정한다."""
        n = len(self._all_events)
        if n == 0:
            return

        # 이미 라운드가 배정된 이벤트는 유지
        unassigned = [e for e in self._all_events if e.round <= 0]
        if not unassigned:
            return

        # 균등 분배 (여파 관찰용 여유 라운드 확보)
        event_window = max(1, max_rounds - 3)
        interval = max(1, event_window // len(unassigned))

        for i, event in enumerate(unassigned):
            event.round = min(1 + i * interval, max_rounds - 2)

    def next_events(self, round_num: int) -> list[SimEvent]:
        """현재 라운드에 주입할 이벤트를 반환한다."""
        result: list[SimEvent] = []
        while self._queue and self._queue[0].round <= round_num:
            event = self._queue.popleft()
            event.is_active = True
            result.append(event)
            self._injected.append(event)
        return result

    @property
    def total_events(self) -> int:
        return len(self._all_events)

    @property
    def injected_count(self) -> int:
        return len(self._injected)

    @property
    def remaining(self) -> int:
        return len(self._queue)

    def add_triggered_event(self, event: SimEvent) -> None:
        """이벤트 체인에 의해 트리거된 새 이벤트를 추가한다."""
        self._queue.append(event)
        # 재정렬
        sorted_queue = sorted(self._queue, key=lambda e: e.round)
        self._queue = deque(sorted_queue)
