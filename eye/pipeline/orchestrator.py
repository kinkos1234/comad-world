"""파이프라인 오케스트레이터 — 6단계 파이프라인 핵심 로직.

CLI(main.py)와 API(api/routes/pipeline.py) 모두 이 모듈을 통해
파이프라인을 실행한다.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("comadeye")


class PipelineTimer:
    """6단계 파이프라인 타이밍 수집기."""

    def __init__(self) -> None:
        self._timings: dict[str, float] = {}
        self._start: float = time.time()

    def record(self, stage: str, elapsed: float) -> None:
        self._timings[stage] = round(elapsed, 2)

    def summary(self) -> dict[str, float]:
        total = round(time.time() - self._start, 2)
        return {**self._timings, "total": total}

    def log_summary(self) -> None:
        s = self.summary()
        parts = [
            f"ingestion={s.get('ingestion', '-')}s",
            f"graph={s.get('graph', '-')}s",
            f"community={s.get('community', '-')}s",
            f"simulation={s.get('simulation', '-')}s",
            f"analysis={s.get('analysis', '-')}s",
            f"report={s.get('report', '-')}s",
            f"total={s.get('total', '-')}s",
        ]
        msg = f"[perf] Pipeline: {', '.join(parts)}"
        logger.info(msg)
        print(msg)


def run_ingestion(
    seed_text: str,
    settings: Any,
    on_progress: Callable | None = None,
    data_dir: Path | None = None,
) -> tuple[list, Any, dict]:
    """시드 텍스트 → 엔티티/관계 추출 + 벡터 인리치먼트."""
    from ingestion.chunker import TextChunker
    from ingestion.deduplicator import Deduplicator
    from ingestion.enricher import VectorEnricher
    from ingestion.extractor import EntityExtractor
    from ingestion.segmenter import TextSegmenter
    from utils.llm_client import LLMClient

    ext_dir = str(data_dir / "extraction") if data_dir else "data/extraction"
    Path(ext_dir).mkdir(parents=True, exist_ok=True)

    # Layer A: Segment — 의미 단위 분해
    segmenter = TextSegmenter()
    segments = segmenter.segment(seed_text)
    segmenter.save_segments(segments, f"{ext_dir}/segments.jsonl")

    # Chunk — 토큰 기준 청킹
    chunker = TextChunker(
        chunk_size=settings.ingestion.chunk_size,
        chunk_overlap=settings.ingestion.chunk_overlap,
    )
    chunks = chunker.chunk_text(seed_text)
    chunker.save_chunks(chunks, f"{ext_dir}/chunks.jsonl")

    # Layer B+C: Extract + Merge
    llm = LLMClient(settings=settings.llm)
    extractor = EntityExtractor(
        llm,
        cache_dir=f"{ext_dir}/chunk_results",
        on_progress=on_progress,
        concurrency=settings.ingestion.extraction_concurrency,
    )
    ontology = extractor.extract(chunks, segments=segments)
    extractor.save_results(ontology, ext_dir)

    dedup = Deduplicator()
    ontology = dedup.deduplicate(ontology)
    dedup.save_merge_log(f"{ext_dir}/merge_log.json")

    from utils.embeddings import EmbeddingService
    emb = EmbeddingService(settings=settings.embeddings)
    enricher = VectorEnricher(embedding_service=emb)
    enrichment = enricher.enrich(ontology)
    enricher.save_index(enrichment, ext_dir)

    return chunks, ontology, llm.usage_stats


def run_graph_loading(ontology: Any, settings: Any) -> Any:
    """온톨로지를 Neo4j 그래프에 로드한다."""
    from graph.loader import GraphLoader
    from graph.neo4j_client import Neo4jClient

    client = Neo4jClient(settings=settings.neo4j)
    client.clear_all()
    loader = GraphLoader(client)
    loader.load(ontology)
    return client


def run_community_detection(client: Any, settings: Any) -> dict:
    """커뮤니티 탐지 + LLM 기반 커뮤니티 요약."""
    from graph.community import CommunityDetector
    from graph.summarizer import CommunitySummarizer
    from utils.llm_client import LLMClient

    detector = CommunityDetector(client)
    result = detector.detect()

    llm = LLMClient(settings=settings.llm)
    summarizer = CommunitySummarizer(client, llm)
    summarizer.summarize(result["communities"])
    return llm.usage_stats


def run_simulation(
    client: Any,
    ontology: Any,
    settings: Any,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """시뮬레이션 엔진을 실행하고 결과 메타데이터를 반환한다."""
    from ontology.action_registry import ActionRegistry
    from ontology.meta_edge_engine import MetaEdgeEngine
    from simulation.engine import SimulationEngine
    from simulation.event_chain import SimEvent
    from utils.active_metadata import ActiveMetadataBus

    snapshot_dir = str(data_dir / "snapshots") if data_dir else "data/snapshots"
    Path(snapshot_dir).mkdir(parents=True, exist_ok=True)

    meta_engine = MetaEdgeEngine()
    action_registry = ActionRegistry()
    metadata_bus = ActiveMetadataBus()

    engine = SimulationEngine(
        client=client,
        meta_edge_engine=meta_engine,
        action_registry=action_registry,
        metadata_bus=metadata_bus,
        settings=settings.simulation,
        snapshot_dir=snapshot_dir,
    )

    # 이벤트 노드에서 SimEvent 생성
    events_data = client.query(
        "MATCH (n:Entity) WHERE n.object_type = 'Event' "
        "RETURN n.uid AS uid, n.name AS name, "
        "n.magnitude AS magnitude"
    )
    events = [
        SimEvent(
            uid=e["uid"],
            name=e.get("name", e["uid"]),
            magnitude=float(e.get("magnitude") or 0.5),
        )
        for e in (events_data or [])
    ]

    result = engine.run(events)

    return {
        "total_rounds": result.total_rounds,
        "total_events": result.total_events,
        "total_actions": result.total_actions,
        "total_meta_edges": result.total_meta_edges_fired,
        "total_migrations": result.total_community_migrations,
    }


def run_analysis(
    client: Any,
    settings: Any,
    *,
    lenses: list[str] | None = None,
    seed_text: str = "",
    analysis_prompt: str | None = None,
    settings_override: dict | None = None,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """6개 분석공간 + 렌즈 딥 필터를 실행한다."""
    from analysis.aggregator import AnalysisAggregator
    from analysis.base import SimulationData
    from utils.llm_client import LLMClient

    snapshot_dir = str(data_dir / "snapshots") if data_dir else "data/snapshots"
    analysis_dir = str(data_dir / "analysis") if data_dir else "data/analysis"

    data = SimulationData.from_snapshots(snapshot_dir, graph=client)
    llm = LLMClient(settings=settings.llm)

    aggregator = AnalysisAggregator(
        data,
        analysis_dir,
        llm=llm,
        selected_lenses=lenses,
        seed_text=seed_text,
        analysis_prompt=analysis_prompt,
        settings_override=settings_override,
        graph_client=client,
        parallel=settings.analysis.parallel,
    )
    return aggregator.run_all()


def run_report(
    seed_text: str,
    sim_result: dict,
    output_dir: Path | str,
    settings: Any,
    *,
    analysis_prompt: str | None = None,
    data_dir: Path | None = None,
) -> tuple[Path, dict]:
    """분석 결과 → 마크다운 리포트 생성."""
    from narration.report_generator import ReportGenerator
    from utils.llm_client import LLMClient

    analysis_dir = str(data_dir / "analysis") if data_dir else "data/analysis"

    llm = LLMClient(settings=settings.llm)
    generator = ReportGenerator(llm, analysis_dir, output_dir)
    path = generator.generate(
        seed_excerpt=seed_text[:500],
        metadata=sim_result,
        analysis_prompt=analysis_prompt,
    )
    return path, llm.usage_stats


def run_full_pipeline(
    seed_text: str,
    settings: Any,
    output_dir: Path | str = "output",
    *,
    on_progress: Callable | None = None,
    data_dir: Path | None = None,
    skip_report: bool = False,
    lenses: list[str] | None = None,
    analysis_prompt: str | None = None,
) -> dict[str, Any]:
    """6단계 파이프라인을 타이밍과 함께 실행한다."""
    timer = PipelineTimer()

    t = time.time()
    chunks, ontology, usage = run_ingestion(
        seed_text, settings, on_progress=on_progress, data_dir=data_dir,
    )
    timer.record("ingestion", time.time() - t)

    t = time.time()
    client = run_graph_loading(ontology, settings)
    timer.record("graph", time.time() - t)

    t = time.time()
    run_community_detection(client, settings)
    timer.record("community", time.time() - t)

    t = time.time()
    sim_result = run_simulation(client, ontology, settings, data_dir=data_dir)
    timer.record("simulation", time.time() - t)

    t = time.time()
    run_analysis(
        client, settings, seed_text=seed_text, lenses=lenses,
        analysis_prompt=analysis_prompt, data_dir=data_dir,
    )
    timer.record("analysis", time.time() - t)

    report_path = None
    if not skip_report:
        t = time.time()
        report_path, _ = run_report(
            seed_text, sim_result, output_dir, settings,
            analysis_prompt=analysis_prompt, data_dir=data_dir,
        )
        timer.record("report", time.time() - t)

    timer.log_summary()

    return {
        "sim_result": sim_result,
        "report_path": report_path,
        "timings": timer.summary(),
    }
