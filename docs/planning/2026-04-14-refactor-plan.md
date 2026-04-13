# Comad World 리팩토링 계획

## 1. 검토 요약

이번 검토는 `01-comad/comad-world` 루트와 주요 모듈 `brain`, `ear`, `eye`, `browse`, `create-comad`, `photo`, `sleep`, `voice`, 그리고 루트 운영 스크립트(`install.sh`, `scripts/*`)를 기준으로 진행했다.

현재 저장소는 "하나의 제품"처럼 소개되고 있지만, 실제 구조는 "여러 개별 프로젝트 + 운영 스크립트 + 실행 산출물 + 문서 + 데이터"가 한 곳에 겹쳐 있는 상태다. 이 때문에 설치, 업그레이드, 테스트, 릴리즈, 신규 기여 진입장벽이 모두 올라가 있다.

### 확인된 핵심 신호

- 저장소 크기가 약 `2.4G`이고, 그중 `eye`가 약 `2.0G`를 차지한다.
- `brain`, `ear`, `eye`, `photo`, `sleep`, `voice` 아래에 각각 `.git`이 존재하지만 루트에는 `.gitmodules`가 없다.
- 실행 산출물과 개발 환경이 저장소 안에 깊게 섞여 있다.
  - 예: `brain/data/`, `ear/archive/`, `ear/digests/`, `eye/.venv/`, `eye/__pycache__/`, `browse/.comad/`
- `eye`는 설정 파일이 이중 관리되고 있다.
  - `action_types.yaml` = `config/action_types.yaml`
  - `bindings.yaml` = `config/bindings.yaml`
  - `cmr.yaml` = `config/cmr.yaml`
- `eye`는 테스트가 사실상 이중 보관되고 있다.
  - `test_*.py` 와 `tests/test_*.py` 페어가 59쌍
  - 그중 58쌍이 동일 내용
- 루트의 "config-driven" 서사와 실제 구현 사이에 차이가 있다.
  - `scripts/apply-config.sh`는 실제로 `ear` 쪽만 생성한다.
- 패키징 방식이 모듈마다 다르다.
  - `brain`: Bun workspace
  - `eye`: Python + FastAPI + Next.js 혼합 구조
  - `browse`, `create-comad`: 독립 CLI
  - 루트: 설치/업그레이드/오케스트레이션 Bash

## 2. 현재 구조의 본질적 문제

### 2.1 저장소 경계가 모호함

지금 가장 큰 문제는 "이 저장소가 진짜 모노레포인지, 여러 리포를 묶은 메타 저장소인지"가 명확하지 않다는 점이다. 루트 README와 설치 흐름은 하나의 제품처럼 보이지만, 내부는 개별 Git 저장소처럼도 동작한다.

이 상태는 아래 문제를 만든다.

- 어떤 변경이 어디까지 영향 주는지 판단하기 어렵다.
- 업그레이드/롤백 정책이 코드 경계와 맞지 않는다.
- CI와 릴리즈 규칙을 일관되게 적용하기 어렵다.

### 2.2 소스와 산출물이 섞여 있음

런타임 데이터, 실험 결과, 캐시, 가상환경, node_modules, digest 산출물이 같은 트리에 있어 개발자 경험과 Git 위생이 무너진다.

이 상태는 아래 문제를 만든다.

- 저장소가 비대해진다.
- 실수로 산출물이 커밋되기 쉽다.
- 새 환경 셋업과 백업/복구 기준이 불분명해진다.

### 2.3 `eye`의 구조 중복이 심함

`eye`는 기능적으로 가장 큰 모듈이지만, 동시에 가장 먼저 정리해야 하는 모듈이기도 하다.

- 루트 모듈과 하위 패키지 명이 중복된다.
  - 예: `aggregator.py` / `analysis/aggregator.py`
  - 예: `loader.py` / `graph/loader.py`
  - 예: `propagation.py` / `simulation/propagation.py`
  - 예: `server.py` / `api/server.py`
- 설정 파일이 루트와 `config/`에 중복된다.
- 테스트가 루트와 `tests/`에 중복된다.

이 상태는 아래 문제를 만든다.

- import 경로와 진짜 책임 경계가 흐려진다.
- 리팩토링 시 삭제/이동 위험이 커진다.
- 테스트 실행 대상과 신뢰 가능한 테스트 집합이 불명확해진다.

### 2.4 운영 자동화가 루트 Bash에 과도하게 집중됨

`install.sh`, `scripts/comad`, `scripts/upgrade.sh`, `scripts/apply-config.sh`가 많은 책임을 가진다.

- 설치
- 상태 확인
- 업그레이드
- 백업/롤백
- 에이전트 배포
- 설정 생성

이 구조는 초기 속도는 빠르지만, 규모가 커지면 유지보수가 급격히 어려워진다.

### 2.5 문서, 제품 서사, 실제 구조가 완전히 일치하지 않음

현재 문서는 강하고 설득력이 있지만, 실제 폴더/설치/업그레이드/구성 경계와 1:1로 맞물리지는 않는다. 장기적으로는 문서보다 코드가 진실의 원천이 되게 만들어야 한다.

## 3. 권장 방향

### 권장안: "진짜 모노레포"로 정리

현재 루트 제품 경험이 이미 하나의 통합 시스템을 전제로 하고 있으므로, 가장 자연스러운 방향은 **명시적인 모노레포로 재정의**하는 것이다.

즉, 다음을 분명히 해야 한다.

- 루트가 진짜 소스 오브 트루스다.
- 하위 `.git` 저장소는 제거하거나 이관한다.
- 모듈은 루트 워크스페이스/패키지 경계 안에서 관리한다.
- 실행 산출물은 루트 밖 또는 명확한 `state/` 아래로 이동한다.

### 대안안: "메타 저장소 + 정식 서브모듈"

만약 각 모듈의 독립 배포/독립 공개/독립 이력 관리가 핵심이라면, 반대로 루트를 메타 저장소로 축소하고 Git submodule/subtree를 공식화하는 쪽이 낫다.

다만 현재 README, 설치기, 업그레이더, 글로벌 `comad` 명령의 방향성을 보면 이 대안보다 **모노레포 정리안이 더 일관적**이다.

## 4. 리팩토링 목표

이번 리팩토링의 목표는 "예쁘게 폴더 정리"가 아니라 아래 다섯 가지다.

1. 저장소 경계를 명확히 한다.
2. 소스와 산출물을 분리한다.
3. 각 모듈에 단일한 canonical 경로를 만든다.
4. 설정과 설치/업그레이드 계약을 코드로 고정한다.
5. CI와 릴리즈가 구조를 강제하게 만든다.

## 5. 단계별 실행 계획

## Phase 0. 경계 결정과 기준선 확보

### 해야 할 일

- 저장소 전략을 확정한다.
  - 권장: 모노레포
  - 대안: 메타 저장소 + 정식 서브모듈
- 현재 동작 기준선을 저장한다.
  - 루트 설치 플로우
  - `brain` 기본 crawl + MCP 실행
  - `eye` 기본 API/프론트 실행
  - `comad status`, `comad upgrade --dry-run`
- "소스 / 샘플 / 픽스처 / 사용자 상태 / 런타임 산출물" 분류표를 작성한다.

### 산출물

- ADR 1개: 저장소 모델 결정 문서
- 기준선 체크리스트 1개

### 완료 기준

- 팀이 "이 저장소는 무엇인가?"를 한 문장으로 설명할 수 있다.
- 이후 단계에서 디렉터리 이동이 생겨도 동작 기준을 비교할 수 있다.

## Phase 1. 저장소 위생 정리

### 해야 할 일

- Git에서 런타임/로컬 산출물을 완전히 분리한다.
- 아래 항목은 원칙적으로 추적 대상에서 제거한다.
  - `node_modules/`
  - `.venv/`
  - `__pycache__/`
  - `.pytest_cache/`
  - `.tsbuildinfo`
  - `brain/data/`의 실운영 결과물
  - `ear/archive/`, `ear/digests/`의 실운영 산출물
  - `data/`의 날짜별 score/benchmark 결과
- 남겨야 하는 데이터는 `fixtures/`, `examples/`, `docs/assets/`처럼 의도를 드러내는 위치로 옮긴다.
- 정리용 명령을 추가한다.
  - 예: `just clean`, `make clean`, `scripts/clean-runtime.sh`
- CI에서 산출물 누수를 차단한다.

### 산출물

- 정리된 `.gitignore`
- 데이터/산출물 배치 규칙
- cleanup 스크립트

### 완료 기준

- 새 클론 후 저장소 크기가 급격히 줄어든다.
- 런타임 실행 전후에도 Git 상태가 쉽게 더러워지지 않는다.

## Phase 2. `eye` 구조 정리

가장 먼저 구조적 효과가 크게 나는 구간이다. 이 단계는 별도 스프린트로 보는 것이 좋다.

### 해야 할 일

- `eye`의 Python 코드를 하나의 canonical 패키지 루트로 통합한다.
  - 권장 예시: `eye/src/comad_eye/` 또는 `eye/comad_eye/`
- 기능 기준 하위 패키지로 재배치한다.
  - `analysis`
  - `api`
  - `graph`
  - `ingestion`
  - `narration`
  - `ontology`
  - `pipeline`
  - `simulation`
  - `shared`
- 루트 중복 모듈은 얇은 호환 레이어를 거쳐 순차 제거한다.
- 설정 파일은 `eye/config/`만 남기고 루트 중복본은 제거한다.
- 테스트는 `eye/tests/`만 canonical로 남긴다.
  - 루트 `test_*.py`는 제거
  - 중복 59쌍 중 동일한 58쌍은 우선 정리 대상
- 프론트엔드 위치를 명확히 한다.
  - `eye/app`와 `eye/frontend`가 함께 존재하는 구조는 장기적으로 혼란을 만든다.
  - 한 곳을 canonical frontend 엔트리로 정하고 나머지는 제거 또는 병합한다.

### 권장 순서

1. config 중복 제거
2. tests canonical화
3. import 경로 정리
4. 모듈 이동
5. frontend 경계 정리

### 산출물

- 정리된 `eye` 폴더 트리
- import 규칙
- 단일 테스트 진입점

### 완료 기준

- 같은 개념이 두 경로에 있지 않다.
- 신규 개발자가 `eye`의 진입점과 패키지 경계를 5분 안에 파악할 수 있다.

## Phase 3. 루트 설정/오케스트레이션 재설계

### 해야 할 일

- `comad.config.yaml`의 역할을 재정의한다.
  - 지금처럼 "설명상 전체 시스템 설정"이 아니라
  - 실제로 어떤 모듈이 어떤 값을 읽는지 계약을 명시한다.
- 설정 스키마를 코드로 고정한다.
  - TypeScript 쪽은 `zod`
  - Python 쪽은 `pydantic`
  - 공통 배포용은 JSON Schema
- `scripts/apply-config.sh`를 템플릿 기반 생성기로 정리한다.
  - 현재는 사실상 `ear` 전용 생성기다.
- 설치/업그레이드 로직을 함수 단위로 분리한다.
  - `scripts/lib/common.sh`
  - `scripts/lib/git.sh`
  - `scripts/lib/runtime.sh`
  - `scripts/lib/agents.sh`
- 가능하면 루트 작업 진입점을 하나로 통일한다.
  - `just` 권장
  - 대안: `Makefile`

### 산출물

- 설정 계약 문서
- 검증 가능한 config loader
- 모듈화된 스크립트 구조

### 완료 기준

- README의 "config-driven" 설명과 실제 코드가 일치한다.
- 설정 변경이 어떤 파일을 재생성하고 어떤 모듈에 영향을 주는지 자동으로 알 수 있다.

## Phase 4. 모듈 패키징 규칙 통일

### 해야 할 일

- `brain`, `browse`, `create-comad`, `sleep`, `voice`의 패키징 규칙을 맞춘다.
- 최소한 아래 항목은 공통 규칙을 가진다.
  - 엔트리포인트 위치
  - README 구조
  - 환경변수 이름
  - 실행/테스트 명령
  - 버전 표기
- `brain`은 현재 workspace 구조가 비교적 선명하므로 유지하되, 루트 오케스트레이션과의 경계만 더 분명히 한다.
- `browse`, `create-comad`는 `tools/` 아래로 이동하는 것이 자연스럽다.
- `ear`, `photo`, `sleep`, `voice`는 코드 모듈인지 에이전트 자산인지 성격을 명확히 나눈다.

### 예시 목표 구조

```text
comad-world/
  apps/
    eye-web/
  services/
    brain/
    eye-api/
  agents/
    ear/
    photo/
    sleep/
    voice/
  tools/
    browse/
    create-comad/
  packages/
    config-contract/
    shared-shell/
    shared-ts/
    shared-py/
  docs/
  examples/
  state/        # gitignored
```

### 완료 기준

- 모듈마다 폴더 구조를 다시 학습하지 않아도 된다.
- 신규 모듈을 추가할 때 어디에 둬야 할지 자연스럽다.

## Phase 5. 문서와 CI를 구조의 감시자로 만들기

### 해야 할 일

- 아키텍처 문서를 하나의 상위 문서 + 모듈별 세부 문서로 재구성한다.
- README는 제품 소개에 집중하고, 운영/개발/아키텍처 문서는 분리한다.
- CI를 "테스트 실행기"가 아니라 "구조 유지 장치"로 확장한다.

### CI에 추가할 항목

- duplicate-file guard
- generated-artifact guard
- config schema validation
- changed-path 기반 테스트 실행
- install/upgrade smoke test

### 완료 기준

- 구조가 다시 무너지려 하면 CI가 바로 잡아준다.
- 문서가 실제 경계를 따라간다.

## 6. 우선순위 제안

아래 순서로 진행하는 것을 권장한다.

1. 저장소 전략 결정
2. 산출물/캐시/환경 디렉터리 정리
3. `eye` 중복 제거
4. config 계약과 루트 스크립트 정리
5. 모듈 패키징 통일
6. 문서/CI 정비

핵심은 **큰 구조 결정 없이 파일 이동부터 시작하지 않는 것**이다.  
지금은 "정리"보다 먼저 "경계 선언"이 필요하다.

## 7. 바로 시작하기 좋은 Quick Wins

리스크가 낮고 효과가 큰 작업부터 시작하면 다음과 같다.

1. `eye`의 중복 설정 파일 제거
2. `eye`의 루트 테스트를 `tests/`로 단일화
3. `eye/.venv`, `eye/__pycache__`, `brain/node_modules`, `browse/.comad` 등 로컬 산출물 정리
4. `brain/data`, `ear/archive`, `ear/digests`, 루트 `data/`를 "샘플"과 "실운영 상태"로 분리
5. 루트에 `justfile` 또는 `Makefile` 추가해 공통 명령 진입점 정리

## 8. 하지 말아야 할 것

- 한 번에 모든 모듈을 재배치하는 빅뱅 리팩토링
- 테스트 체계 정리 전 대규모 import 경로 변경
- 루트/하위 Git 경계 결정을 미룬 채 폴더만 옮기는 작업
- 운영 산출물과 예제 데이터를 다시 같은 폴더에 섞는 것

## 9. 결론

Comad World는 이미 기능적으로는 꽤 많은 것을 해내고 있고, 각 모듈의 문제도 "기능 부족"보다는 "경계와 구조의 불명확성"에 더 가깝다.

따라서 이번 리팩토링은 새 기능 추가보다 아래 두 줄에 집중하는 것이 좋다.

- **이 저장소의 진짜 경계를 다시 정의한다.**
- **중복과 산출물을 제거해 구조가 스스로 설명되게 만든다.**

그 시작점으로는 `eye` 중복 제거와 저장소 위생 정리가 가장 효율적이다.
