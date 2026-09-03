#!/usr/bin/env python3
"""05 verify_initial — 하네스 5축 점수를 측정한다.

2026-08-02 사용자 결정으로 지표를 바꿨다.

예전 지표 `l6_blocker_count` 는 pending(=포착된 fix:/feat: 커밋 수) 을 더하고 있어서
**일하면 올라가는** 값이었다. 주 1회 learn-weekly 가 pending 을 비울 때만 떨어지는
톱니파였고, 정지 조건(0)에 도달할 경로가 루프 밖에 있었다. 3,860회를 도달 불가능한
목표에 대고 돌린 셈이다.

지금 지표는 harness-report 의 composite score (0-100, 높을수록 좋음):
  HARD 커버리지 30 · pending 처리율 30 · 반복패턴 20 · 2차리뷰 10 · evolve 활동 10
커밋한다고 올라가지 않고, "좋아지고 있나"에 직접 답한다.

Stdout: {status, output:{metric_name, metric_value, breakdown}}
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys

HARNESS = (
    pathlib.Path.home() / ".claude" / "skills" / "harness-report" / "bin" / "harness-report.py"
)


def load_harness():
    spec = importlib.util.spec_from_file_location("harness_report", HARNESS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"harness-report 로드 실패: {HARNESS}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["harness_report"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    json.loads(sys.stdin.read() or "{}")  # payload 는 쓰지 않지만 규약상 소비한다

    try:
        hr = load_harness()
        # measure() 는 results.tsv 에 쓰지 않는다 — 기록은 harness-report 자신의 몫
        # 비용 스캔(collect-cost: 전체 트랜스크립트 수백 파일) 은 점수에 안 들어가므로 tick 마다 돌리지
        # 않는다 — 하루 1회 15-closeout 의 append 때만 잰다 (2026-09-03 headless 감사 §5-4).
        os.environ.setdefault("HARNESS_SKIP_COST", "1")
        m = hr.measure(notes="loopy-era verify")
        score = float(m["score"])
        breakdown = {
            "hard": f"{m['hard_count']}/{m['hard_target']}",
            "pending": f"{m['pending_processed']}/{m['pending_total']}",
            "recurring": m["recurring"],
            "second_opinion": m["second_opinion"],
            "evolve_applied": m["evolve_applied"],
        }
    except Exception as e:  # 측정 실패를 0점으로 흘리면 루프가 영원히 안 멈춘다 — 명시적으로 알린다
        print(json.dumps({
            "status": "error",
            "summary": f"하네스 점수 측정 실패: {e}",
        }, ensure_ascii=False))
        return 1

    print(json.dumps({
        "status": "ok",
        "output": {
            "metric_name": "harness_score",
            "metric_value": score,
            "breakdown": breakdown,
        },
        "summary": f"harness_score={score} ({breakdown})",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
