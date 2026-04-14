"""Autoresearch 메트릭 스코어 산출 v2.

파이프라인 실행 결과를 분석하여 복합 점수를 계산한다.

기본 점수:
  (엔티티 수 * 2) + (관계 수 * 3) + 단어점수 + (완주 보너스 50)
  단어점수: ≤3000단어까지 선형(/10), 이후 로그 스케일 (블로트 방지)

품질 보너스 (최대 350점):
  + 보고서 섹션 완성도 (10개 필수 섹션 × 10점 = 최대 100점)
  + Key Findings 보너스 (findings 수 × 평균 신뢰도 × 50, 최대 100점)
  + 렌즈 인사이트 보너스 (인사이트 수 × 5, 최대 50점)
  + 인과 체인 깊이 보너스 (체인 수 × 10, 최대 50점)
  + 권고사항 보너스 (30점)
  + 시나리오 보너스 (20점)

서사 품질 보너스 v2 (최대 300점):
  + 해석 밀도: LLM 해석 단락 수 × 10 (최대 80점)
  + 데이터 인용률: 엔티티명 언급 비율 (최대 50점)
  + 교차 참조 밀도: 섹션 간 상호 참조 수 × 5 (최대 40점)
  + 시뮬레이션 깊이: (라운드 수 × 5) + (이벤트 수 × 2) + (액션 수 × 3) (최대 50점)
  + 렌즈 교차 종합: cross-lens 인사이트 수 × 10 (최대 30점)
  + 부록 풍부함: 부록 테이블 행 수 × 0.5 (최대 50점)
"""
import json
import re
from pathlib import Path


def compute_score() -> float:
    score = 0.0

    # 1. 추출 결과 확인
    extraction_dir = Path("data/extraction")
    entities_file = extraction_dir / "entities.jsonl"
    rels_file = extraction_dir / "relationships.jsonl"

    entity_count = 0
    rel_count = 0

    if entities_file.exists():
        for line in entities_file.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                entity_count += 1

    if rels_file.exists():
        for line in rels_file.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                rel_count += 1

    # ontology.json 에서도 확인
    ontology_file = extraction_dir / "comad_eye.ontology.json"
    entity_names: list[str] = []
    if ontology_file.exists():
        try:
            data = json.loads(ontology_file.read_text(encoding="utf-8"))
            entities_raw = data.get("entities", {})
            rels_raw = data.get("relationships", {})
            # entities can be dict (keyed by uid) or list
            if isinstance(entities_raw, dict):
                entity_count = max(entity_count, len(entities_raw))
                entity_names = [
                    v.get("name", k.replace("_", " "))
                    for k, v in entities_raw.items()
                    if isinstance(v, dict)
                ]
            else:
                entity_count = max(entity_count, len(entities_raw))
                entity_names = [
                    e.get("name", "") for e in entities_raw if e.get("name")
                ]
            if isinstance(rels_raw, dict):
                rel_count = max(rel_count, len(rels_raw))
            else:
                rel_count = max(rel_count, len(rels_raw))
        except Exception:
            pass

    # 2. 보고서 확인
    report_dir = Path("data/reports")
    report_text = ""
    report_words = 0
    if report_dir.exists():
        for f in sorted(report_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            if len(text.split()) > report_words:
                report_text = text
                report_words = len(text.split())

    # 3. 기본 점수 계산
    # 단어 수: 최소 3000단어까지는 선형, 이후 로그 스케일 (블로트 방지)
    if report_words <= 3000:
        word_score = report_words / 10
    else:
        import math
        word_score = 300 + math.log2(report_words / 3000) * 150
    score = (entity_count * 2) + (rel_count * 3) + word_score

    # 완주 보너스 (엔티티 + 관계 + 보고서 모두 존재)
    if entity_count > 0 and rel_count > 0 and report_words > 0:
        score += 50

    # 4. 품질 보너스 (기존 v1 — 최대 350점)
    quality_bonus = 0.0
    quality_details: dict[str, float] = {}

    # 4-1. 보고서 섹션 완성도
    required_sections = [
        "Executive Summary",
        "인과 분석",
        "구조 분석",
        "시스템 다이내믹스",
        "교차 분석 인사이트",
        "렌즈 딥 분석",
        "시나리오 분석",
        "핵심 엔티티 프로파일",
        "리스크 매트릭스",
        "전략적 권고사항",
    ]
    section_count = sum(1 for s in required_sections if s in report_text)
    section_bonus = section_count * 10
    quality_bonus += section_bonus
    quality_details["sections"] = section_bonus

    # 4-2. Key Findings 보너스
    analysis_dir = Path("data/analysis")
    agg_file = analysis_dir / "aggregated.json"
    findings_bonus = 0.0
    if agg_file.exists():
        try:
            agg = json.loads(agg_file.read_text(encoding="utf-8"))
            findings = agg.get("key_findings", [])
            if findings:
                avg_conf = sum(f.get("confidence", 0) for f in findings) / len(findings)
                findings_bonus = min(100, len(findings) * avg_conf * 50)
        except Exception:
            pass
    quality_bonus += findings_bonus
    quality_details["findings"] = findings_bonus

    # 4-3. 렌즈 인사이트 보너스
    lens_file = analysis_dir / "lens_insights.json"
    lens_bonus = 0.0
    if lens_file.exists():
        try:
            lens_data = json.loads(lens_file.read_text(encoding="utf-8"))
            total_insights = sum(
                len(v) for v in lens_data.values() if isinstance(v, list)
            )
            lens_bonus = min(50, total_insights * 5)
        except Exception:
            pass
    quality_bonus += lens_bonus
    quality_details["lenses"] = lens_bonus

    # 4-4. 인과 체인 깊이 보너스
    causal_file = analysis_dir / "causal.json"
    causal_bonus = 0.0
    if causal_file.exists():
        try:
            causal = json.loads(causal_file.read_text(encoding="utf-8"))
            chains = causal.get("causal_chains", [])
            causal_bonus = min(50, len(chains) * 10)
        except Exception:
            pass
    quality_bonus += causal_bonus
    quality_details["causal_chains"] = causal_bonus

    # 4-5. 권고사항 보너스
    rec_bonus = 30.0 if "전략적 권고사항" in report_text else 0.0
    quality_bonus += rec_bonus
    quality_details["recommendations"] = rec_bonus

    # 4-6. 시나리오 보너스
    scenario_bonus = 20.0 if "시나리오 분석" in report_text else 0.0
    quality_bonus += scenario_bonus
    quality_details["scenarios"] = scenario_bonus

    # 5. 서사 품질 보너스 v2 (최대 300점)
    narrative_bonus = 0.0
    narrative_details: dict[str, float] = {}

    # 5-1. 해석 밀도: 보고서 내 LLM 해석 단락 수
    # LLM 해석은 보통 테이블/리스트가 아닌 산문 단락으로 나타남
    paragraphs = re.split(r"\n\n+", report_text)
    prose_paragraphs = [
        p for p in paragraphs
        if len(p.strip()) > 80
        and not p.strip().startswith("|")
        and not p.strip().startswith("-")
        and not p.strip().startswith("#")
        and not p.strip().startswith("*")
        and not p.strip().startswith(">")
    ]
    interpret_bonus = min(80, len(prose_paragraphs) * 10)
    narrative_bonus += interpret_bonus
    narrative_details["interpretation_density"] = interpret_bonus

    # 5-2. 데이터 인용률: 보고서에서 엔티티명이 얼마나 언급되는지
    if entity_names:
        mentioned = sum(1 for name in entity_names if name in report_text)
        citation_ratio = mentioned / len(entity_names)
        citation_bonus = min(50, citation_ratio * 60)
    else:
        citation_bonus = 0.0
    narrative_bonus += citation_bonus
    narrative_details["data_citation"] = citation_bonus

    # 5-3. 교차 참조 밀도: 섹션 간 상호 참조 패턴
    cross_ref_patterns = [
        r"인과 분석에서",
        r"구조 분석에서",
        r"시간.*분석에서",
        r"재귀.*분석에서",
        r"교차.*분석에서",
        r"앞서 언급한",
        r"위에서 확인한",
        r"상기 분석",
        r"전술한",
        r"이를 통해",
        r"이는.*일치",
        r"이는.*부합",
        r"이는.*연결",
    ]
    cross_ref_count = sum(
        len(re.findall(pat, report_text)) for pat in cross_ref_patterns
    )
    cross_ref_bonus = min(40, cross_ref_count * 5)
    narrative_bonus += cross_ref_bonus
    narrative_details["cross_reference"] = cross_ref_bonus

    # 5-4. 시뮬레이션 깊이: 실제 시뮬레이션이 얼마나 풍부하게 실행됐는지
    sim_depth_bonus = 0.0
    if agg_file.exists():
        try:
            agg = json.loads(agg_file.read_text(encoding="utf-8"))
            sim = agg.get("simulation_summary", {})
            rounds = sim.get("total_rounds", 0)
            events = sim.get("total_events", 0)
            actions = sim.get("total_actions", 0)
            meta_edges = sim.get("total_meta_edges_fired", 0)
            sim_depth_bonus = min(
                50,
                rounds * 5 + events * 2 + actions * 3 + meta_edges * 2,
            )
        except Exception:
            pass
    narrative_bonus += sim_depth_bonus
    narrative_details["simulation_depth"] = sim_depth_bonus

    # 5-5. 렌즈 교차 종합: cross-lens 인사이트
    lens_cross_file = analysis_dir / "lens_cross.json"
    lens_cross_bonus = 0.0
    if lens_cross_file.exists():
        try:
            cross_data = json.loads(lens_cross_file.read_text(encoding="utf-8"))
            if isinstance(cross_data, list):
                lens_cross_bonus = min(30, len(cross_data) * 10)
        except Exception:
            pass
    narrative_bonus += lens_cross_bonus
    narrative_details["lens_cross"] = lens_cross_bonus

    # 5-6. 부록 풍부함: 테이블 행 수
    appendix_start = report_text.find("부록")
    if appendix_start > 0:
        appendix_text = report_text[appendix_start:]
        table_rows = sum(
            1 for line in appendix_text.split("\n")
            if line.strip().startswith("|") and not line.strip().startswith("|---")
            and not line.strip().startswith("| 항목") and not line.strip().startswith("| 엔티티")
        )
        appendix_bonus = min(50, table_rows * 0.5)
    else:
        appendix_bonus = 0.0
    narrative_bonus += appendix_bonus
    narrative_details["appendix_richness"] = appendix_bonus

    # 6. 구조 품질 패널티 (최대 -150점)
    structural_penalty = 0.0
    penalty_details: dict[str, float] = {}

    # 6-1. 거대 테이블 패널티: 30행 초과 테이블은 읽기 어려움
    lines = report_text.split("\n")
    table_streak = 0
    max_table_size = 0
    for line in lines:
        if line.strip().startswith("|"):
            table_streak += 1
        else:
            max_table_size = max(max_table_size, table_streak)
            table_streak = 0
    max_table_size = max(max_table_size, table_streak)
    if max_table_size > 30:
        big_table_penalty = min(50, (max_table_size - 30) * 1.0)
        structural_penalty += big_table_penalty
        penalty_details["big_table"] = big_table_penalty

    # 6-2. 필러 텍스트 패널티: "제한적입니다", 동일 문구 반복
    filler_patterns = [
        "시뮬레이션 데이터가 제한적",
        "데이터가 충분하지 않",
        "유의미한.*감지되지 않",
    ]
    filler_count = sum(
        len(re.findall(pat, report_text)) for pat in filler_patterns
    )
    if filler_count > 0:
        filler_penalty = min(50, filler_count * 15)
        structural_penalty += filler_penalty
        penalty_details["filler_text"] = filler_penalty

    # 6-3. 동일 패턴 반복 패널티: 테이블 행의 80% 이상이 같은 값
    table_sections = re.findall(r"(\|[^\n]+\n){5,}", report_text)
    for table in table_sections:
        rows = [r.strip() for r in table.strip().split("\n") if r.strip().startswith("|")]
        if len(rows) > 5:
            # 마지막 열 값 추출
            last_cols = []
            for row in rows[2:]:  # 헤더+구분선 제외
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if cells:
                    last_cols.append(cells[-1])
            if last_cols:
                most_common = max(set(last_cols), key=last_cols.count)
                ratio = last_cols.count(most_common) / len(last_cols)
                if ratio > 0.8 and len(last_cols) > 10:
                    repeat_penalty = min(50, int((ratio - 0.8) * 250))
                    structural_penalty += repeat_penalty
                    penalty_details["repeat_pattern"] = repeat_penalty
                    break

    total_score = score + quality_bonus + narrative_bonus - structural_penalty

    # 출력
    print(f"ENTITIES={entity_count}")
    print(f"RELATIONSHIPS={rel_count}")
    print(f"REPORT_WORDS={report_words}")
    print(f"BASE_SCORE={score:.1f}")
    print(f"QUALITY_BONUS={quality_bonus:.1f}")
    for k, v in quality_details.items():
        print(f"  {k}={v:.1f}")
    print(f"NARRATIVE_BONUS={narrative_bonus:.1f}")
    for k, v in narrative_details.items():
        print(f"  {k}={v:.1f}")
    if structural_penalty > 0:
        print(f"STRUCTURAL_PENALTY=-{structural_penalty:.1f}")
        for k, v in penalty_details.items():
            print(f"  {k}=-{v:.1f}")
    print(f"SCORE={total_score:.1f}")

    return total_score


if __name__ == "__main__":
    compute_score()
