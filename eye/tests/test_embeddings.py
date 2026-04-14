"""Tests for utils/embeddings.py — embedding service, cosine similarity, search."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from comad_eye.embeddings import EmbeddingService


# ---------------------------------------------------------------------------
# Cosine similarity (pure math, no mocks needed)
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        assert EmbeddingService.cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        assert EmbeddingService.cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([-1.0, 0.0], dtype=np.float32)
        assert EmbeddingService.cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_arbitrary_normalized(self):
        a = np.array([0.6, 0.8], dtype=np.float32)
        b = np.array([0.8, 0.6], dtype=np.float32)
        expected = 0.6 * 0.8 + 0.8 * 0.6
        assert EmbeddingService.cosine_similarity(a, b) == pytest.approx(expected, abs=1e-5)


# ---------------------------------------------------------------------------
# Batch cosine similarity
# ---------------------------------------------------------------------------

class TestBatchCosineSimilarity:
    def test_single_corpus(self):
        query = np.array([1.0, 0.0], dtype=np.float32)
        corpus = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        result = EmbeddingService.batch_cosine_similarity(query, corpus)
        np.testing.assert_array_almost_equal(result, [1.0, 0.0])

    def test_empty_corpus(self):
        query = np.array([1.0, 0.0], dtype=np.float32)
        corpus = np.empty((0, 2), dtype=np.float32)
        result = EmbeddingService.batch_cosine_similarity(query, corpus)
        assert len(result) == 0

    def test_multiple_similar(self):
        query = np.array([0.6, 0.8], dtype=np.float32)
        corpus = np.array([
            [0.6, 0.8],  # identical
            [0.8, 0.6],  # similar
            [-0.6, -0.8],  # opposite
        ], dtype=np.float32)
        result = EmbeddingService.batch_cosine_similarity(query, corpus)
        # Identical should be highest
        assert result[0] > result[1]
        # Opposite should be lowest
        assert result[2] < result[1]


# ---------------------------------------------------------------------------
# EmbeddingService initialization
# ---------------------------------------------------------------------------

class TestEmbeddingServiceInit:
    @patch("comad_eye.embeddings.load_settings")
    def test_default_settings(self, mock_settings):
        mock_cfg = MagicMock()
        mock_cfg.embeddings.model = "BAAI/bge-m3"
        mock_cfg.embeddings.device = "cpu"
        mock_cfg.embeddings.batch_size = 32
        mock_settings.return_value = mock_cfg

        svc = EmbeddingService()
        assert svc._settings.model == "BAAI/bge-m3"
        assert svc._model is None  # lazy loaded

    def test_custom_settings(self):
        from comad_eye.config import EmbeddingsSettings
        settings = EmbeddingsSettings(model="test-model", device="cpu", batch_size=8)
        svc = EmbeddingService(settings=settings)
        assert svc._settings.model == "test-model"
        assert svc._settings.batch_size == 8


# ---------------------------------------------------------------------------
# encode / encode_single (mocked model)
# ---------------------------------------------------------------------------

class TestEncode:
    def _make_service(self) -> EmbeddingService:
        from comad_eye.config import EmbeddingsSettings
        svc = EmbeddingService(
            settings=EmbeddingsSettings(model="test", device="cpu")
        )
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array(
            [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32
        )
        svc._model = mock_model
        return svc

    def test_encode_returns_array(self):
        svc = self._make_service()
        result = svc.encode(["hello", "world"])
        assert result.shape == (2, 3)
        assert result.dtype == np.float32

    def test_encode_single_returns_1d(self):
        svc = self._make_service()
        result = svc.encode_single("hello")
        assert result.shape == (3,)

    def test_encode_calls_model_with_correct_params(self):
        svc = self._make_service()
        svc.encode(["test"])
        svc._model.encode.assert_called_once()
        call_kwargs = svc._model.encode.call_args
        assert call_kwargs[1]["show_progress_bar"] is False
        assert call_kwargs[1]["normalize_embeddings"] is True


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_returns_sorted_results(self):
        from comad_eye.config import EmbeddingsSettings
        svc = EmbeddingService(
            settings=EmbeddingsSettings(model="test", device="cpu")
        )

        # Mock encode_single to return a specific query vector
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array(
            [[0.6, 0.8]], dtype=np.float32
        )
        svc._model = mock_model

        corpus_texts = ["text A", "text B", "text C"]
        corpus_emb = np.array([
            [0.6, 0.8],   # cos ~1.0 (identical)
            [0.8, 0.6],   # cos ~0.96
            [-0.6, -0.8],  # cos ~-1.0 (opposite)
        ], dtype=np.float32)

        results = svc.search("query", corpus_texts, corpus_emb, top_k=2)

        assert len(results) == 2
        # First result should be the most similar (index 0)
        assert results[0][0] == 0
        assert results[0][2] == "text A"
        # Second should be index 1
        assert results[1][0] == 1

    def test_search_top_k_limits_results(self):
        from comad_eye.config import EmbeddingsSettings
        svc = EmbeddingService(
            settings=EmbeddingsSettings(model="test", device="cpu")
        )
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array(
            [[1.0, 0.0]], dtype=np.float32
        )
        svc._model = mock_model

        corpus = ["a", "b", "c", "d", "e"]
        emb = np.eye(5, 2, dtype=np.float32)

        results = svc.search("q", corpus, emb, top_k=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# save / load embeddings
# ---------------------------------------------------------------------------

class TestSaveLoadEmbeddings:
    def test_save_and_load_roundtrip(self, tmp_path):
        from comad_eye.config import EmbeddingsSettings
        svc = EmbeddingService(
            settings=EmbeddingsSettings(model="test", device="cpu")
        )

        original = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        path = str(tmp_path / "emb.npy")

        svc.save_embeddings(original, path)
        loaded = EmbeddingService.load_embeddings(path)

        np.testing.assert_array_equal(original, loaded)

    def test_load_embeddings_static(self, tmp_path):
        path = str(tmp_path / "test.npy")
        data = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        np.save(path, data)

        loaded = EmbeddingService.load_embeddings(path)
        np.testing.assert_array_equal(data, loaded)


# ---------------------------------------------------------------------------
# _load_model (mocked)
# ---------------------------------------------------------------------------

class TestLoadModel:
    @patch("comad_eye.embeddings.load_settings")
    def test_lazy_loading(self, mock_settings):
        mock_cfg = MagicMock()
        mock_cfg.embeddings.model = "test-model"
        mock_cfg.embeddings.device = "cpu"
        mock_cfg.embeddings.batch_size = 32
        mock_settings.return_value = mock_cfg

        svc = EmbeddingService()
        assert svc._model is None

    def test_load_model_called_once(self):
        pytest.importorskip("sentence_transformers")
        from comad_eye.config import EmbeddingsSettings
        svc = EmbeddingService(
            settings=EmbeddingsSettings(model="test", device="cpu")
        )
        mock_model = MagicMock()

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_model,
        ):
            result = svc._load_model()
            assert result is mock_model

            # Call again — should return cached model
            result2 = svc._load_model()
            assert result2 is mock_model
