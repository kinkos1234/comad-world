"""Extended tests for pipeline/orchestrator.py — mock-based function execution tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile


# ---------------------------------------------------------------------------
# run_ingestion tests
# ---------------------------------------------------------------------------

class TestRunIngestion:
    @patch("comad_eye.ingestion.enricher.VectorEnricher")
    @patch("comad_eye.embeddings.EmbeddingService")
    @patch("comad_eye.ingestion.deduplicator.Deduplicator")
    @patch("comad_eye.ingestion.extractor.EntityExtractor")
    @patch("comad_eye.ingestion.chunker.TextChunker")
    @patch("comad_eye.ingestion.segmenter.TextSegmenter")
    @patch("comad_eye.llm_client.LLMClient")
    def test_run_ingestion_returns_tuple(
        self, MockLLM, MockSeg, MockChunk, MockExt, MockDedup, MockEmb, MockEnrich
    ):
        from comad_eye.pipeline.orchestrator import run_ingestion

        mock_settings = MagicMock()
        mock_settings.ingestion.chunk_size = 300
        mock_settings.ingestion.chunk_overlap = 50
        mock_settings.ingestion.extraction_concurrency = 1

        mock_seg_inst = MockSeg.return_value
        mock_seg_inst.segment.return_value = [MagicMock()]

        mock_chunk_inst = MockChunk.return_value
        mock_chunk_inst.chunk_text.return_value = [MagicMock()]

        mock_ontology = MagicMock()
        mock_ext_inst = MockExt.return_value
        mock_ext_inst.extract.return_value = mock_ontology

        mock_dedup_inst = MockDedup.return_value
        mock_dedup_inst.deduplicate.return_value = mock_ontology

        mock_llm_inst = MockLLM.return_value
        mock_llm_inst.usage_stats = {"tokens": 100}

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            result = run_ingestion("test seed text", mock_settings, data_dir=data_dir)

        assert len(result) == 3  # chunks, ontology, usage_stats
        mock_seg_inst.segment.assert_called_once()
        mock_chunk_inst.chunk_text.assert_called_once()
        mock_ext_inst.extract.assert_called_once()

    @patch("comad_eye.ingestion.enricher.VectorEnricher")
    @patch("comad_eye.embeddings.EmbeddingService")
    @patch("comad_eye.ingestion.deduplicator.Deduplicator")
    @patch("comad_eye.ingestion.extractor.EntityExtractor")
    @patch("comad_eye.ingestion.chunker.TextChunker")
    @patch("comad_eye.ingestion.segmenter.TextSegmenter")
    @patch("comad_eye.llm_client.LLMClient")
    def test_run_ingestion_with_progress_callback(
        self, MockLLM, MockSeg, MockChunk, MockExt, MockDedup, MockEmb, MockEnrich
    ):
        from comad_eye.pipeline.orchestrator import run_ingestion

        mock_settings = MagicMock()
        mock_settings.ingestion.chunk_size = 300
        mock_settings.ingestion.chunk_overlap = 50
        mock_settings.ingestion.extraction_concurrency = 1

        MockSeg.return_value.segment.return_value = []
        MockChunk.return_value.chunk_text.return_value = []
        MockExt.return_value.extract.return_value = MagicMock()
        MockDedup.return_value.deduplicate.return_value = MagicMock()
        MockLLM.return_value.usage_stats = {}

        on_progress = MagicMock()

        with tempfile.TemporaryDirectory() as tmp:
            run_ingestion("text", mock_settings, on_progress=on_progress, data_dir=Path(tmp))

        # Progress callback is passed to EntityExtractor
        MockExt.assert_called_once()
        _, kwargs = MockExt.call_args
        assert kwargs.get("on_progress") is on_progress


# ---------------------------------------------------------------------------
# run_graph_loading tests
# ---------------------------------------------------------------------------

class TestRunGraphLoading:
    @patch("comad_eye.graph.loader.GraphLoader")
    @patch("comad_eye.graph.neo4j_client.Neo4jClient")
    def test_run_graph_loading(self, MockClient, MockLoader):
        from comad_eye.pipeline.orchestrator import run_graph_loading

        mock_settings = MagicMock()
        mock_client_inst = MockClient.return_value
        mock_loader_inst = MockLoader.return_value

        ontology = MagicMock()
        result = run_graph_loading(ontology, mock_settings)

        mock_client_inst.clear_all.assert_called_once()
        mock_loader_inst.load.assert_called_once_with(ontology)
        assert result is mock_client_inst


# ---------------------------------------------------------------------------
# run_community_detection tests
# ---------------------------------------------------------------------------

class TestRunCommunityDetection:
    @patch("comad_eye.llm_client.LLMClient")
    @patch("comad_eye.graph.summarizer.CommunitySummarizer")
    @patch("comad_eye.graph.community.CommunityDetector")
    def test_run_community_detection(self, MockDetector, MockSummarizer, MockLLM):
        from comad_eye.pipeline.orchestrator import run_community_detection

        mock_settings = MagicMock()
        mock_client = MagicMock()

        mock_det_inst = MockDetector.return_value
        mock_det_inst.detect.return_value = {"communities": {"C0": {}}}

        mock_llm_inst = MockLLM.return_value
        mock_llm_inst.usage_stats = {"tokens": 50}

        result = run_community_detection(mock_client, mock_settings)

        mock_det_inst.detect.assert_called_once()
        MockSummarizer.return_value.summarize.assert_called_once()
        assert result == {"tokens": 50}


# ---------------------------------------------------------------------------
# run_simulation tests
# ---------------------------------------------------------------------------

class TestRunSimulation:
    @patch("comad_eye.active_metadata.ActiveMetadataBus")
    @patch("comad_eye.simulation.engine.SimulationEngine")
    @patch("comad_eye.ontology.action_registry.ActionRegistry")
    @patch("comad_eye.ontology.meta_edge_engine.MetaEdgeEngine")
    def test_run_simulation(self, MockMeta, MockAction, MockEngine, MockBus):
        from comad_eye.pipeline.orchestrator import run_simulation

        mock_settings = MagicMock()
        mock_client = MagicMock()
        mock_ontology = MagicMock()

        # Mock events query
        mock_client.query.return_value = [
            {"uid": "ev1", "name": "Event1", "magnitude": 0.8},
        ]

        mock_sim_result = MagicMock()
        mock_sim_result.total_rounds = 10
        mock_sim_result.total_events = 1
        mock_sim_result.total_actions = 5
        mock_sim_result.total_meta_edges_fired = 3
        mock_sim_result.total_community_migrations = 2

        MockEngine.return_value.run.return_value = mock_sim_result

        with tempfile.TemporaryDirectory() as tmp:
            result = run_simulation(mock_client, mock_ontology, mock_settings, data_dir=Path(tmp))

        assert result["total_rounds"] == 10
        assert result["total_events"] == 1
        assert result["total_actions"] == 5

    @patch("comad_eye.active_metadata.ActiveMetadataBus")
    @patch("comad_eye.simulation.engine.SimulationEngine")
    @patch("comad_eye.ontology.action_registry.ActionRegistry")
    @patch("comad_eye.ontology.meta_edge_engine.MetaEdgeEngine")
    def test_run_simulation_no_events(self, MockMeta, MockAction, MockEngine, MockBus):
        from comad_eye.pipeline.orchestrator import run_simulation

        mock_settings = MagicMock()
        mock_client = MagicMock()
        mock_client.query.return_value = []

        mock_sim_result = MagicMock()
        mock_sim_result.total_rounds = 0
        mock_sim_result.total_events = 0
        mock_sim_result.total_actions = 0
        mock_sim_result.total_meta_edges_fired = 0
        mock_sim_result.total_community_migrations = 0

        MockEngine.return_value.run.return_value = mock_sim_result

        with tempfile.TemporaryDirectory() as tmp:
            result = run_simulation(mock_client, MagicMock(), mock_settings, data_dir=Path(tmp))

        assert result["total_events"] == 0


# ---------------------------------------------------------------------------
# run_analysis tests
# ---------------------------------------------------------------------------

class TestRunAnalysis:
    @patch("comad_eye.analysis.aggregator.AnalysisAggregator")
    @patch("comad_eye.analysis.base.SimulationData")
    @patch("comad_eye.llm_client.LLMClient")
    def test_run_analysis(self, MockLLM, MockSimData, MockAgg):
        from comad_eye.pipeline.orchestrator import run_analysis

        mock_settings = MagicMock()
        mock_settings.analysis.parallel = True
        mock_client = MagicMock()

        MockAgg.return_value.run_all.return_value = {"spaces": 6}

        with tempfile.TemporaryDirectory() as tmp:
            result = run_analysis(mock_client, mock_settings, data_dir=Path(tmp))

        assert result == {"spaces": 6}
        MockAgg.return_value.run_all.assert_called_once()


# ---------------------------------------------------------------------------
# run_report tests
# ---------------------------------------------------------------------------

class TestRunReport:
    @patch("comad_eye.narration.report_generator.ReportGenerator")
    @patch("comad_eye.llm_client.LLMClient")
    def test_run_report(self, MockLLM, MockGen):
        from comad_eye.pipeline.orchestrator import run_report

        mock_settings = MagicMock()
        mock_llm_inst = MockLLM.return_value
        mock_llm_inst.usage_stats = {"tokens": 200}

        MockGen.return_value.generate.return_value = Path("/tmp/report.md")

        with tempfile.TemporaryDirectory() as tmp:
            path, usage = run_report(
                "seed text", {"rounds": 10}, tmp, mock_settings, data_dir=Path(tmp),
            )

        assert str(path).endswith("report.md")
        assert usage == {"tokens": 200}
