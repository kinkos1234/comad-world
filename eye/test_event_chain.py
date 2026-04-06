"""Tests for event chain — round assignment and event injection."""

from __future__ import annotations

from simulation.event_chain import EventChain, SimEvent


class TestSimEvent:
    def test_defaults(self):
        e = SimEvent(uid="e1", name="Event 1")
        assert e.magnitude == 0.5
        assert e.round == 1
        assert e.is_active is False

    def test_custom_values(self):
        e = SimEvent(uid="e1", name="Event 1", magnitude=0.8, round=3)
        assert e.magnitude == 0.8
        assert e.round == 3


class TestEventChain:
    def test_single_event(self):
        events = [SimEvent(uid="e1", name="E1", round=1)]
        chain = EventChain(events, max_rounds=5)
        assert chain.total_events == 1
        assert chain.remaining == 1

    def test_next_events_at_round(self):
        events = [
            SimEvent(uid="e1", name="E1", round=1),
            SimEvent(uid="e2", name="E2", round=3),
        ]
        chain = EventChain(events, max_rounds=5)

        r1 = chain.next_events(1)
        assert len(r1) == 1
        assert r1[0].uid == "e1"
        assert r1[0].is_active is True

        r2 = chain.next_events(2)
        assert len(r2) == 0

        r3 = chain.next_events(3)
        assert len(r3) == 1
        assert r3[0].uid == "e2"

    def test_auto_assign_rounds(self):
        """Events with round <= 0 should get auto-assigned."""
        events = [
            SimEvent(uid="e1", name="E1", round=0),
            SimEvent(uid="e2", name="E2", round=0),
            SimEvent(uid="e3", name="E3", round=0),
        ]
        EventChain(events, max_rounds=10)
        # All should be assigned positive rounds
        for e in events:
            assert e.round >= 1

    def test_pre_assigned_preserved(self):
        events = [SimEvent(uid="e1", name="E1", round=5)]
        EventChain(events, max_rounds=10)
        assert events[0].round == 5

    def test_add_triggered_event(self):
        chain = EventChain([], max_rounds=5)
        chain.add_triggered_event(SimEvent(uid="t1", name="Triggered", round=2))
        assert chain.remaining == 1
        triggered = chain.next_events(2)
        assert len(triggered) == 1
        assert triggered[0].uid == "t1"

    def test_injected_count(self):
        events = [SimEvent(uid="e1", name="E1", round=1)]
        chain = EventChain(events, max_rounds=5)
        assert chain.injected_count == 0
        chain.next_events(1)
        assert chain.injected_count == 1

    def test_empty_chain(self):
        chain = EventChain([], max_rounds=5)
        assert chain.total_events == 0
        assert chain.remaining == 0
        assert chain.next_events(1) == []

    def test_all_events_same_round(self):
        events = [
            SimEvent(uid=f"e{i}", name=f"E{i}", round=2)
            for i in range(3)
        ]
        chain = EventChain(events, max_rounds=5)
        assert chain.next_events(1) == []
        r2 = chain.next_events(2)
        assert len(r2) == 3
        assert chain.remaining == 0
