"""렌즈 지식 그래프 — 10개 렌즈의 핵심 원리를 Neo4j 노드로 적재한다.

각 렌즈의 사상가 원리를 :LensKnowledge 노드로 생성하고,
렌즈 분석 시 해당 원리를 RAG 방식으로 쿼리하여 LLM 프롬프트에 주입한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("comadeye")


@dataclass
class LensPrinciple:
    """렌즈 원리 하나."""
    lens_id: str
    principle_id: str
    name: str
    description: str
    application_hint: str  # 시뮬레이션 데이터에 적용하는 힌트
    space_relevance: list[str] = field(default_factory=list)  # 관련 분석공간


# ── 10개 렌즈의 핵심 원리 정의 ──

LENS_PRINCIPLES: list[LensPrinciple] = [
    # ── 손자 (Sun Tzu) ──
    LensPrinciple(
        lens_id="sun_tzu", principle_id="st_shi",
        name="세(勢) — 전략적 형세",
        description="전투 전에 유리한 형세를 만드는 것이 핵심이다. 직접 충돌보다 상황 조성이 중요하다.",
        application_hint="영향력 점수가 높으면서 변동성이 낮은 엔티티는 '세'를 장악한 것이다",
        space_relevance=["structural", "hierarchy"],
    ),
    LensPrinciple(
        lens_id="sun_tzu", principle_id="st_terrain",
        name="지형(地形) — 전략적 위치",
        description="높은 곳을 차지하고, 좁은 통로를 지배하라. 네트워크에서 브릿지 노드는 전략적 요충지이다.",
        application_hint="betweenness centrality가 높은 노드는 전략적 요충지다. 이 노드를 통제하면 정보와 영향력 흐름을 지배한다",
        space_relevance=["structural", "hierarchy"],
    ),
    LensPrinciple(
        lens_id="sun_tzu", principle_id="st_void",
        name="허실(虛實) — 집중과 분산",
        description="적이 강한 곳을 피하고 약한 곳을 공격하라. 실(實)이 집중된 곳과 허(虛)인 곳을 식별하라.",
        application_hint="구조적 공백(structural hole)은 '허'이고, 밀집 커뮤니티는 '실'이다. 공백을 연결하는 행위자가 전략적 우위를 점한다",
        space_relevance=["structural", "causal"],
    ),
    LensPrinciple(
        lens_id="sun_tzu", principle_id="st_surprise",
        name="기정(奇正) — 정공법과 기습",
        description="정(正)으로 적을 묶고 기(奇)로 승리한다. 예측 가능한 패턴과 의외의 변화를 구분하라.",
        application_hint="추세를 따르는 엔티티는 '정', 갑자기 stance가 급변하는 엔티티는 '기'의 전략을 쓴다",
        space_relevance=["temporal", "recursive"],
    ),
    LensPrinciple(
        lens_id="sun_tzu", principle_id="st_win_without",
        name="부전승(不戰勝) — 싸우지 않고 이기기",
        description="최선의 전략은 전투 없이 승리하는 것이다. 상대의 전략을 무력화하라.",
        application_hint="영향력 전파만으로 타 엔티티의 stance를 자신 쪽으로 수렴시키는 패턴이 부전승이다",
        space_relevance=["causal", "temporal"],
    ),

    # ── 애덤 스미스 (Adam Smith) ──
    LensPrinciple(
        lens_id="adam_smith", principle_id="as_invisible",
        name="보이지 않는 손 — 자기조직화",
        description="개별 행위자가 자기 이익을 추구할 때, 의도하지 않게 전체 시스템의 효율이 향상된다.",
        application_hint="각 엔티티가 독립적으로 행동하는데도 시스템 전체의 stance가 수렴하면 '보이지 않는 손'이 작동하는 것이다",
        space_relevance=["hierarchy", "temporal"],
    ),
    LensPrinciple(
        lens_id="adam_smith", principle_id="as_division",
        name="분업과 전문화",
        description="역할을 분담하면 전체 생산성이 증가한다. 각 행위자가 비교우위에 집중하는가?",
        application_hint="커뮤니티별로 서로 다른 역할(허브/브릿지/주변부)을 맡고 있으면 건강한 분업이다",
        space_relevance=["structural", "hierarchy"],
    ),
    LensPrinciple(
        lens_id="adam_smith", principle_id="as_market_fail",
        name="시장 실패 — 외부효과와 독점",
        description="정보 비대칭, 외부효과, 독과점이 존재하면 자원 배분이 비효율적이 된다.",
        application_hint="소수 엔티티에 영향력이 과도하게 집중되거나, 커뮤니티 간 정보 흐름이 차단되면 시장 실패",
        space_relevance=["structural", "causal"],
    ),
    LensPrinciple(
        lens_id="adam_smith", principle_id="as_comparative",
        name="비교우위",
        description="절대적 능력이 아니라 상대적 기회비용에 따라 전문화하면 모두가 이득이다.",
        application_hint="영향력 절대값보다, 특정 관계에서의 상대적 영향력이 높은 엔티티가 비교우위를 가진다",
        space_relevance=["structural", "hierarchy"],
    ),

    # ── 탈레브 (Taleb) ──
    LensPrinciple(
        lens_id="taleb", principle_id="tb_antifragile",
        name="안티프래질 — 충격에 강해지기",
        description="충격을 받을수록 강해지는 시스템이 안티프래질하다. 변동성은 위험이 아니라 기회일 수 있다.",
        application_hint="이벤트 충격 후 stance가 더 안정되거나 영향력이 증가한 엔티티는 안티프래질하다",
        space_relevance=["temporal", "recursive"],
    ),
    LensPrinciple(
        lens_id="taleb", principle_id="tb_blackswan",
        name="블랙 스완 — 극단적 사건",
        description="극단적이고 예측 불가능한 사건이 시스템을 지배한다. 정규분포 가정은 위험하다.",
        application_hint="시뮬레이션에서 단일 이벤트가 전체 시스템 stance를 급변시켰다면 블랙 스완이다",
        space_relevance=["temporal", "causal"],
    ),
    LensPrinciple(
        lens_id="taleb", principle_id="tb_skin",
        name="스킨 인 더 게임 — 책임과 보상의 일치",
        description="의사결정자가 결과의 부정적 영향도 직접 감수해야 건전한 시스템이다.",
        application_hint="영향력은 높은데 변동성(리스크 노출)이 낮은 엔티티는 '스킨 인 더 게임'이 없다",
        space_relevance=["structural", "causal"],
    ),
    LensPrinciple(
        lens_id="taleb", principle_id="tb_barbell",
        name="바벨 전략 — 극단적 보수 + 극단적 공격",
        description="중간 리스크를 피하고, 매우 안전한 것과 매우 공격적인 것을 조합하라.",
        application_hint="stance가 극단(±0.8 이상)에 있는 엔티티와 중립(±0.1 이내) 엔티티의 분포를 확인하라",
        space_relevance=["structural", "temporal"],
    ),

    # ── 카너먼 (Kahneman) ──
    LensPrinciple(
        lens_id="kahneman", principle_id="kn_prospect",
        name="프로스펙트 이론 — 손실 회피",
        description="사람은 이득보다 손실에 2배 민감하게 반응한다. 같은 크기의 변화도 방향에 따라 반응이 다르다.",
        application_hint="stance가 하락할 때의 volatility 증가폭이 상승할 때보다 크면 손실 회피 패턴이다",
        space_relevance=["temporal", "recursive"],
    ),
    LensPrinciple(
        lens_id="kahneman", principle_id="kn_system1",
        name="시스템 1 — 빠르고 직관적",
        description="즉각적, 자동적, 감정적 반응. 편향에 취약하지만 빠르다.",
        application_hint="이벤트 발생 직후(1-2라운드) 급격히 반응하는 엔티티는 시스템 1이 지배적이다",
        space_relevance=["temporal", "causal"],
    ),
    LensPrinciple(
        lens_id="kahneman", principle_id="kn_anchor",
        name="앵커링 — 초기값 의존",
        description="최초 제시된 정보(앵커)에 과도하게 의존하여 이후 판단이 편향된다.",
        application_hint="초기 stance 값 근처에서 벗어나지 못하는 엔티티는 앵커링에 갇힌 것이다",
        space_relevance=["temporal", "hierarchy"],
    ),
    LensPrinciple(
        lens_id="kahneman", principle_id="kn_availability",
        name="가용성 편향 — 최근 사건 과대평가",
        description="쉽게 떠오르는(최근, 극적인) 사건의 영향을 과대평가한다.",
        application_hint="최근 라운드의 이벤트에 과도하게 반응하고, 오래된 영향은 무시하는 패턴",
        space_relevance=["temporal", "recursive"],
    ),

    # ── 메도우즈 (Meadows) ──
    LensPrinciple(
        lens_id="meadows", principle_id="md_leverage",
        name="레버리지 포인트 — 시스템 개입점",
        description="적은 힘으로 시스템 전체를 변화시킬 수 있는 지점. 파라미터(약) → 규칙 → 패러다임(강).",
        application_hint="pagerank 대비 degree가 낮은 노드는 높은 레버리지 포인트다(적은 연결로 큰 영향)",
        space_relevance=["structural", "causal"],
    ),
    LensPrinciple(
        lens_id="meadows", principle_id="md_stock_flow",
        name="스톡과 플로우 — 축적과 흐름",
        description="스톡(축적량)은 천천히 변하고, 플로우(유입/유출)가 변화를 만든다.",
        application_hint="stance/volatility는 스톡이고, 전파/행동은 플로우다. 플로우 없이 스톡이 변하면 외부 충격이다",
        space_relevance=["temporal", "hierarchy"],
    ),
    LensPrinciple(
        lens_id="meadows", principle_id="md_delay",
        name="지연(Delay) — 원인과 결과의 시차",
        description="시스템의 피드백에 지연이 있으면 진동과 오버슈팅이 발생한다.",
        application_hint="leading indicator의 lag_rounds가 큰 쌍은 지연이 심한 경로다. 지연이 클수록 시스템 불안정",
        space_relevance=["temporal", "recursive"],
    ),
    LensPrinciple(
        lens_id="meadows", principle_id="md_feedback",
        name="피드백 루프 — 균형과 강화",
        description="음의 루프는 안정시키고, 양의 루프는 증폭시킨다. 루프의 지배력이 시스템 행동을 결정한다.",
        application_hint="양의 피드백 루프의 강도가 음의 루프보다 크면 시스템은 폭주한다",
        space_relevance=["recursive", "causal"],
    ),

    # ── 데카르트 (Descartes) ──
    LensPrinciple(
        lens_id="descartes", principle_id="dc_doubt",
        name="방법적 회의 — 체계적 의심",
        description="모든 것을 의심하고, 확실한 것만 남겨라. 'confidence가 낮은 분석은 의심하라'는 원칙.",
        application_hint="confidence < 0.5인 렌즈 인사이트나 상관관계는 방법적 회의의 대상이다",
        space_relevance=["causal", "temporal"],
    ),
    LensPrinciple(
        lens_id="descartes", principle_id="dc_reduction",
        name="환원적 분석 — 분해와 재조합",
        description="복잡한 현상을 가장 단순한 요소로 분해한 뒤, 단순한 것부터 재조합하라.",
        application_hint="복잡한 인과 체인을 2-hop 단위로 분해하면 각 단계의 메커니즘을 명확히 이해할 수 있다",
        space_relevance=["causal", "structural"],
    ),
    LensPrinciple(
        lens_id="descartes", principle_id="dc_enumerate",
        name="체계적 열거 — 빠짐없는 검토",
        description="가능한 모든 경우를 빠짐없이 열거하라. 누락이 오류의 원인이다.",
        application_hint="분석에서 고려하지 못한 커뮤니티나 관계 유형이 없는지 점검하라",
        space_relevance=["structural", "hierarchy"],
    ),
    LensPrinciple(
        lens_id="descartes", principle_id="dc_clear",
        name="명석판명(Clara et Distincta) — 확실성 기준",
        description="명석하고(clear) 판명한(distinct) 것만 참으로 받아들여라.",
        application_hint="통계적으로 유의미한 패턴(상관 > 0.7, confidence > 0.8)만 확실한 발견으로 보고하라",
        space_relevance=["causal", "temporal"],
    ),

    # ── 마키아벨리 (Machiavelli) ──
    LensPrinciple(
        lens_id="machiavelli", principle_id="mc_power",
        name="권력의 역학",
        description="권력은 유지하기 위해 끊임없이 행사해야 한다. 정당성보다 효과가 중요하다.",
        application_hint="영향력이 높고 행동(action) 빈도도 높은 엔티티가 적극적으로 권력을 행사하는 행위자다",
        space_relevance=["structural", "temporal"],
    ),
    LensPrinciple(
        lens_id="machiavelli", principle_id="mc_fortune",
        name="비르투와 포르투나 — 능력과 운",
        description="50%는 운(fortuna)이고 50%는 능력(virtù)이다. 위기에 능력이 드러난다.",
        application_hint="이벤트 충격(포르투나) 후 빠르게 stance를 회복한 엔티티는 높은 비르투를 가진 것이다",
        space_relevance=["temporal", "recursive"],
    ),
    LensPrinciple(
        lens_id="machiavelli", principle_id="mc_fear_love",
        name="두려움과 사랑 — 통제 수단",
        description="사랑받는 것보다 두려움의 대상이 되는 것이 통치에 유리하다.",
        application_hint="stance 변화를 강제(음의 전파)하는 엔티티는 '두려움', 자발적 수렴을 이끄는 엔티티는 '사랑'으로 통제한다",
        space_relevance=["causal", "hierarchy"],
    ),

    # ── 클라우제비츠 (Clausewitz) ──
    LensPrinciple(
        lens_id="clausewitz", principle_id="cw_friction",
        name="마찰(Friction) — 계획과 현실의 괴리",
        description="전쟁에서 모든 것이 단순하지만, 가장 단순한 것이 가장 어렵다.",
        application_hint="시뮬레이션에서 예상 전파 경로와 실제 결과가 다르면 마찰이 존재하는 것이다",
        space_relevance=["temporal", "causal"],
    ),
    LensPrinciple(
        lens_id="clausewitz", principle_id="cw_fog",
        name="전쟁의 안개(Fog of War) — 불확실성",
        description="적의 의도와 상황을 완전히 파악할 수 없다. 불확실성 속에서 결정해야 한다.",
        application_hint="volatility가 높은 영역은 '안개'가 짙은 곳이다. 이 영역의 분석은 confidence를 낮춰야 한다",
        space_relevance=["structural", "temporal"],
    ),
    LensPrinciple(
        lens_id="clausewitz", principle_id="cw_decisive",
        name="결정적 지점(Schwerpunkt)",
        description="전력을 집중해야 할 결정적 지점을 식별하라. 병력 분산은 패배의 원인이다.",
        application_hint="인과 체인이 수렴하는 노드(여러 경로가 만나는 지점)가 결정적 지점이다",
        space_relevance=["causal", "structural"],
    ),

    # ── 헤겔 (Hegel) ──
    LensPrinciple(
        lens_id="hegel", principle_id="hg_dialectic",
        name="변증법 — 정반합(正反合)",
        description="정(thesis)과 반(antithesis)의 충돌이 합(synthesis)을 낳는다.",
        application_hint="stance가 반대인(+ vs -) 엔티티 쌍의 상호작용이 새로운 균형점을 만들면 변증법적 합이다",
        space_relevance=["temporal", "recursive"],
    ),
    LensPrinciple(
        lens_id="hegel", principle_id="hg_aufheben",
        name="지양(Aufheben) — 보존하며 넘어섬",
        description="대립을 단순히 해소하는 것이 아니라, 양쪽의 진리를 보존하며 높은 단계로 올라간다.",
        application_hint="두 커뮤니티가 합병될 때 양쪽의 특성이 보존되면 지양, 한쪽이 소멸하면 단순 흡수",
        space_relevance=["hierarchy", "structural"],
    ),
    LensPrinciple(
        lens_id="hegel", principle_id="hg_contradiction",
        name="모순 — 발전의 동력",
        description="내적 모순이 변화와 발전을 추동한다. 모순이 없는 시스템은 정체된다.",
        application_hint="같은 커뮤니티 내에서 stance 방향이 반대인 엔티티가 공존하면 내적 모순이 존재한다",
        space_relevance=["hierarchy", "recursive"],
    ),

    # ── 다윈 (Darwin) ──
    LensPrinciple(
        lens_id="darwin", principle_id="dw_selection",
        name="자연선택 — 적자생존",
        description="환경에 더 잘 적응한 개체가 살아남아 번식한다. 가장 강한 것이 아니라 가장 적응한 것이 생존한다.",
        application_hint="시뮬레이션 종료 시점에서 영향력이 유지되거나 증가한 엔티티는 환경에 적응한 것이다",
        space_relevance=["temporal", "structural"],
    ),
    LensPrinciple(
        lens_id="darwin", principle_id="dw_variation",
        name="변이와 다양성",
        description="집단 내 다양성이 높을수록 환경 변화에 대한 전체 적응력이 높다.",
        application_hint="커뮤니티 내 stance의 분산(표준편차)이 적절히 높으면 건강한 다양성이다",
        space_relevance=["hierarchy", "recursive"],
    ),
    LensPrinciple(
        lens_id="darwin", principle_id="dw_niche",
        name="생태적 지위(Niche) — 독자적 영역",
        description="각 종은 고유한 생태적 지위를 차지한다. 겹치면 경쟁, 분리되면 공존.",
        application_hint="같은 object_type의 엔티티가 같은 커뮤니티에서 유사한 역할을 하면 경쟁(niche overlap)이다",
        space_relevance=["structural", "hierarchy"],
    ),
]


def load_lens_knowledge_to_graph(client: Any) -> int:
    """렌즈 지식을 Neo4j 그래프에 :LensKnowledge 노드로 적재한다.

    Args:
        client: Neo4jClient 인스턴스

    Returns:
        적재된 원리 노드 수
    """
    # 기존 렌즈 지식 삭제 (재적재 지원)
    client.write("MATCH (n:LensKnowledge) DETACH DELETE n")

    # 배치 적재
    principles_data = []
    for p in LENS_PRINCIPLES:
        principles_data.append({
            "uid": f"lens_{p.lens_id}_{p.principle_id}",
            "lens_id": p.lens_id,
            "principle_id": p.principle_id,
            "name": p.name,
            "description": p.description,
            "application_hint": p.application_hint,
            "space_relevance": ",".join(p.space_relevance),
        })

    if not principles_data:
        return 0

    client.write(
        """
        UNWIND $principles AS p
        CREATE (n:LensKnowledge {
            uid: p.uid,
            lens_id: p.lens_id,
            principle_id: p.principle_id,
            name: p.name,
            description: p.description,
            application_hint: p.application_hint,
            space_relevance: p.space_relevance
        })
        """,
        principles=principles_data,
    )

    logger.info("렌즈 지식 적재 완료: %d개 원리", len(principles_data))
    return len(principles_data)


def query_lens_principles(
    client: Any,
    lens_id: str,
    space_name: str | None = None,
) -> list[dict[str, str]]:
    """특정 렌즈의 원리를 그래프에서 쿼리한다.

    Args:
        client: Neo4jClient 인스턴스
        lens_id: 렌즈 ID (e.g., "sun_tzu")
        space_name: 분석공간 이름 (e.g., "structural"). None이면 전체 반환.

    Returns:
        [{"name": ..., "description": ..., "application_hint": ...}, ...]
    """
    if space_name:
        results = client.query(
            "MATCH (n:LensKnowledge) "
            "WHERE n.lens_id = $lens_id AND n.space_relevance CONTAINS $space "
            "RETURN n.name AS name, n.description AS description, "
            "n.application_hint AS application_hint",
            lens_id=lens_id,
            space=space_name,
        )
    else:
        results = client.query(
            "MATCH (n:LensKnowledge) "
            "WHERE n.lens_id = $lens_id "
            "RETURN n.name AS name, n.description AS description, "
            "n.application_hint AS application_hint",
            lens_id=lens_id,
        )

    return [
        {
            "name": r.get("name", ""),
            "description": r.get("description", ""),
            "application_hint": r.get("application_hint", ""),
        }
        for r in results
    ]


def format_principles_for_prompt(principles: list[dict[str, str]]) -> str:
    """쿼리된 원리를 LLM 프롬프트용 텍스트로 포맷한다."""
    if not principles:
        return ""

    lines = ["[참조 프레임워크 원리]"]
    for i, p in enumerate(principles, 1):
        lines.append(f"{i}. {p['name']}")
        lines.append(f"   원리: {p['description']}")
        lines.append(f"   적용법: {p['application_hint']}")
    return "\n".join(lines)
