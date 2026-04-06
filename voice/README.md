<p align="center">
  <img src="docs/images/slide-1-cover.png" alt="Comad Voice" width="800" style="max-width: 100%;">
</p>

<h1 align="center">Comad Voice</h1>

<p align="center">
  <strong>"말만 해. 나머지는 AI가 다 한다."</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/kinkos1234/comad-voice/releases"><img src="https://img.shields.io/github/v/release/kinkos1234/comad-voice?include_prereleases" alt="Release"></a>
  <img src="https://img.shields.io/badge/Made%20with-AI-22D3EE" alt="Made with AI">
  <img src="https://img.shields.io/badge/Claude%20Code-compatible-blueviolet" alt="Claude Code">
  <a href="https://github.com/kinkos1234/comad-voice/stargazers"><img src="https://img.shields.io/github/stars/kinkos1234/comad-voice?style=social" alt="GitHub Stars"></a>
</p>

<p align="center">
  비개발자 바이브코더를 위한 AI 워크플로우 하네스.<br>
  Claude Code 하나만 있으면 대주제 하나 던지면<br>
  리서치 → 실험 → 리팩토링 → 완성까지 자동으로 돌아간다.
</p>

<p align="center">
  한국어 · <a href="README.en.md">English</a>
</p>

---

## 목차

- [Comad 시리즈](#comad-시리즈)
- [누구를 위한 건가요?](#누구를-위한-건가요)
- [이걸 쓰면 뭐가 달라지나요?](#이걸-쓰면-뭐가-달라지나요)
- [왜 Comad Voice인가?](#왜-comad-voice인가)
- [필수 요구 사항](#필수-요구-사항)
- [설치](#설치)
- [사용법](#사용법)
- [핵심 명령어 치트시트](#핵심-명령어-치트시트)
- [작동 원리](#작동-원리)
- [문제 해결](#문제-해결)
- [크레딧](#크레딧)
- [기여하기](#기여하기)
- [라이선스](#라이선스)

---

## Comad 시리즈

| 이름            | 역할                          |
| --------------- | ----------------------------- |
| **ComadEye**    | 미래 시뮬레이터 (보다)        |
| **Comad Ear**   | 디스코드 봇 서버 (듣다)       |
| **Comad Brain** | 지식 온톨로지 (생각하다)      |
| **Comad Voice** | AI 워크플로우 하네스 (말하다) |

---

## 누구를 위한 건가요?

- 코딩은 모르지만 AI로 프로젝트를 만들고 싶은 사람
- Claude Max, ChatGPT Plus, Google Pro 등 구독은 있는데 제대로 활용을 못 하는 사람
- "뭘 시켜야 할지 모르겠는" 바이브코더

## 이걸 쓰면 뭐가 달라지나요?

**Before:** "이거 개선해줘" → Claude가 한 가지만 고치고 끝

**After:** "검토해봐" → Claude가 알아서 진단하고, 선택지 카드를 보여주고, 선택만 하면 자동 실험 루프

<p align="center">
  <img src="docs/images/slide-2-before-after.png" alt="Before vs After" width="800" style="max-width: 100%;">
</p>

### 기능 비교

| 기능 | Raw Claude Code | Comad Voice v3 |
| --- | :---: | :---: |
| 한마디 진단 ("검토해봐") | - | O |
| 자동 실험 루프 (autoresearch) | - | O |
| 멀티-AI 의존성 자동 판단 | - | O |
| 세션 메모리 관리 | - | O |
| 로컬 모델 대기시간 활용 | - | O |
| 비개발자 카드 UI | - | O |
| 디자인 파이프라인 (시안+코드) | - | O (v3 신규) |
| 보안 감사 (CSO 모드) | - | O (v3 신규) |
| 브라우저 QA 테스트 | - | O (v3 신규) |
| 배포+카나리 모니터링 | - | O (v3 신규) |
| 멀티AI 검증+학습 관리 | - | O (v3 신규) |
| 설치 복잡도 | - | 1줄 curl |

### 왜 Comad Voice인가?

Claude Code는 강력하지만, **뭘 시켜야 하는지 아는 사람**을 위해 설계되었습니다.

Comad Voice는 그 반대편에 있는 사람을 위한 것입니다:

- "검토해봐" 한마디면 AI가 알아서 진단하고 실험합니다
- 의존성 판단, 병렬 위임, 세션 관리를 사용자 대신 합니다
- 코드가 아닌 **설정(configuration)**입니다 — 설치하고 말하면 끝

> "도구를 잘 쓰는 것"이 아니라 "도구가 알아서 잘 되는 것"

---

## 필수 요구 사항

| 도구                       | 필요 여부 | 설명                                      |
| -------------------------- | --------- | ----------------------------------------- |
| **Claude Code**            | 필수      | Claude Max 구독 권장 (Opus 모델 사용)     |
| **Codex CLI**              | 선택      | 병렬 작업 위임 (없어도 Claude만으로 동작) |
| **tmux**                   | 선택      | Codex CLI 병렬 실행에 필요                |

> Claude Code만 있으면 모든 기능이 동작합니다. 외부 도구 의존성 없음.

### 사전 설치

```bash
# Codex CLI (선택)
npm install -g @openai/codex

# tmux (선택, macOS)
brew install tmux
```

---

## 설치

```bash
curl -fsSL https://raw.githubusercontent.com/kinkos1234/comad-voice/main/install.sh | bash
```

또는 수동 설치:

```bash
git clone https://github.com/kinkos1234/comad-voice.git
cd comad-voice
./install.sh
```

설치 스크립트가 하는 일:

1. `~/.claude/CLAUDE.md`에 Comad Voice 설정을 추가
2. 현재 프로젝트에 메모리 템플릿 복사 (선택)

---

## 사용법

### 1. "검토해봐" — 가장 쉬운 시작

프로젝트 폴더에서 Claude Code를 열고 이렇게만 말하세요:

```
검토해봐
```

Claude가 알아서:

1. 코드베이스를 분석하고
2. 개선 가능한 영역을 카드로 보여주고
3. 번호만 선택하면 자동으로 실험 루프를 돌립니다

### 2. "풀사이클" — 대주제 던지기

```
ComadEye의 리포트 품질을 전반적으로 개선해줘
```

6단계 파이프라인이 자동 실행:

```
RESEARCH → DECOMPOSE → EXPERIMENT → INTEGRATE → POLISH → DELIVER
```

### 3. 로컬 모델 대기 시간 활용

로컬 LLM 테스트가 돌아가는 동안:

```
이 대기 시간에 다음 실험 코드 미리 준비해줘
```

Claude가 백그라운드 실행 + 병렬 작업을 자동으로 관리합니다.

### 4. 세션 관리

긴 작업은 세션을 나눠서:

```
지금까지 결과 메모리에 저장하고 새 세션 시작하자
```

---

## 핵심 명령어 치트시트

| 하고 싶은 것     | 이렇게 말하세요                            |
| ---------------- | ------------------------------------------ |
| 현재 상태 진단   | "검토해봐", "어디가 문제야?"               |
| 대주제 자동 실행 | "풀사이클", "알아서 다 해줘"               |
| 실험 반복        | "실험해봐", "autoresearch"                 |
| 세션 저장        | "여기까지", "세션 끝", "저장해줘"          |
| 이어서 작업      | "이어서 해줘", "어디까지 했어?"            |
| 대기 시간 활용   | "다음 실험 미리 준비해줘"                  |
| 병렬 작업        | 자동 감지 (의존성 없는 작업을 알아서 위임) |
| 레포 꾸미기      | "광택", "repo polish", "레포 정리"         |
| 디자인 만들기    | "디자인해줘", "UI 만들어줘", "목업"        |
| 보안 점검        | "보안 점검", "보안 감사", "취약점"         |
| 사이트 테스트    | "QA해줘", "화면 확인", "사이트 테스트" ([qa.md](docs/qa.md))    |
| 코드 리뷰 군단  | "리뷰해줘", "코드 검토" ([review-army.md](docs/review-army.md)) |
| 배포하기         | "배포해줘", "라이브로", "프로덕션에"       |
| AI 세컨드 오피니언 | "다른 AI한테 물어봐", "세컨드 오피니언"  |

---

## 작동 원리

### Full-Cycle Pipeline

<p align="center">
  <img src="docs/images/slide-3-pipeline.png" alt="Full-Cycle Pipeline" width="800" style="max-width: 100%;">
</p>

```
사용자: "리포트 품질 개선해줘"
         ↓
[RESEARCH] 현재 코드 분석 + 관련 기술 리서치
         ↓
[DECOMPOSE] 서브태스크 분해 + 의존성 자동 판단
   🟢 독립 → Codex에 병렬 위임
   🔴 의존 → Claude가 순차 실행
   🟡 맥락 필요 → Claude가 직접
         ↓
[EXPERIMENT] 각 서브태스크별 autoresearch 루프
         ↓
[INTEGRATE] 최적 결과 병합 + 리팩토링
         ↓
[POLISH] 디자인 검수(T6) + 브라우저 QA(T8) + 보안 감사(T7) + 문서화
         ↓
[DELIVER] 배포 파이프라인(T9) + PR 생성 + 회고 + 학습 기록(T10)
```

### 의존성 자동 판단

비개발자가 "이건 독립적이야, 저건 의존적이야"를 판단할 필요 없습니다.
Claude가 5가지 기준으로 자동 분석합니다:

1. 파일 겹침이 있는가?
2. 다른 태스크가 만드는 함수를 쓰는가?
3. 다른 태스크의 출력을 입력으로 받는가?
4. 반드시 순서가 있는가?
5. 공유 상태를 변경하는가?

### 세션 메모리

긴 세션의 컨텍스트 오염을 방지합니다:

- 실험 5-7개마다 세션 교체 권장
- 중요한 결과는 자동으로 메모리 파일에 저장
- 새 세션에서 자동 복원

### 프로젝트 구조

```
comad-voice/
├── core/
│   ├── comad-voice.md          # 핵심 설정 (CLAUDE.md에 추가됨, 11개 트리거)
│   ├── design-palettes.md      # 디자인 레퍼런스 (9 팔레트 + 타이포/컬러 가이드)
│   └── triggers/
│       ├── t0-onboarding.md    # 첫 세션 온보딩
│       ├── t1-review.md        # "검토해봐" 트리거
│       ├── t2-fullcycle.md     # "풀사이클" 트리거
│       ├── t3-parallel.md      # 병렬 자동 감지
│       ├── t4-polish.md        # 레포 광택 트리거
│       └── t5-session-save.md  # 세션 저장 & 인수인계
├── memory-templates/           # 세션 메모리 템플릿
├── examples/
│   └── first-session.md        # 첫 세션 가이드
├── install.sh                  # 원클릭 설치 스크립트
└── tests/                      # bats 테스트 스위트
```

> T6-T10 트리거는 `core/comad-voice.md`에 직접 정의되어 있습니다.

---

## 실제 사용 사례

### 사례 1: 테스트 커버리지 개선

```
사용자: 검토해봐

Claude: 🔍 현재 상황 진단 결과

  카드 1: 테스트 커버리지 — 난이도 ⭐⭐ / 예상 효과 🔥🔥🔥
  현재 45% → 목표 80%. analysis/, api/, utils/ 모듈이 미커버.

  카드 2: 미머지 브랜치 — 난이도 ⭐ / 예상 효과 🔥🔥
  autoresearch/mar21 브랜치 7일째 방치.

  👉 어떤 카드를 먼저 진행할까요?

사용자: 1번

Claude: [autoresearch 루프 자동 시작]
  → 모듈별 테스트 작성 → 실행 → 실패 수정 → 반복
  → 결과: 45% → 94% (1,331 tests)
```

### 사례 2: 풀사이클 대주제

```
사용자: ComadEye의 리포트 품질을 전반적으로 개선해줘

Claude: [RESEARCH] 현재 리포트 구조 분석 중...
  → 6개 분석 공간, 내러티브 빌더, 리포트 생성기 파악

Claude: [DECOMPOSE] 5개 서브태스크로 분해:
  [S1] 🟢 엔티티 프로파일 개선 → Codex 위임
  [S2] 🟢 시나리오 서사 강화 → Codex 위임
  [S3] 🔴 렌즈 분석 깊이 확장 → Claude 직접 (S1 결과 의존)
  이대로 실행할까요?

사용자: 진행

Claude: [EXPERIMENT] S1, S2 병렬 실행 중... 대기 시간에 S3 코드 준비
  → [INTEGRATE] 최적 결과 병합 → [POLISH] QA 통과 → [DELIVER] PR 생성 완료
```

### 사례 3: 세션 이어서 작업

```
[이전 세션에서 실험 6개 진행 후]

사용자: 여기까지 저장하고 새 세션 시작하자

Claude: ✅ 메모리 저장 완료
  - experiments.md: 실험 6개 결과 요약
  - architecture.md: 아키텍처 결정 2건 기록
  → 새 세션에서 "이어서 해줘" 라고 말하면 자동 복원됩니다

[새 세션]

사용자: 이어서 해줘

Claude: 📋 이전 세션 복원 완료. 실험 7번부터 이어서 진행합니다.
```

---

## 문제 해결

### "검토해봐"가 작동하지 않아요

- `~/.claude/CLAUDE.md`에서 `COMAD-VOICE:START` 마커가 있는지 확인
- `cat ~/.claude/CLAUDE.md | grep COMAD-VOICE` 로 설치 확인

### 설치 스크립트가 실패해요

- `claude` CLI가 설치되어 있는지 확인: `which claude`
- 기존 CLAUDE.md 백업: `~/.claude/CLAUDE.md.bak.*` 에서 복원 가능

### Codex 병렬 위임이 안 돼요

- Codex CLI 설치 확인: `which codex`
- tmux 설치 확인: `which tmux`
- 이 기능은 선택 사항 — Codex 없이도 모든 기능 동작

---

## 크레딧

Comad Voice는 다음에서 영감을 받아 독립적으로 개발되었습니다:

- **autoresearch** 패턴 — 자율 실험 루프 (Andrej Karpathy 영감)
- **멀티 에이전트 오케스트레이션** — 역할 기반 에이전트 위임 패턴
- **안전 프로토콜** — 위험 명령 경고, 디버깅 원칙 등

> Comad Voice는 Claude Code만으로 완전히 독립 동작합니다. 외부 도구 의존성 없음.

### 영감

- [Andrej Karpathy — "Software in the era of AI"](https://www.youtube.com/watch?v=kwSVtQ7dziU)
  - Generation + Verification 루프
  - Autonomy Slider 개념
  - "부분적 자율성"으로 AI와 협업

---

## 기여하기

기여를 환영합니다! [CONTRIBUTING.md](CONTRIBUTING.md)를 참고해주세요.

---

## 라이선스

[MIT](LICENSE) - 자유롭게 사용, 수정, 배포할 수 있습니다.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=kinkos1234/comad-voice&type=Date)](https://star-history.com/#kinkos1234/comad-voice&Date)

---

<p align="center">
  <strong>Made with AI by Comad J</strong>
</p>
