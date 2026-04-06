### T2. 풀사이클 / 대주제 요청 감지

**감지 키워드:** "풀사이클", "full-cycle", "대주제", "이거 통째로", "알아서 다 해줘", "end-to-end로", "처음부터 끝까지", or broad topic without specific file/function targets

**실행:** 6-Stage 풀사이클 파이프라인

```
조사 -> 분해 -> 실험 -> 통합 -> 다듬기 -> 전달
RESEARCH -> DECOMPOSE -> EXPERIMENT -> INTEGRATE -> POLISH -> DELIVER
```

### Stage 1: 조사 (RESEARCH)
- 대주제의 기술 환경 파악 (웹 검색 + 코드베이스 탐색)
- 탐색자(haiku) 에이전트로 기존 코드 구조 파악
- 제품 리프레이밍: "진짜 문제가 뭔가?", "누가 왜 쓰는가?", "지금 대안은?" 등 강제 질문으로 핵심 파악
- 산출물: `.comad/research/topic-landscape.md`
- **내레이션**: "[조사 단계] 시작합니다 — 기술 환경을 파악합니다."

### Stage 2: 분해 (DECOMPOSE)
- 설계자(opus) 에이전트로 서브주제 3-5개 도출
- 각 서브주제에 측정 가능한 메트릭 부여
- 5-Point Checklist로 의존성 자동 판단 (T3 참조)
- 산출물: `.comad/plans/decomposition.md`
- **내레이션**: "[분해 단계] 서브태스크 N개로 나눴습니다. 독립 M개, 의존 K개."

**decomposition.md 형식:**

```markdown
## 서브태스크 분해

### [S1] 태스크명 — 독립 -> 병렬 실행
- 설명: ...
- 메트릭: ...
- 수정 파일: file_a.py, file_b.py
- 의존: 없음

### [S2] 태스크명 — 의존 -> 순차 실행
- 설명: ...
- 메트릭: ...
- 수정 파일: file_a.py, file_d.py (S1과 겹침)
- 의존: S1 완료 후 실행

## 실행 계획
- 병렬 1차: S1(에이전트A) + S3(에이전트B)
- 순차 2차: S2(S1 완료 후)
```

### Stage 3: 실험 (EXPERIMENT)
- 각 서브주제마다 자동실험 루프 실행
- 독립적 서브주제 -> Agent tool로 병렬 에이전트 생성하여 동시 실험
- 의존적 서브주제 -> 순차 체이닝
- 실험마다 git commit으로 keep/discard
- 산출물: 각 서브주제별 `experiment-log.md` + 최적 결과 커밋
- **내레이션**: 각 실험마다 가설/변경/결과/판단 보고

### Stage 4: 통합 (INTEGRATE)
- 최적 결과를 하나로 병합
- 검토자 에이전트로 코드 리뷰 + 중복 제거 + 리팩토링
- 구조적 검토: SQL 안전성, 신뢰 경계, 조건부 부작용, 보안 취약점 등
- 테스트 추가
- 산출물: 통합된 클린 코드 + 테스트
- **내레이션**: "[통합 단계] 실험 결과를 하나로 합치고 있습니다."

### Stage 5: 다듬기 (POLISH)
- 웹/UI: 디자인 일관성 점검 + 주요 흐름 수동/자동 QA
- 비-UI: 성능 최적화 + 코드 리뷰
- 문서화: README, ARCHITECTURE 등 프로젝트 문서 자동 동기화
- 산출물: 성능 벤치마크, 최종 문서
- **내레이션**: "[다듬기 단계] 품질 점검 + 문서화 진행 중."

### Stage 6: 전달 (DELIVER)
- PR 생성 자동화: base 브랜치 머지, 테스트 실행, diff 리뷰, 버전 범프
- CHANGELOG 업데이트 + GitHub Release
- 스프린트 회고: 커밋 분석, 패턴 추적, 교훈 기록
- 산출물: PR, CHANGELOG, 회고 기록
- **내레이션**: "[전달 단계] PR을 만들고 마무리합니다."
