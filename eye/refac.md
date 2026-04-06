# ComadEye 리팩토링 제안서

## 1. 목적

현재 시스템은 시드 텍스트를 온톨로지적으로 구조화하고 시뮬레이션한 뒤 예측 보고서를 생성하는 흐름은 갖추고 있다. 다만 입력이 길어질수록 다음 문제가 반복된다.

- 추출 단계 LLM 호출이 길어지면서 timeout 또는 연결 끊김이 발생
- 한 단계 실패가 전체 파이프라인 실패로 이어짐
- 사용자는 긴 입력이 위험한지 사전에 알 수 없음
- 진행 상황은 보이지만 어느 지점에서 왜 느린지, 무엇을 줄여야 하는지 보이지 않음

이 문서는 현재 코드 구조를 기준으로 사용성과 성능을 동시에 개선하는 리팩토링 방향을 정리한다.

## 2. 현재 구조 기준 진단

### 2.1 실제 병목

코드상 긴 입력에 가장 취약한 구간은 `ingestion/extractor.py`, `graph/summarizer.py`, `narration/report_generator.py`, `utils/llm_client.py`다.

- `ingestion/chunker.py`
  - 600 토큰 / 100 오버랩으로 고정 청킹
  - 청킹은 되지만, 이후 단계가 "길어진 전체 맥락"을 계속 다시 먹는 구조를 억제하지 못함
- `ingestion/extractor.py`
  - 청크 2개씩 묶어 LLM 호출
  - 호출 실패 시 배치 전체를 버리고 다음 배치로 넘어감
  - 엔티티/관계 추출과 후속 관계 재추출이 모두 LLM 의존
  - 배치별 결과 저장, 재개, 캐시가 없음
- `graph/summarizer.py`
  - 여러 커뮤니티를 하나의 프롬프트로 합쳐 1회 요약
  - 입력이 커질수록 커뮤니티 요약 단계도 불안정해짐
- `narration/report_generator.py`
  - 리포트 자체는 구조적이지만 제목/부제/해석 문단 생성이 여전히 LLM 중심
  - 긴 분석 결과가 들어오면 서술 품질보다 응답 안정성이 먼저 깨질 수 있음
- `utils/llm_client.py`
  - 재시도는 있으나, 프롬프트 축소/강등/부분 복구 전략이 없음
  - timeout 이후 동일한 큰 요청을 다시 보내 비용만 늘어남

### 2.2 운영 로그 기준 징후

로그 기준으로 이미 긴 추론의 징후가 명확하다.

- 평균 LLM 호출 시간: 약 17.9초
- p95: 약 52.7초
- 최대: 약 82.9초
- 실제 오류: `timed out`, `Server disconnected`, `Connection refused`

즉 문제는 "긴 입력을 처리할 수 없는 모델"이 아니라, "긴 입력이 들어왔을 때 요청 크기와 처리 단위를 제어하지 못하는 파이프라인 설계"에 가깝다.

### 2.3 UX 관점 문제

현재 `frontend/app/new/page.tsx`와 `api/routes/pipeline.py` 기준으로는 다음 문제가 있다.

- 입력 길이에 대한 경고가 없음
- 토큰 예상치, 예상 소요시간, 비용성 단계가 보이지 않음
- 긴 입력일수록 자동으로 더 안전한 모드로 전환되지 않음
- 실패 후 재시작 시 이전 성공 단계 재사용이 어려움
- 진행 화면은 stage 단위 상태만 보여주고, 청크/배치 단위 진행률은 보여주지 않음

## 3. 리팩토링의 핵심 방향

핵심 방향은 한 줄로 정리하면 다음과 같다.

> "전체 입력을 한 번에 이해시키는 구조"에서 "작은 단위로 추출하고, 구조화된 중간 산출물을 누적 병합하는 구조"로 바꿔야 한다.

즉 아래 4가지를 먼저 확보해야 한다.

1. 입력 사전 진단
2. 단계별 분할 처리
3. 중간 결과 영속화 및 재시도 가능성
4. 사용자에게 현재 위험도와 진행률을 설명하는 UX

## 4. 권장 아키텍처 변경

### 4.1 Preflight 단계 추가

`run_pipeline` 시작 전에 `preflight` 단계를 추가하는 것을 권장한다.

이 단계에서 수행할 일:

- 문자 수, 문장 수, 예상 토큰 수 계산
- 섹션 경계 탐지
- 표/목록/참고자료/잡음 구간 식별
- 안전 모드 자동 선택

추천 출력:

```json
{
  "chars": 58231,
  "estimated_tokens": 14320,
  "sections": 27,
  "risk_level": "high",
  "recommended_mode": "hierarchical",
  "expected_batches": 19
}
```

이 정보를 사용자에게 먼저 보여주면 긴 입력에 대한 사용성이 크게 올라간다.

### 4.2 Ingestion을 3계층 파이프라인으로 재구성

현재는 청크 -> 추출 -> 병합에 가깝다. 이를 다음처럼 바꾸는 것이 좋다.

#### A. Segment Layer

문서 전체를 먼저 의미 단위로 나눈다.

- 제목/소제목
- 단락
- 표/리스트
- 출처/부록

이 계층의 목적은 단순 토큰 청킹보다 "문맥 단위 보존"이다.

#### B. Chunk Extraction Layer

각 segment를 다시 토큰 예산 기준으로 청킹하고, 각 청크에서 아래만 추출한다.

- local entities
- local relations
- local events
- local claims

여기서는 청크 단위 JSON만 만든다. 청크 간 전역 정합성은 요구하지 않는다.

#### C. Reduce / Merge Layer

청크 결과들을 병합하여 전역 온톨로지를 만든다.

- 이름 정규화
- 동의어 병합
- 관계 중복 통합
- 엔티티 canonicalization
- cross-chunk relation completion

이 구조로 바꾸면 긴 입력의 복잡성이 LLM 호출 크기로 전이되지 않고, reducer의 병합 복잡성으로 이동한다. 이게 맞는 방향이다.

### 4.3 Community Summary와 Report도 Map-Reduce화

현재 `graph/summarizer.py`는 다수 커뮤니티를 한 번에 요약한다. 이를 아래처럼 바꾼다.

- 커뮤니티별 독립 요약
- 커뮤니티 요약 캐시
- 최종 리포트에서는 커뮤니티 요약 일부만 선택 사용

리포트도 동일하다.

- 제목/부제 생성은 마지막에 1회
- 섹션 서술은 공간별 독립 생성
- 실패 시 해당 섹션만 템플릿 fallback

즉 "전체 리포트 생성 실패"가 아니라 "섹션 n만 fallback" 구조여야 한다.

## 5. 구체 리팩토링 항목

### 5.1 LLM 요청 제어 계층 신설

`utils/llm_client.py` 위에 `LLMTaskRunner` 같은 오케스트레이터 계층을 두는 것이 좋다.

권장 책임:

- 요청 타입별 토큰 예산 관리
- timeout 프로파일 분리
- 재시도 전 프롬프트 축소
- JSON schema validation
- 부분 실패 fallback
- 디스크 캐시
- idempotency key

예시 정책:

- extraction: 작은 청크, 낮은 temperature, 엄격 JSON
- summary: 중간 크기, timeout 짧게
- report_title: 매우 짧은 prompt
- report_section: section별 독립 호출

### 5.2 배치 결과 저장 방식 변경

현재는 최종 산출물 위주다. 긴 입력 대응을 위해 아래 중간 파일을 명시적으로 저장해야 한다.

- `data/extraction/segments.jsonl`
- `data/extraction/chunk_tasks.jsonl`
- `data/extraction/chunk_results/{chunk_id}.json`
- `data/extraction/merge_candidates.json`
- `data/extraction/failures.jsonl`

효과:

- 실패한 청크만 재시도 가능
- 동일 입력 재실행 시 캐시 재사용 가능
- 어느 청크가 병목인지 추적 가능

### 5.3 Deduplicator 고도화

현재 `ingestion/deduplicator.py`는 문자열 유사도 중심이다. 긴 입력일수록 동일 엔티티의 표현 변형이 늘어나므로 다음이 필요하다.

- alias 테이블 도입
- 임베딩 기반 병합 후보 생성
- object_type 제약 기반 병합
- 사람이 읽을 수 있는 merge decision log 저장

추천 구조:

1. exact normalize
2. alias dictionary
3. embedding candidate top-k
4. conservative merge
5. ambiguous merge는 보류

긴 입력에서 가장 위험한 것은 누락보다 과병합이다. 따라서 "조심스럽게 덜 합치는" 쪽이 맞다.

### 5.4 ReportGenerator의 컨텍스트 축소

`narration/report_generator.py`는 이미 구조적 템플릿 성향이 강하므로 조금만 더 밀어주면 안정성이 크게 좋아진다.

권장 변경:

- 제목/부제도 LLM 실패 시 deterministic 템플릿 생성
- 각 섹션에 넣는 분석 JSON을 미리 압축
- 해석 문단 생성 입력을 `top findings + 근거 수치 + 관련 엔티티 3~5개`로 제한
- 긴 분석 raw JSON 전체를 넘기지 않음

즉 LLM에는 "분석 결과 전체"가 아니라 "서술용 digest"만 보내야 한다.

### 5.5 API 레벨 입력 모드 추가

`api/models.py`의 `RunPipelineRequest`에 다음 옵션을 추가하는 것을 권장한다.

- `ingestion_mode`: `auto | fast | balanced | robust`
- `max_input_tokens`
- `allow_partial_report`
- `resume_from_cache`

`auto`일 때는 preflight 결과로 모드를 자동 선택한다.

예시:

- `fast`: 샘플링 기반, 빠른 초안
- `balanced`: 현재 기본
- `robust`: 긴 입력용, 작은 청크 + 강한 캐시 + 부분 리포트 허용

## 6. 사용성 개선안

### 6.1 입력 화면

`frontend/app/new/page.tsx`에 아래를 추가하는 것이 좋다.

- 입력 글자 수 / 예상 토큰 수 실시간 표시
- 위험도 배지: low / medium / high
- 추천 실행 모드 자동 선택
- 긴 입력일 경우 "참고자료/부록 제외" 체크박스
- 파일 업로드 후 섹션 자동 감지 결과 미리보기

이렇게 해야 사용자가 긴 입력을 그냥 던지고 실패를 기다리는 구조에서 벗어난다.

### 6.2 진행 화면

`frontend/app/run/page.tsx`는 stage 상태만 보여준다. 긴 입력에서는 이것만으로 부족하다.

추가 권장 항목:

- 총 청크 수 / 완료 청크 수
- 실패 청크 수 / 재시도 수
- 현재 처리 중 segment 제목
- 현재 사용 중 모드
- 예상 남은 시간
- 부분 리포트 가능 여부

즉 "INGESTION 진행 중"이 아니라 "총 42개 청크 중 17개 완료, 2개 재시도 중"이 보여야 한다.

### 6.3 실패 복구 UX

실패 시 아래 선택지를 제공해야 한다.

- 실패 청크만 재시도
- robust 모드로 재실행
- report 없이 analysis까지만 완료
- 부분 리포트 생성

이건 엔지니어링보다 UX 개선 효과가 더 크다.

## 7. 성능 개선안

### 7.1 가장 먼저 할 것

아래는 효과 대비 구현 비용이 낮다.

1. preflight 토큰 추정
2. chunk 결과 캐시
3. 실패 청크만 재시도
4. report section별 독립 생성
5. community summary 분할 호출

이 5개만 해도 긴 입력 실패율은 크게 낮아질 가능성이 높다.

### 7.2 병렬화는 신중하게

병렬화는 무조건 좋은 것이 아니다. 로컬 Ollama 환경에서는 오히려 연결 실패를 늘릴 수 있다.

추천 방식:

- 기본은 직렬
- 작은 청크에 한해서 제한적 병렬화
- 동시 실행 수는 2 이하
- 모델 상태가 불안정하면 자동으로 직렬 강등

즉 병렬화보다 "작은 요청 + 재개 가능성"이 먼저다.

### 7.3 프롬프트 축소 전략

timeout 재시도 전에 동일 프롬프트를 그대로 보내지 말고 자동 축소해야 한다.

예:

1. 원본 요청
2. 설명 필드 제거
3. object_types 추출 생략
4. entities only 추출
5. 관계는 후속 단계에서 재구성

이런 degrade 전략이 있으면 실패 시 전체 중단을 피할 수 있다.

### 7.4 컨텍스트 윈도우 의존성 축소

`num_ctx`를 키우는 방식은 임시 처방이다. 긴 입력 대응의 본질은:

- 한 호출당 정보량을 줄이고
- 중간 구조를 누적 저장하고
- reducer에서 전역 일관성을 맞추는 것

즉 더 큰 모델이나 더 큰 context를 전제로 설계를 계속 밀면 운영 안정성이 떨어진다.

## 8. 추천 구현 순서

### Phase 1. 안정화

- preflight 단계 추가
- chunk 결과 캐시 추가
- 배치 실패 시 skip이 아니라 retry queue로 이동
- report/community 요약 분할
- deterministic fallback 추가

### Phase 2. 구조화

- segment -> chunk -> merge 3계층 ingestion 도입
- dedup 개선
- section digest 기반 report generation 도입
- job resume 지원

### Phase 3. UX 고도화

- 입력 위험도 안내
- chunk 진행률/ETA 표시
- 부분 결과 열람
- 실패 후 부분 재실행

### Phase 4. 최적화

- 선택적 병렬화
- 캐시 hit율 최적화
- prompt budget 정책 튜닝
- 모델별 프로파일 분리

## 9. Multi-Agent 적용에 대한 판단

### 9.1 결론

이 시스템을 전면적인 AI agent 구조로 바꾸는 것은 성능 개선의 정답이 아니다. 현재 구조에서는 잘못 적용하면 오히려 더 느려지고 더 불안정해질 가능성이 높다.

이유는 명확하다.

- 현재 코어 병목은 `simulation`이나 `analysis`가 아니라 LLM 기반 `추출/요약/서술` 구간이다
- agent를 늘리면 agent 간 메시지 전달과 중복 컨텍스트 비용이 생긴다
- 긴 입력 문제는 "지능 부족"보다 "처리 단위 설계 부족"에 가깝다

따라서 방향은 "모든 구성요소를 AI agent화"가 아니라, "긴 입력에 취약한 일부 구간만 제한된 작업자(agent-like worker) 구조로 재편"이 맞다.

### 9.2 전면 Agent화가 불리한 이유

다음과 같은 naive multi-agent 구조는 권장하지 않는다.

- 추출 agent
- 요약 agent
- 검토 agent
- 보고서 agent

이들이 자연어 대화로 서로 결과를 전달하는 방식

이 방식의 예상 결과:

- 지연시간 증가
- 토큰 사용량 증가
- 실패 지점 증가
- 동일 온톨로지의 중복 해석 증가
- 전역 일관성 저하

즉 현재 문제인 긴 입력 실패를 해결하기보다, 긴 입력을 여러 agent가 반복해서 읽는 구조가 되기 쉽다.

### 9.3 제한적 Multi-Agent는 유효할 수 있음

다만 다음 조건을 만족하면 제한적 multi-agent 구조는 의미가 있다.

- agent 역할이 매우 좁다
- 각 agent 출력이 자유 텍스트가 아니라 JSON schema다
- agent 간 전달 단위가 전체 문맥이 아니라 digest다
- 전역 정합성은 마지막 reducer/validator가 담당한다

이 경우 multi-agent는 사실상 "계층형 분산 파이프라인"으로 동작한다. 이 형태는 긴 입력 대응 안정성을 높이는 데 유리하다.

### 9.4 이 시스템에 맞는 권장 구조

권장 구조는 아래와 같다.

1. `Preflight Agent`
   - 입력 길이, 토큰 추정, 위험도, 권장 모드 판정
2. `Segmentation Agent`
   - 문서를 섹션/단락/표/참고자료 단위로 분해
3. `Chunk Extraction Workers`
   - 각 청크에서 엔티티/관계/이벤트/클레임 추출
4. `Ontology Merge Agent`
   - canonical entity, alias, merge candidate 생성
5. `Validation Agent`
   - 누락 관계, 충돌 엔티티, 스키마 위반 검증
6. `Report Planner Agent`
   - 분석 결과를 section digest로 축소

중요한 점은 `simulation`과 `analysis`는 agent화하지 않는 것이다.

- `simulation`은 지금처럼 규칙 기반 엔진이 더 빠르고 일관적이다
- `analysis`도 지금처럼 알고리즘 기반이 더 저렴하고 재현 가능하다

즉 AI agent는 Layer 0과 Layer 4 일부에만 제한적으로 적용해야 한다.

### 9.5 예상 성능 변화

제약된 multi-agent 구조를 도입했을 때 예상되는 변화는 다음과 같다.

#### 좋아질 가능성이 큰 항목

- 긴 입력 성공률
- 실패 후 부분 재시도 가능성
- 어느 단계에서 병목이 생기는지에 대한 관찰성
- 일부 섹션만 fallback 처리하는 복원력

#### 나빠질 가능성이 큰 항목

- 총 처리시간
- 총 토큰 사용량
- 오케스트레이션 복잡도
- 개발 및 운영 난이도

즉 성능을 하나의 숫자로 보면 무조건 좋아지지 않는다. 대신 아래 트레이드오프가 생긴다.

- `속도`: 대체로 하락
- `안정성`: 상승 가능
- `비용`: 대체로 상승
- `디버깅 가능성`: 상승

### 9.6 추천 여부

이 프로젝트에는 아래 방식을 권장한다.

- 전체 시스템을 multi-agent로 재설계: 비추천
- ingestion/report 일부만 constrained multi-agent화: 추천
- ontology/simulation/analysis 코어는 현재 구조 유지: 강하게 추천

즉 이 시스템의 이상적인 형태는 "multi-agent 제품"이 아니라 아래에 가깝다.

> 규칙 기반 코어 위에, 긴 입력을 잘게 나누고 전달하는 소수의 schema-constrained 작업자 계층을 얹은 hybrid 구조

### 9.7 구현 시 원칙

multi-agent 성격의 구조를 도입한다면 다음 원칙을 지켜야 한다.

- agent 간 자연어 대화 금지
- agent 출력은 항상 schema 검증
- 전체 문서 원문 전달 금지, digest만 전달
- 전역 일관성 판단은 최종 merge/validator 한 곳에서 수행
- 실패한 worker만 재실행 가능해야 함
- 최종 report는 section 단위로 독립 fallback 가능해야 함

이 원칙이 깨지면 multi-agent는 성능 개선이 아니라 성능 악화 요인이 된다.

## 10. 측정 지표

리팩토링 후 다음 지표를 반드시 수집해야 한다.

- 입력 토큰 수별 성공률
- stage별 평균 시간
- chunk당 평균 추론 시간
- retry 비율
- cache hit 비율
- partial fallback 발생 비율
- report 생성 성공률
- 사용자 이탈률: 실행 시작 후 실패/중단 비율

최소 목표:

- 긴 입력(high risk) 성공률 90% 이상
- 동일 입력 재실행 시간 50% 이상 단축
- LLM timeout 후 전체 job 실패율 50% 이상 감소

## 11. 제안하는 코드 단위 작업 목록

### 백엔드

- `utils/preflight.py` 추가
- `utils/llm_task_runner.py` 추가
- `ingestion/segmenter.py` 추가
- `ingestion/extractor.py`를 chunk task 기반으로 개편
- `ingestion/deduplicator.py`에 alias/embedding 병합 후보 추가
- `graph/summarizer.py`를 community별 분할 처리로 개편
- `narration/report_generator.py`를 section digest 기반으로 개편
- `api/routes/pipeline.py`에 preflight, resume, partial result 로직 추가
- `api/models.py`에 robust mode 관련 필드 추가

### 프런트엔드

- `frontend/app/new/page.tsx`에 입력 토큰 추정 및 위험도 표시
- `frontend/app/run/page.tsx`에 chunk 진행률, ETA, retry 수 표시
- 실패 시 재시도 옵션 UI 추가

## 12. 결론

현재 시스템의 핵심 문제는 온톨로지나 시뮬레이션 로직보다, 긴 입력을 작은 처리 단위로 안정적으로 분해하고 다시 합치는 오케스트레이션 계층이 약하다는 점이다.

따라서 리팩토링의 중심은 모델 교체가 아니라 아래여야 한다.

- 입력 사전 진단
- map-reduce형 추출
- 중간 산출물 캐시와 재개
- section 단위 fallback
- 사용자에게 위험도와 진행률을 설명하는 UX

multi-agent를 도입하더라도 적용 범위는 제한해야 한다. `ingestion`과 `report planning`에만 schema-constrained worker를 도입하고, `ontology/simulation/analysis` 코어는 규칙 기반으로 유지하는 hybrid 구조가 가장 현실적이다.

가장 먼저 착수할 항목은 `preflight + chunk 캐시 + 부분 재시도 + report/community 분할 생성`이다. 이후 필요하면 `segmenter/extractor/validator` 수준의 제한적 multi-agent 구조를 얹는 순서가 가장 안전하다.
