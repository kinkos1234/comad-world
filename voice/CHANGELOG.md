# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-03-30

### Changed
- **외부 의존성 완전 내재화** — OMC/gstack 참조를 모든 파일에서 제거
- 풀사이클 파이프라인(T2)의 gstack 스킬 참조를 자체 설명으로 대체
- `core/comad-voice.md` 외부 도구 테이블에서 OMC/gstack 행 제거
- `install.sh` v2.1 — OMC/gstack 감지 로직 제거 (불필요한 출력 정리)
- README/README.en 필수 요구 사항에서 OMC/gstack 제거
- 모든 홍보 문서(docs/) 업데이트 — "OMC/gstack 필수" → "Claude Code만으로 독립 동작"

### Removed
- `install.sh`의 OMC/gstack 감지 블록
- `test_install.bats`의 "fails if OMC not detected" 테스트
- SECURITY.md의 OMC/gstack 의존 도구 참조

## [2.0.0] - 2026-03-25

### Added
- **T0 온보딩 트리거** — 첫 세션 자동 프로젝트 탐색 + `.comad/` 초기화
- **T5 세션 저장 트리거** — "여기까지", "저장해줘"로 작업 상태 저장 + 인수인계
- **5역할 시스템** — 탐색자/설계자/실행자/검토자/확인자 (Claude Code Agent tool 기반)
- **자동실험 루프 (Autoresearch)** — git keep/discard 패턴으로 자체 실험 프로토콜
- **안전 프로토콜** — 위험 명령 한국어 경고, 디버깅 3원칙, 프로덕션 감지
- **진행 상황 내레이션** — 모든 자동화 단계를 한국어로 실시간 보고
- **실험 내레이션** — 각 실험의 가설/변경/결과/판단을 사용자에게 보고
- **`.comad/` 상태 폴더** — 프로젝트별 독립 상태 관리

### Changed
- **OMC/gstack 의존성 제거** — 필수 → 선택 (있으면 활용, 없어도 동작)
- **Nexus 의존성 제거** — 풀사이클/병렬 로직을 Comad Voice 자체로 내재화
- 파이프라인 용어 한국어화 (RESEARCH→조사, DECOMPOSE→분해 등)
- `.omc/` 경로 → `.comad/` 경로로 독립
- `install.sh` v2.0 — OMC 미설치 시에도 정상 설치 가능
- T2 (풀사이클) 확장 — 내레이션 포함, 외부 스킬 참조 제거
- T3 (병렬) 확장 — Agent tool 기반 병렬 실행 방법 명시, `/pumasi` 참조 제거

### Removed
- OMC 필수 설치 요구 (`install.sh`에서 `exit 1` 제거)
- gstack 필수 설치 요구
- Nexus 트리거 중복 (`comad-voice.md`에서 Nexus 참조 전면 제거)
- 외부 스킬 슬래시 명령어 참조 (`/deep-research`, `/autoresearch`, `/pumasi`, `/team`)

## [1.1.0] - 2026-03-24

### Added
- 영어 README (`README.en.md`) + 한/영 언어 토글
- bats 테스트 스위트 (`tests/test_install.bats`) — 파일 구조, 설치 흐름 검증
- 트리거 모듈 분리 (`core/triggers/t1~t4`) — 개별 업데이트 가능
- CI에 bats 테스트 단계 추가

### Changed
- `install.sh` 견고성 대폭 개선
  - `set -euo pipefail` 적용
  - macOS/Linux 호환 `sed_inplace()` 함수
  - 타임스탬프 백업 (`CLAUDE.md.bak.YYYYMMDDHHMMSS`)
  - curl 다운로드 실패 검증 + 빈 파일 체크
  - cleanup trap으로 임시 파일 자동 정리
- 메모리 템플릿에 작성 가이드 + 구체적 예시 추가
- `core/comad-voice.md` 443줄 → 278줄로 축소 (T4 상세를 모듈로 분리)

## [1.0.0] - 2026-03-24

### Added
- 초기 릴리스
- "검토해봐" 트리거 — 코드베이스 자동 진단 + 개선 카드 제시
- "풀사이클" 트리거 — 6단계 자동 파이프라인 (RESEARCH → DELIVER)
- 멀티-AI 병렬 위임 — 5-Point 의존성 체크리스트로 Codex 자동 위임
- 세션 메모리 관리 — 컨텍스트 오염 방지 + 자동 메모리 기록
- 로컬 모델 대기 시간 활용 전략
- 원클릭 설치 스크립트 (`install.sh`)
- 메모리 템플릿 (MEMORY.md, experiments.md, architecture.md)
- 첫 세션 가이드 (`examples/first-session.md`)

### Credits
- oh-my-claudecode (OMC), gstack, autoresearch, pumasi, Nexus 위에 구축
- Andrej Karpathy "Software in the era of AI" 영감
