# Competitive Moat

> "What do you know that nobody else knows?" — Peter Thiel
> Comad의 해자는 단일 기능이 아니라 세 축의 결합이다. 하나만 있으면 따라잡히고, 셋이 함께 있을 때만 시간이 지날수록 격차가 벌어진다.

## 1. Self-evolving feedback loop — 복제 불가능한 궤적

Comad의 핵심은 "읽은 결과"가 끝나지 않고 다음 도구 동작을 다시 바꾼다는 점이다. 사용자가 논문을 읽고, 메모를 남기고, 분류를 수정하고, 예측이 틀릴 때마다 lens weight가 감쇠한다 (eye의 falsification log). 그 흔적이 그래프·메모리·크롤 우선순위에 누적되면서 다음 수집과 해석 품질을 미세하게 바꾼다.

**이 루프는 한 번 잘 쓴 프롬프트로 복제되지 않는다.** 경쟁자가 겉모습을 베껴도, 실제 사용자 상호작용과 축적된 수정 이력 없이 같은 성능 곡선을 재현하기 어렵다. moat는 코드가 아니라 **궤적(trajectory)** 이다.

## 2. Claude Max $0/day 아키텍처 — 원가 구조의 우위

Comad는 별도 API 호출 비용을 늘리는 방식이 아니라 **이미 지불한 Claude Max 구독을 재활용**하는 구조를 전제로 한다 (OS-aware scheduler가 GUI 세션의 OAuth를 상속받아 추가 API 키 없이 동작). 추가 per-call 비용이 사실상 0이므로, 사용량이 늘수록 경쟁 우위가 커진다.

경쟁사가 같은 경험을 제공하려면 **자사 모델 호출을 무료에 가깝게 풀거나 구독 기반 수익 모델을 다시 짜야** 한다. 가격표가 아니라 원가 구조가 다른 셈이다.

## 3. Local-first data sovereignty — 감시 자본주의에 대한 구조적 반대

Neo4j 두 인스턴스, Ollama (eye), 세션 로그 — 모두 로컬에 머문다. 크롤한 원문, 그래프 구조, 예측 이력이 사용자 장비 밖으로 나가지 않는다. 상용 SaaS는 "프라이버시 모드"를 옵션으로 제공할 수 있지만, **텔레메트리 수익을 포기한 아키텍처는 쉽게 따라오지 못한다**. Shoshana Zuboff 축에서 9/10이라는 평가는 이 부분의 구조적 강점이다.

## 4. What we can NOT moat — 정직하게

다음은 **모방 가능**하다:
- 그래프 스키마, MCP 툴 목록, 모듈 분리 아이디어 — 좋은 엔지니어 팀이면 몇 주에 비슷한 표면을 만든다.
- 5 lens 시뮬레이션 개념 — 논문·블로그로 이미 공개된 패턴.
- YAML-driven config reconfiguration — technical taste의 문제지 비밀이 아니다.

우리가 독점할 수 없는 부분을 과장하면 전략 판단이 흐려진다.

## 결론

**Moat = self-evolving loop × Claude Max pricing × local-first.**

셋 중 하나만 가진 경쟁자는:
- 루프만 있고 원가가 높으면 — 사용자가 늘수록 적자.
- 가격 우위만 있고 루프가 없으면 — "또 하나의 MCP 툴킷"에 그친다.
- 로컬 우선만 있으면 — Obsidian plugin 수준에서 정체.

시간이 지날수록 격차가 벌어지는 건 **세 축이 곱셈으로 누적**되기 때문이다.
