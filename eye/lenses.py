"""분석 렌즈 엔진 — 10개 지적 프레임워크 기반 딥 필터

각 렌즈는 6개 분석공간의 원시 결과에 LLM 기반 심층 해석을 적용한다.
렌즈는 독립적인 분석이 아니라, 기존 분석공간 결과를 지적 프레임워크로
재해석하여 추가 인사이트를 생성하는 "딥 필터"로 작동한다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from comad_eye.llm_client import LLMClient

logger = logging.getLogger("comadeye")


# ─────────────────────── 렌즈 정의 ───────────────────────

@dataclass
class Lens:
    """분석 렌즈 정의."""
    id: str
    name_ko: str
    name_en: str
    thinker: str
    framework: str  # 프레임워크 설명
    system_prompt: str  # LLM 시스템 프롬프트
    space_prompts: dict[str, str] = field(default_factory=dict)  # 공간별 분석 프롬프트
    default_enabled: bool = True


# 10개 렌즈 정의
LENS_CATALOG: list[Lens] = [
    # ── 전략/권력 ──
    Lens(
        id="sun_tzu",
        name_ko="손자",
        name_en="Sun Tzu",
        thinker="손자 (孫子)",
        framework="전략적 지형/세력 분석 — 세(勢), 지형(地形), 허실(虛實)",
        default_enabled=True,
        system_prompt="""\
당신은 손자병법의 전략 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 세(勢): 유리한 형세를 만드는 엔티티/세력은 누구인가?
- 지형(地形): 네트워크 구조에서 전략적 요충지는 어디인가?
- 허실(虛實): 방어가 약한 허점과 집중된 실(實)은 어디인가?
- 기(奇)와 정(正): 예측 가능한 정공법 vs 의외의 기습 패턴
- 승리 조건: 싸우지 않고 이기는 경로가 있는가?

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 구조에서 전략적 고지(高地)를 차지한 세력과 취약한 계층을 분석하세요. 상위 계층이 지형의 이점을 활용하는지, 하위 계층이 기습적 부상을 보이는지 평가하세요.",
            "temporal": "시간축에서 세(勢)의 흐름을 분석하세요. 어떤 엔티티가 먼저 움직여 선기(先機)를 잡았고, 어떤 엔티티가 후발이지만 세를 역전시켰는가?",
            "recursive": "피드백 루프를 세(勢)의 축적 또는 소진으로 해석하세요. 양의 루프는 세의 가속, 음의 루프는 세의 제동. 어떤 루프가 결정적 세를 형성하는가?",
            "structural": "브릿지 노드를 전략적 요충지로, 구조적 공백을 방어 취약점으로 분석하세요. 중심성 높은 노드가 허(虛)인지 실(實)인지 판단하세요.",
            "causal": "인과 체인에서 기(奇)와 정(正)을 구분하세요. 예측 가능한 인과 경로(정)와 의외의 파급 경로(기)를 식별하세요.",
        },
    ),
    Lens(
        id="machiavelli",
        name_ko="마키아벨리",
        name_en="Machiavelli",
        thinker="니콜로 마키아벨리",
        framework="권력 구조/동맹 역학 — 군주론, 비르투(Virtù)와 포르투나(Fortuna)",
        default_enabled=False,
        system_prompt="""\
당신은 마키아벨리 관점의 권력 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 비르투(Virtù): 능동적으로 상황을 통제하는 엔티티는 누구인가?
- 포르투나(Fortuna): 외부 사건에 의해 운명이 좌우되는 엔티티는?
- 동맹과 배신: 관계의 안정성과 전략적 동맹/적대 패턴
- 공포와 사랑: 영향력의 원천이 두려움(강제)인가 호감(합의)인가?
- 권력 유지: 현재 권력자가 지위를 유지할 수 있는가?

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 구조를 권력 서열로 해석하세요. 각 계층에서 누가 군주(지배자)이고 누가 신민인가? 계층 간 권력 이동이 있는가?",
            "temporal": "시간축에서 비르투와 포르투나의 상호작용을 분석하세요. 어떤 엔티티가 능동적으로 행동하고, 어떤 엔티티가 사건에 수동적으로 반응하는가?",
            "recursive": "피드백 루프를 권력 강화/약화 메커니즘으로 해석하세요. 양의 루프는 권력 집중, 음의 루프는 견제. 불안정한 권력 구조의 징후는?",
            "structural": "네트워크에서 권력의 원천을 분석하세요. 중심성 = 직접 권력, 매개 중심성 = 정보/중재 권력. 구조적 공백은 권력 진공.",
            "causal": "인과 체인에서 의도적 행위(비르투)와 우연적 결과(포르투나)를 구분하세요. 누가 인과의 주체이고 누가 피동적 결과인가?",
        },
    ),
    Lens(
        id="clausewitz",
        name_ko="클라우제비츠",
        name_en="Clausewitz",
        thinker="카를 폰 클라우제비츠",
        framework="마찰/불확실성/결정적 타격점 — 전쟁론, 전장의 안개",
        default_enabled=False,  # 로컬 LLM 부하 절감
        system_prompt="""\
당신은 클라우제비츠 관점의 전략 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 마찰(Friction): 계획과 실제 결과 사이의 괴리. 예상치 못한 저항이나 지연
- 전장의 안개(Fog of War): 정보 불완전성으로 인한 판단 오류 가능성
- 중심(Schwerpunkt): 결정적 타격점. 여기에 자원을 집중하면 전세를 뒤집을 수 있는 지점
- 절정점(Culminating Point): 공세가 더 이상 유지될 수 없는 한계점
- 정치적 목적: 시뮬레이션 내 갈등의 궁극적 목적

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 간 마찰을 분석하세요. 상위 계층의 의도가 하위 계층에서 왜곡되거나 지연되는가? 정보 전달의 안개는?",
            "temporal": "시간축에서 절정점을 식별하세요. 공세적 변화가 최고조에 달한 뒤 반전되는 시점은? 마찰로 인한 지연 패턴은?",
            "recursive": "피드백 루프를 마찰의 증폭/감쇠로 해석하세요. 양의 루프는 마찰의 기하급수적 증가, 음의 루프는 자연적 제동.",
            "structural": "네트워크에서 중심(Schwerpunkt)을 식별하세요. 최소 자원으로 최대 효과를 낼 수 있는 결정적 타격점은 어디인가?",
            "causal": "인과 체인에서 마찰이 가장 심한 경로를 찾으세요. 계획된 인과와 실제 인과의 괴리가 큰 곳은? 전장의 안개가 판단을 흐린 곳은?",
        },
    ),

    # ── 경제/시장 ──
    Lens(
        id="adam_smith",
        name_ko="애덤 스미스",
        name_en="Adam Smith",
        thinker="애덤 스미스",
        framework="자원 흐름/자기조직화 — 보이지 않는 손, 분업, 비교우위",
        default_enabled=True,
        system_prompt="""\
당신은 애덤 스미스 관점의 시장/자원 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 보이지 않는 손: 개별 엔티티의 이기적 행동이 전체 시스템에 미치는 영향
- 분업과 전문화: 엔티티들이 역할을 분담하고 있는가?
- 비교우위: 각 엔티티의 상대적 강점은 무엇인가?
- 자원 배분: 영향력/stance/volatility가 효율적으로 분배되는가?
- 시장 실패: 외부효과, 정보 비대칭, 독과점이 존재하는가?

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 구조를 시장 구조로 해석하세요. 독과점적 계층이 있는가? 하위 계층의 자원이 상위로 이동하는 '보이지 않는 손'의 패턴은?",
            "temporal": "시간축에서 자원 흐름의 효율성을 분석하세요. 빠르게 반응하는 엔티티(효율적 시장)와 느리게 반응하는 엔티티(시장 실패)는?",
            "recursive": "피드백 루프를 시장 매커니즘으로 해석하세요. 양의 루프는 버블/독점 강화, 음의 루프는 시장 자기교정.",
            "structural": "네트워크에서 자원 흐름의 병목과 효율성을 분석하세요. 브릿지 노드는 중개자/거래소, 구조적 공백은 시장 미발달 영역.",
            "causal": "인과 체인을 공급-수요 인과로 해석하세요. 어떤 변화가 연쇄적 시장 반응을 일으키는가? 외부효과(의도하지 않은 파급)는?",
        },
    ),
    Lens(
        id="taleb",
        name_ko="탈레브",
        name_en="Taleb",
        thinker="나심 니콜라스 탈레브",
        framework="안티프래질/블랙스완 리스크 — 비대칭 보상, 꼬리 리스크",
        default_enabled=True,
        system_prompt="""\
당신은 탈레브 관점의 리스크 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 블랙스완: 극히 낮은 확률이지만 발생 시 시스템 전체를 뒤흔드는 사건/엔티티
- 안티프래질(Antifragile): 충격을 받을수록 강해지는 엔티티
- 프래질(Fragile): 작은 충격에도 무너지는 취약한 엔티티
- 꼬리 리스크: 분포의 극단값에 숨겨진 위험
- 비대칭: 이득은 제한적이지만 손실은 무한한 구조

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "각 계층의 프래질리티를 평가하세요. 어떤 계층이 충격에 취약하고, 어떤 계층이 안티프래질한가? 블랙스완이 발생하면 어떤 계층이 먼저 무너지는가?",
            "temporal": "시간축에서 블랙스완 후보를 식별하세요. 비정상적으로 큰 변화, 예측 불가능한 반응, 극단적 지연 패턴은?",
            "recursive": "피드백 루프를 프래질리티 관점에서 분석하세요. 양의 루프는 프래질(붕괴 가속), 음의 루프는 로버스트(자기교정). 안티프래질 루프는?",
            "structural": "네트워크의 꼬리 리스크를 분석하세요. 단일 노드 제거 시 전체 네트워크가 분리되는 취약점은? 브릿지 노드의 프래질리티는?",
            "causal": "인과 체인에서 비대칭 리스크를 식별하세요. 작은 원인이 거대한 결과를 낳는 경로, 또는 거대한 투입이 미미한 결과를 내는 경로는?",
        },
    ),
    Lens(
        id="kahneman",
        name_ko="카너먼",
        name_en="Kahneman",
        thinker="다니엘 카너먼",
        framework="인지 편향/비대칭 반응 — 프로스펙트 이론, 시스템 1·2",
        default_enabled=True,
        system_prompt="""\
당신은 카너먼 관점의 행동경제학 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 프로스펙트 이론: 이득보다 손실에 더 민감하게 반응하는 패턴
- 시스템 1 (빠른 반응): 즉각적/감정적/직관적 반응 패턴
- 시스템 2 (느린 반응): 분석적/이성적/계산적 반응 패턴
- 앵커링: 초기 정보에 과도하게 의존하는 패턴
- 가용성 편향: 최근 사건에 과도하게 반응하는 패턴
- 확증 편향: 기존 입장을 강화하는 방향으로만 반응

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층별 인지 편향을 분석하세요. 상위 계층은 시스템 2(분석적)로 반응하고 하위 계층은 시스템 1(직관적)로 반응하는가? 앵커링 효과는?",
            "temporal": "시간축에서 프로스펙트 이론 패턴을 분석하세요. 부정적 변화에 대한 반응 강도가 긍정적 변화보다 큰가? 최근 사건에 대한 과잉반응(가용성 편향)은?",
            "recursive": "피드백 루프에서 인지 편향의 역할을 분석하세요. 확증 편향이 양의 루프를 강화하는가? 손실 회피가 음의 루프를 만드는가?",
            "structural": "네트워크 구조에서 정보 편향을 분석하세요. 중심 노드가 앵커 역할을 하여 주변 노드의 판단을 왜곡하는가?",
            "causal": "인과 체인에서 비대칭 반응을 식별하세요. 동일한 원인이 긍정/부정에 따라 다른 강도의 결과를 만드는 경로는?",
        },
    ),

    # ── 시스템/구조 ──
    Lens(
        id="hegel",
        name_ko="헤겔",
        name_en="Hegel",
        thinker="게오르크 빌헬름 프리드리히 헤겔",
        framework="변증법적 대립과 종합 — 정(These), 반(Antithese), 합(Synthese)",
        default_enabled=False,
        system_prompt="""\
당신은 헤겔 변증법 관점의 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 정(These): 현재 지배적인 입장/세력
- 반(Antithese): 정에 반대하는 입장/세력
- 합(Synthese): 정과 반의 충돌에서 새로 출현하는 종합적 입장
- 모순의 내재화: 겉보기에 안정적인 구조 안에 내재된 모순
- 역사적 필연: 현재 갈등의 필연적 귀결

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 구조에서 정-반-합의 변증법적 운동을 식별하세요. 지배 계층(정)에 대한 도전(반)이 새로운 질서(합)를 만들고 있는가?",
            "temporal": "시간축에서 변증법적 진행을 추적하세요. 정→반→합의 순환이 관찰되는가? 합이 다시 새로운 정이 되는 패턴은?",
            "recursive": "피드백 루프를 변증법적 모순으로 해석하세요. 양의 루프는 모순의 심화, 음의 루프는 종합의 시도?",
            "structural": "네트워크에서 대립하는 세력(정-반)과 중재하는 세력(잠재적 합)을 식별하세요.",
            "causal": "인과 체인에서 변증법적 전개를 분석하세요. 대립이 새로운 인과를 만드는가? 종합이 새로운 모순을 낳는가?",
        },
    ),
    Lens(
        id="darwin",
        name_ko="다윈",
        name_en="Darwin",
        thinker="찰스 다윈",
        framework="적응/도태/진화 압력 — 자연선택, 적자생존, 변이",
        default_enabled=False,
        system_prompt="""\
당신은 다윈 진화론 관점의 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 자연선택: 환경(시뮬레이션 조건)에 적응한 엔티티가 생존하는가?
- 적응(Adaptation): 어떤 엔티티가 변화하는 환경에 성공적으로 적응하는가?
- 도태(Extinction): 적응에 실패한 엔티티의 특징은?
- 변이(Variation): 다양한 전략/입장의 분포
- 진화 압력: 시스템이 특정 방향으로 엔티티를 밀어내는 압력

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 구조를 생태계 먹이사슬로 해석하세요. 최상위 포식자, 중간 종, 기초 종은 무엇인가? 진화 압력의 방향은?",
            "temporal": "시간축에서 적응과 도태 패턴을 분석하세요. 어떤 엔티티가 빠르게 적응하고, 어떤 엔티티가 도태 위기인가?",
            "recursive": "피드백 루프를 진화적 무기 경쟁(arms race)으로 해석하세요. 공진화 패턴이 관찰되는가?",
            "structural": "네트워크에서 적응도 지형(fitness landscape)을 분석하세요. 국소 최적에 갇힌 엔티티와 전역 최적을 향하는 엔티티는?",
            "causal": "인과 체인을 선택 압력의 전파로 해석하세요. 어떤 사건이 강한 진화 압력을 만들고, 그 압력에 어떤 엔티티가 적응/도태하는가?",
        },
    ),
    Lens(
        id="meadows",
        name_ko="메도우즈",
        name_en="Meadows",
        thinker="도넬라 메도우즈",
        framework="시스템 레버리지 포인트 — 12단계 개입점, 시스템 사고",
        default_enabled=True,
        system_prompt="""\
당신은 메도우즈 관점의 시스템 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 레버리지 포인트: 적은 개입으로 시스템 전체를 변화시킬 수 있는 지점
  (낮은 레벨: 파라미터/버퍼 → 높은 레벨: 규칙/패러다임)
- 스톡과 플로우: 축적되는 양(stance, volatility)과 흐름(전파, 행동)
- 지연(Delay): 원인과 결과 사이의 시간차
- 제한된 성장: 성장을 제한하는 제약 요인
- 시스템 목적: 시스템이 실제로 추구하는 목적 vs 명시적 목적

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 구조에서 레버리지 포인트를 식별하세요. 어떤 계층/커뮤니티에 개입하면 전체 시스템이 변하는가? 가장 높은 레벨의 개입점은?",
            "temporal": "시간축에서 시스템의 지연(delay)을 분석하세요. 스톡-플로우 역학은? 어떤 지연이 시스템 불안정을 만드는가?",
            "recursive": "피드백 루프를 메도우즈의 12단계 레버리지로 매핑하세요. 어떤 루프가 가장 높은 레벨의 개입점인가?",
            "structural": "네트워크에서 시스템의 규칙을 결정하는 노드를 식별하세요. 파라미터 수준(낮은 레버리지)과 패러다임 수준(높은 레버리지)을 구분하세요.",
            "causal": "인과 체인에서 제한된 성장 패턴을 식별하세요. 어떤 제약이 시스템 성장을 막는가? 그 제약을 해제하는 레버리지 포인트는?",
        },
    ),

    # ── 인식론 ──
    Lens(
        id="descartes",
        name_ko="데카르트",
        name_en="Descartes",
        thinker="르네 데카르트",
        framework="방법적 회의/가정 검증 — 체계적 의심, 명석판명한 인식",
        default_enabled=True,
        system_prompt="""\
당신은 데카르트 관점의 인식론 분석가입니다.
다음 원리로 시뮬레이션 데이터를 분석하세요:
- 방법적 회의: 모든 분석 결과를 의심하고 검증하세요
- 가정 검증: 분석에 내재된 숨겨진 가정은 무엇인가?
- 명석판명(Clara et Distincta): 확실히 참인 것과 불확실한 것을 구분
- 환원적 분석: 복잡한 현상을 가장 단순한 요소로 분해
- 체계적 열거: 모든 가능성을 빠짐없이 검토

반드시 JSON 형식으로 응답하세요.""",
        space_prompts={
            "hierarchy": "계층 분석의 숨겨진 가정을 검증하세요. 계층 구분 자체가 인위적이지 않은가? 다른 분류 기준이면 결과가 달라지는가?",
            "temporal": "시간 분석의 불확실성을 평가하세요. 선행지표의 상관이 인과를 의미하는가? 우연의 일치를 배제할 수 있는가?",
            "recursive": "피드백 루프 탐지의 신뢰도를 검증하세요. 관찰된 루프가 진짜 피드백인가, 아니면 데이터 노이즈인가?",
            "structural": "네트워크 분석의 가정을 의심하세요. 중심성 지표가 실제 영향력을 반영하는가? 관찰되지 않는 숨겨진 연결은?",
            "causal": "인과 분석의 명석판명한 부분과 불확실한 부분을 구분하세요. 상관관계를 인과로 오인한 곳은? 역인과 가능성은?",
        },
    ),
]

# 렌즈 ID → 렌즈 객체 매핑
LENS_MAP: dict[str, Lens] = {lens.id: lens for lens in LENS_CATALOG}

# 기본 활성화 렌즈 ID 목록
DEFAULT_LENS_IDS: list[str] = [lens.id for lens in LENS_CATALOG if lens.default_enabled]

# 전체 렌즈 ID 목록
ALL_LENS_IDS: list[str] = [lens.id for lens in LENS_CATALOG]


def compute_lens_budget(settings_override: dict[str, Any] | None = None) -> int:
    """시뮬레이션 파라미터에 따라 적용할 렌즈 수를 결정한다.

    깊은 분석(높은 max_rounds, 높은 max_hops, 낮은 convergence_threshold)일수록
    더 많은 렌즈를 적용하여 분석 시선을 다각화한다.

    Returns:
        3 ~ 10 사이의 렌즈 예산
    """
    if not settings_override:
        return len(DEFAULT_LENS_IDS)  # 기본 6개

    rounds = settings_override.get("max_rounds", 10)
    hops = settings_override.get("propagation_max_hops", settings_override.get("max_hops", 3))
    decay = settings_override.get("propagation_decay", 0.6)
    convergence = settings_override.get("convergence_threshold", 0.01)

    # 깊이 점수 계산 (0.0 ~ 1.0)
    # rounds: 5→0.0, 50→1.0
    rounds_score = min(1.0, max(0.0, (rounds - 5) / 45))
    # hops: 1→0.0, 10→1.0
    hops_score = min(1.0, max(0.0, (hops - 1) / 9))
    # decay: 0.7→얕음(0.0), 0.3→깊음(1.0) — 낮을수록 멀리 전파
    decay_score = min(1.0, max(0.0, (0.7 - decay) / 0.4))
    # convergence: 0.05→얕음(0.0), 0.001→깊음(1.0) — 낮을수록 정밀
    conv_score = min(1.0, max(0.0, (0.05 - convergence) / 0.049))

    depth = (rounds_score * 0.35 + hops_score * 0.25 + decay_score * 0.2 + conv_score * 0.2)

    # 3 ~ 10 매핑
    budget = round(3 + depth * 7)
    return max(3, min(10, budget))


# ─────────────────────── 렌즈 엔진 ───────────────────────

class LensEngine:
    """분석공간 결과에 지적 프레임워크 렌즈를 적용한다."""

    def __init__(
        self,
        llm: LLMClient,
        selected_lens_ids: list[str] | None = None,
        graph_client: Any | None = None,
    ):
        self._llm = llm
        self._graph = graph_client  # RAG 쿼리용 그래프 클라이언트
        self._auto_selected = False
        if selected_lens_ids is None:
            self._lenses = [LENS_MAP[lid] for lid in DEFAULT_LENS_IDS]
        else:
            self._lenses = [LENS_MAP[lid] for lid in selected_lens_ids if lid in LENS_MAP]
        logger.info("렌즈 엔진 초기화: %d개 렌즈 활성화", len(self._lenses))

    def auto_select(
        self,
        seed_text: str,
        analysis_prompt: str | None,
        budget: int,
    ) -> None:
        """LLM을 사용하여 시드 데이터와 분석 주제에 적합한 렌즈를 자동 선별한다."""
        catalog_desc = "\n".join(
            f"- {lens.id}: {lens.name_ko} ({lens.name_en}) — {lens.framework}"
            for lens in LENS_CATALOG
        )

        prompt = (
            f"분석 대상 데이터 (시드 텍스트 앞부분):\n{seed_text[:500]}\n\n"
        )
        if analysis_prompt:
            prompt += f"분석 주제/관점: {analysis_prompt}\n\n"

        prompt += (
            f"사용 가능한 분석 렌즈 목록:\n{catalog_desc}\n\n"
            f"위 데이터와 주제에 가장 적합한 렌즈를 정확히 {budget}개 선택하세요.\n"
            f"선택 기준: 데이터의 성격, 분석 주제와의 관련성, 다각적 시선 확보\n\n"
            f'JSON 형식으로 응답: {{"selected": ["lens_id_1", "lens_id_2", ...], '
            f'"reasoning": "선택 이유 (1~2문장)"}}'
        )

        try:
            result = self._llm.generate_json(
                system=(
                    "당신은 분석 전략가입니다. 주어진 데이터와 분석 주제에 가장 적합한 "
                    "지적 프레임워크 렌즈를 선별합니다. 데이터의 도메인(경제, 기술, 정치, "
                    "사회 등)과 분석 목적을 고려하여 다각적 분석이 가능하도록 렌즈를 "
                    "조합하세요. 반드시 JSON으로만 응답하세요."
                ),
                prompt=prompt,
                temperature=0.3,
                task_type="lens",
            )

            selected_ids = result.get("selected", [])
            # 유효한 렌즈 ID만 필터링
            valid_ids = [lid for lid in selected_ids if lid in LENS_MAP]

            if valid_ids:
                self._lenses = [LENS_MAP[lid] for lid in valid_ids[:budget]]
                self._auto_selected = True
                reasoning = result.get("reasoning", "")
                logger.info(
                    "렌즈 자동 선별 완료 (예산 %d개): %s — %s",
                    budget, [lbl.id for lbl in self._lenses], reasoning,
                )
            else:
                # 실패 시 기본 렌즈 사용
                self._lenses = [LENS_MAP[lid] for lid in DEFAULT_LENS_IDS[:budget]]
                logger.warning("렌즈 자동 선별 실패, 기본 렌즈 %d개 사용", len(self._lenses))

        except Exception as e:
            logger.warning("렌즈 자동 선별 LLM 호출 실패: %s — 기본 렌즈 사용", e)
            self._lenses = [LENS_MAP[lid] for lid in DEFAULT_LENS_IDS[:budget]]

    @property
    def is_auto_selected(self) -> bool:
        return self._auto_selected

    @property
    def active_lens_ids(self) -> list[str]:
        return [lens.id for lens in self._lenses]

    def apply_to_spaces(
        self,
        space_results: dict[str, dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """모든 활성 렌즈를 5개 분석공간 결과에 적용한다.

        Returns:
            {space_name: [lens_insight, ...]} 형태의 딕셔너리
        """
        all_insights: dict[str, list[dict[str, Any]]] = {}

        for space_name, space_result in space_results.items():
            if space_name == "cross_space":
                continue  # 교차공간은 렌즈 적용 대상이 아님

            space_insights: list[dict[str, Any]] = []
            for lens in self._lenses:
                space_prompt = lens.space_prompts.get(space_name)
                if not space_prompt:
                    continue

                insight = self._apply_single_lens(lens, space_name, space_result, space_prompt)
                if insight:
                    space_insights.append(insight)

            all_insights[space_name] = space_insights
            logger.info(
                "렌즈 적용 완료 [%s]: %d개 렌즈 → %d개 인사이트",
                space_name, len(self._lenses), len(space_insights),
            )

        return all_insights

    def synthesize_cross_lens(
        self,
        lens_insights: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """렌즈 인사이트를 교차 분석하여 메타 인사이트를 생성한다."""
        if not any(lens_insights.values()):
            return []

        # 렌즈별로 모든 공간의 인사이트를 모은다
        by_lens: dict[str, list[dict[str, Any]]] = {}
        for space_name, insights in lens_insights.items():
            for insight in insights:
                lid = insight.get("lens_id", "")
                by_lens.setdefault(lid, []).append({
                    "space": space_name,
                    **insight,
                })

        cross_insights: list[dict[str, Any]] = []
        for lid, insights in by_lens.items():
            lens = LENS_MAP.get(lid)
            if not lens or len(insights) < 2:
                continue

            # 렌즈별 교차 종합
            summary_parts = []
            for ins in insights:
                key_points = ins.get("key_points", [])
                if key_points:
                    summary_parts.append(f"[{ins['space']}] {'; '.join(key_points[:2])}")

            if not summary_parts:
                continue

            prompt = (
                f"아래는 {lens.name_ko}({lens.thinker}) 렌즈로 분석한 "
                f"5개 분석공간의 핵심 발견입니다.\n\n"
                + "\n".join(summary_parts)
                + "\n\n이 발견들을 종합하여 다음을 JSON으로 작성하세요:\n"
                '{"synthesis": "종합 해석 (2~3문장)", '
                '"cross_pattern": "공간을 관통하는 패턴", '
                '"confidence": 0.0~1.0, '
                '"actionable_insight": "실행 가능한 핵심 제안"}'
            )

            try:
                result = self._llm.generate_json(
                    system=lens.system_prompt,
                    prompt=prompt,
                    temperature=0.3,
                    task_type="lens",
                )
                cross_insights.append({
                    "lens_id": lid,
                    "lens_name": lens.name_ko,
                    "thinker": lens.thinker,
                    "spaces": [ins["space"] for ins in insights],
                    **result,
                })
            except Exception as e:
                logger.warning("렌즈 교차 종합 실패 [%s]: %s", lid, e)

        # 신뢰도 기반 정렬
        cross_insights.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return cross_insights

    def _query_lens_principles(self, lens_id: str, space_name: str) -> str:
        """그래프에서 렌즈 원리를 RAG 쿼리하여 프롬프트용 텍스트를 반환한다."""
        if not self._graph:
            return ""
        try:
            from analysis.lens_knowledge import (
                format_principles_for_prompt,
                query_lens_principles,
            )
            principles = query_lens_principles(self._graph, lens_id, space_name)
            return format_principles_for_prompt(principles)
        except Exception:
            return ""

    def _apply_single_lens(
        self,
        lens: Lens,
        space_name: str,
        space_result: dict[str, Any],
        space_prompt: str,
    ) -> dict[str, Any] | None:
        """단일 렌즈를 단일 분석공간 결과에 적용한다."""
        # 공간 결과를 간결하게 요약 (LLM 컨텍스트 절약)
        data_summary = self._summarize_space_result(space_name, space_result)

        # RAG: 그래프에서 렌즈 원리를 쿼리
        principles_text = self._query_lens_principles(lens.id, space_name)

        prompt = f"분석공간: {space_name}\n\n"

        # 렌즈 원리를 데이터 앞에 배치 (RAG 컨텍스트)
        if principles_text:
            prompt += f"{principles_text}\n\n"

        prompt += (
            f"분석 데이터:\n{data_summary}\n\n"
            f"분석 지시:\n{space_prompt}\n\n"
            "위 프레임워크 원리를 데이터에 구체적으로 적용하여 분석하세요.\n"
            "각 원리의 '적용법'을 참고하여 데이터의 수치와 엔티티를 직접 언급하세요.\n\n"
            "다음 JSON 형식으로 응답하세요:\n"
            '{"key_points": ["핵심 발견 1", "핵심 발견 2", "핵심 발견 3"], '
            '"risk_assessment": "위험 평가 (1문장)", '
            '"opportunity": "기회 요인 (1문장)", '
            '"confidence": 0.0~1.0}\n\n'
            "중요: 분석 데이터에 있는 엔티티와 수치만 사용하세요. "
            "데이터에 없는 엔티티나 사실을 만들어내지 마세요. "
            "데이터가 부족하면 confidence를 낮게 설정하고 그 사실을 key_points에 명시하세요."
        )

        try:
            result = self._llm.generate_json(
                system=lens.system_prompt,
                prompt=prompt,
                temperature=0.3,
                task_type="lens",
            )
            return {
                "lens_id": lens.id,
                "lens_name": lens.name_ko,
                "thinker": lens.thinker,
                "space": space_name,
                **result,
            }
        except Exception as e:
            logger.warning("렌즈 적용 실패 [%s → %s]: %s", lens.id, space_name, e)
            return None

    def _summarize_space_result(self, space_name: str, result: dict[str, Any]) -> str:
        """분석공간 결과를 LLM에 전달할 간결한 텍스트로 요약한다."""
        parts: list[str] = []

        if space_name == "hierarchy":
            parts.append(f"전파 방향: {result.get('propagation_direction', 'N/A')}")
            parts.append(f"가장 동적 계층: {result.get('most_dynamic_tier', 'N/A')}")
            parts.append(f"가장 동적 커뮤니티: {result.get('most_dynamic_community', 'N/A')}")
            tier = result.get("tier_analysis", {})
            for tier_key, comms in tier.items():
                if isinstance(comms, dict):
                    for cid, metrics in list(comms.items())[:3]:
                        parts.append(
                            f"  {tier_key}/{cid}: 멤버 {metrics.get('member_count', 0)}, "
                            f"stance변화 {metrics.get('stance_delta', 0):.3f}, "
                            f"변동성변화 {metrics.get('volatility_delta', 0):.3f}, "
                            f"행동 {metrics.get('action_count', 0)}회"
                        )

        elif space_name == "temporal":
            events = result.get("event_reactions", {})
            parts.append(f"이벤트 반응 수: {len(events)}")
            for eid, data in list(events.items())[:3]:
                parts.append(
                    f"  {data.get('event_name', eid)}: "
                    f"반응 {data.get('reaction_count', 0)}건, "
                    f"평균지연 {data.get('avg_delay', 0):.1f}라운드"
                )
            indicators = result.get("leading_indicators", [])
            parts.append(f"선행지표: {len(indicators)}개")
            for ind in indicators[:3]:
                parts.append(
                    f"  {ind.get('leader_name', '?')} → {ind.get('follower_name', '?')} "
                    f"(상관 {ind.get('correlation', 0):.2f}, 시차 {ind.get('lag_rounds', 0)})"
                )

        elif space_name == "recursive":
            loops = result.get("feedback_loops", [])
            summary = result.get("loop_summary", {})
            parts.append(f"양의 루프: {summary.get('positive_count', 0)}")
            parts.append(f"음의 루프: {summary.get('negative_count', 0)}")
            for loop in loops[:5]:
                nodes = " → ".join(loop.get("nodes", [])[:4])
                parts.append(
                    f"  [{loop.get('type', '?')}] {nodes} (강도 {loop.get('strength', 0):.3f})"
                )
            fractals = result.get("fractal_patterns", [])
            if fractals:
                parts.append(f"프랙탈 패턴: {len(fractals)}개")

        elif space_name == "structural":
            centrality = result.get("centrality_changes", {})
            risers = centrality.get("top_risers", [])
            parts.append(f"Top Risers: {len(risers)}")
            for r in risers[:3]:
                parts.append(
                    f"  {r.get('name', '?')}: degree={r.get('degree', 0):.3f}, "
                    f"pagerank={r.get('pagerank', 0):.3f}"
                )
            bridges = result.get("bridge_nodes", [])
            parts.append(f"브릿지 노드: {len(bridges)}개")
            for b in bridges[:3]:
                parts.append(f"  {b.get('name', '?')}: {len(b.get('bridges', []))}개 커뮤니티 연결")
            holes = result.get("structural_holes", [])
            parts.append(f"구조적 공백: {len(holes)}개")

        elif space_name == "causal":
            dag = result.get("causal_dag", {})
            parts.append(f"DAG: 노드 {dag.get('nodes', 0)}, 엣지 {dag.get('edges', 0)}")
            root_causes = result.get("root_cause_ranking", [])
            parts.append(f"근본 원인: {len(root_causes)}개")
            for rc in root_causes[:3]:
                parts.append(
                    f"  {rc.get('node', '?')}: 하류 {rc.get('downstream', 0)}개, "
                    f"영향 {rc.get('total_impact', 0):.2f}"
                )
            chains = result.get("causal_chains", [])
            parts.append(f"인과 체인: {len(chains)}개")
            for chain in chains[:3]:
                parts.append(f"  {chain.get('chain_str', '?')} (가중치 {chain.get('total_weight', 0):.2f})")

        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)[:2000]
