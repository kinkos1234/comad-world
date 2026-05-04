# Comad — loopy-era

> **Always-on self-evolution harness** — 30분 주기 supervisor + memory-bank
> 자동 동기화 + 야간 dream 자동 발화. 사용자 명시 트리거 없이도
> 메모리 그래프가 비대해지지 않고 system score 가 계속 측정·기록되는 것이
> 핵심 정체성.

## 빠른 그림

```
LaunchAgent (30분)        LaunchAgent (2시간)        LaunchAgent (03:15 KST)
┌───────────────────┐    ┌───────────────────┐    ┌─────────────────────────┐
│ supervisor.py     │    │ kb-sleep-tick.py  │    │ auto-dream.sh           │
│   ↓ 15-phase tick │    │   ↓ extract       │    │   ↓ dream_pending? then │
│ phases/           │    │     embed         │    │     headless `claude -p`│
│   01-init →       │    │     consolidate   │    │     comad-sleep agent   │
│   ...             │    │     publish git   │    │                         │
│   15-closeout     │    │   → /memory-log/  │    │ (mutex: skip if cdx/ccd)│
└───────────────────┘    └───────────────────┘    └─────────────────────────┘
```

## 디렉토리

```
loopy-era/                       ← git 추적 (이 레포)
├── README.md                    ← 이 파일
├── bin/
│   ├── supervisor.py            ← 15-phase orchestrator
│   ├── start-harness.sh         ← 수동 진입점 (status/tick/start/stop)
│   ├── llm-dispatch.sh          ← 환경 감지 (claude / codex), no fallback
│   ├── kb-sleep-tick.py         ← memory-bank tick 워커 (2h)
│   ├── auto-dream.sh            ← 야간 dream 트리거 (03:15 KST)
│   ├── hooks/
│   │   ├── session-start.sh
│   │   ├── stop.sh
│   │   └── user-prompt-submit.sh
│   └── phases/
│       ├── 01-init-project.py
│       ├── 02-qa-scenario-gen.py
│       ├── 03-self-improve-trigger.py
│       ├── 04-self-improve-worker-initial.py
│       ├── 05-verify-initial.py
│       ├── 13-verify-final.py
│       └── 15-closeout.py
└── (런타임은 ~/.comad/loopy-era/ 에 별도 — gitignore)
```

## 런타임 디렉토리

`~/.comad/loopy-era/` 가 모든 런타임 상태를 보유:

| 항목 | 역할 |
|---|---|
| `state.json` | iteration, last_phase, metric_value, stopping flag |
| `phase_history/iter-NNNN/*.json` | phase 별 raw output |
| `pending/*.json` | Stop hook 가 잡은 fix/feat 커밋 (T6 candidates) |
| `logs/{daemon,supervisor,kb-sleep,auto-dream}*.log` | 각 LaunchAgent stdout/stderr |
| `metrics.jsonl` | tick 별 metric trail |
| `results.tsv` | composite score history (harness-report) |
| `bin/` | (symlink → 이 레포의 `bin/`) |

이 분리 덕에 **소스는 git, 상태는 런타임** — 다른 comad 모듈과 일관.

## LaunchAgent 3개

| Label | 주기 | ProgramArguments |
|---|---|---|
| `com.comad.loopy-era` | StartInterval 1800s (30m) | `bin/supervisor.py tick` |
| `com.comad.kb-sleep` | StartInterval 7200s (2h) | `bin/kb-sleep-tick.py` |
| `com.comad.auto-dream` | StartCalendar 03:15 daily | `bin/auto-dream.sh` |

설치는 comad-world 루트의 `install.sh` 가 처리.

## 환경변수

| 변수 | 기본값 | 의미 |
|---|---|---|
| `COMAD_LOOPY_DIR` | `~/.comad/loopy-era` | 런타임 디렉토리 (state/logs/pending/...) |
| `COMAD_LOOPY_LLM` | `auto` | `claude` / `codex` / `auto` (dispatcher 분기) |
| `KB_SLEEP_NO_PUSH` | `0` | `1` 이면 kb-sleep-tick 의 git push 비활성 |
| `OLLAMA_URL` | `http://localhost:11434` | 임베딩용 (kb-sleep) |

## 수동 사용

```bash
# 한 번 tick (전체 15-phase)
comad-world/loopy-era/bin/start-harness.sh tick

# 상태
comad-world/loopy-era/bin/supervisor.py status

# kb-sleep tick 수동 (push 안 하고)
comad-world/loopy-era/bin/kb-sleep-tick.py --no-push

# auto-dream 수동 트리거
comad-world/loopy-era/bin/auto-dream.sh
```

## 의존

- macOS launchd (LaunchAgent 등록)
- python3 (stdlib only — numpy/pip deps 없음)
- bash + zsh
- (선택) Ollama @ localhost:11434 — `nomic-embed-text` 모델 (kb-sleep 임베딩)
- (선택) `claude` CLI — auto-dream 실행 시 호출

## 라이브 게시

매 kb-sleep tick 의 메타정보가 GitHub Pages 에 자동 게시됩니다 (옵션 1: 본문 비공개, 메타만):
👉 https://kinkos1234.github.io/memory-log/

자세한 구조와 안전장치는 [comad/guide/sleep.html](https://kinkos1234.github.io/comad/guide/sleep.html#loop)
를 참고.
