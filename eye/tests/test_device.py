"""Tests for utils/device.py — device detection and model fitness evaluation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comad_eye.device import (
    DeviceInfo,
    ModelRecommendation,
    _estimate_required_ram,
    _parse_parameter_size,
    detect_device,
    evaluate_all_models,
    evaluate_model_fitness,
    get_ollama_model_details,
)


# ---------------------------------------------------------------------------
# _parse_parameter_size
# ---------------------------------------------------------------------------

class TestParseParameterSize:
    def test_standard_format(self):
        assert _parse_parameter_size("32B") == 32.0

    def test_decimal_format(self):
        assert _parse_parameter_size("7.5B") == 7.5

    def test_lowercase_b(self):
        assert _parse_parameter_size("3.5b") == 3.5

    def test_with_spaces(self):
        assert _parse_parameter_size("8 B") == 8.0

    def test_empty_string(self):
        assert _parse_parameter_size("") == 0.0

    def test_no_match(self):
        assert _parse_parameter_size("unknown") == 0.0

    def test_none_like_empty(self):
        # Empty string returns 0.0
        assert _parse_parameter_size("") == 0.0


# ---------------------------------------------------------------------------
# _estimate_required_ram
# ---------------------------------------------------------------------------

class TestEstimateRequiredRam:
    def test_with_size_gb(self):
        # size_gb * 1.2 + 2.0
        result = _estimate_required_ram(10.0, 0.0)
        assert result == pytest.approx(14.0)

    def test_with_param_billions_only(self):
        # param_billions * 0.5 * 1.2 + 2.0
        result = _estimate_required_ram(0.0, 8.0)
        assert result == pytest.approx(6.8)

    def test_size_gb_takes_priority(self):
        # size_gb > 0, so it's used even if param_billions is also provided
        result = _estimate_required_ram(5.0, 7.0)
        assert result == pytest.approx(8.0)

    def test_both_zero(self):
        assert _estimate_required_ram(0.0, 0.0) == 0.0

    def test_small_model(self):
        result = _estimate_required_ram(2.0, 0.0)
        assert result == pytest.approx(4.4)


# ---------------------------------------------------------------------------
# DeviceInfo dataclass
# ---------------------------------------------------------------------------

class TestDeviceInfo:
    def test_defaults(self):
        info = DeviceInfo()
        assert info.total_ram_gb == 0.0
        assert info.cpu_cores == 0
        assert info.gpu_type == ""

    def test_custom_values(self):
        info = DeviceInfo(total_ram_gb=64.0, cpu_cores=10, gpu_type="mps")
        assert info.total_ram_gb == 64.0
        assert info.cpu_cores == 10
        assert info.gpu_type == "mps"


# ---------------------------------------------------------------------------
# ModelRecommendation dataclass
# ---------------------------------------------------------------------------

class TestModelRecommendation:
    def test_defaults(self):
        rec = ModelRecommendation(name="test-model")
        assert rec.fitness == "unknown"
        assert rec.size_gb == 0.0
        assert rec.reason == ""

    def test_custom(self):
        rec = ModelRecommendation(
            name="llama3.1:8b",
            size_gb=4.7,
            parameter_size="8B",
            fitness="safe",
            reason="ok",
        )
        assert rec.name == "llama3.1:8b"
        assert rec.fitness == "safe"


# ---------------------------------------------------------------------------
# evaluate_model_fitness
# ---------------------------------------------------------------------------

class TestEvaluateModelFitness:
    def _device(self, ram: float = 64.0) -> DeviceInfo:
        return DeviceInfo(
            total_ram_gb=ram,
            cpu_cores=10,
            gpu_type="mps",
            os_name="Darwin",
            arch="arm64",
        )

    def test_safe_with_plenty_of_ram(self):
        # 64GB RAM, 4.7GB model: required ~7.6GB, available ~60GB → ratio ~0.13
        rec = evaluate_model_fitness(
            self._device(64.0), "llama3.1:8b", size_gb=4.7, parameter_size="8B"
        )
        assert rec.fitness == "safe"
        assert rec.name == "llama3.1:8b"

    def test_warning_with_moderate_ram(self):
        # 16GB RAM, ~18GB model: required ~23.6, available ~12 → ratio ~1.97 → danger
        rec = evaluate_model_fitness(
            self._device(16.0), "qwen2.5:32b", size_gb=18.0, parameter_size="32B"
        )
        assert rec.fitness == "danger"

    def test_danger_with_insufficient_ram(self):
        # 8GB RAM, 18GB model: available = 4GB, required ~23.6 → ratio >> 1
        rec = evaluate_model_fitness(
            self._device(8.0), "big-model", size_gb=18.0, parameter_size="32B"
        )
        assert rec.fitness == "danger"

    def test_unknown_when_no_ram_info(self):
        device = DeviceInfo(total_ram_gb=0.0)
        rec = evaluate_model_fitness(device, "any-model", size_gb=5.0)
        assert rec.fitness == "unknown"

    def test_unknown_when_no_model_info(self):
        rec = evaluate_model_fitness(
            self._device(64.0), "mystery-model", size_gb=0.0, parameter_size=""
        )
        assert rec.fitness == "unknown"

    def test_qwen3_warning_escalation(self):
        # Safe model but qwen3 → warning due to thinking model penalty
        rec = evaluate_model_fitness(
            self._device(64.0), "qwen3:8b", size_gb=4.7, parameter_size="8B"
        )
        assert rec.fitness == "warning"
        assert "thinking" in rec.reason.lower() or "thinking" in rec.reason

    def test_parameter_size_inferred_from_model_name(self):
        # No explicit parameter_size, but model name contains "7b"
        rec = evaluate_model_fitness(
            self._device(64.0), "llama3.1:7b", size_gb=4.0
        )
        assert rec.parameter_size == "7.0B"
        assert rec.fitness == "safe"

    def test_warning_zone(self):
        # Construct a scenario where ratio is between 0.6 and 0.85
        # available = 20 - 4 = 16, required = 10 * 1.2 + 2 = 14 → ratio = 14/16 = 0.875 → danger
        # Actually: 14/16 = 0.875 > 0.85 → danger. Let me adjust.
        # required = 8 * 1.2 + 2 = 11.6, available = 20-4=16, ratio=11.6/16=0.725 → warning
        rec = evaluate_model_fitness(
            self._device(20.0), "model:14b", size_gb=8.0, parameter_size="14B"
        )
        assert rec.fitness == "warning"

    def test_available_ram_zero_or_negative(self):
        # total_ram <= 4, so available_for_model <= 0 → ratio = 999 → danger
        rec = evaluate_model_fitness(
            self._device(3.0), "small-model", size_gb=1.0, parameter_size="1B"
        )
        assert rec.fitness == "danger"


# ---------------------------------------------------------------------------
# detect_device (mocked)
# ---------------------------------------------------------------------------

class TestDetectDevice:
    @patch("comad_eye.device.platform")
    def test_basic_detection(self, mock_platform):
        mock_platform.system.return_value = "Darwin"
        mock_platform.machine.return_value = "arm64"
        mock_platform.processor.return_value = "Apple M1 Max"

        with patch.dict("sys.modules", {"psutil": MagicMock()}):
            import sys
            mock_psutil = sys.modules["psutil"]
            mock_vm = MagicMock()
            mock_vm.total = 64 * (1024 ** 3)  # 64 GB
            mock_psutil.virtual_memory.return_value = mock_vm

            with patch("os.cpu_count", return_value=10):
                info = detect_device()

        assert info.os_name == "Darwin"
        assert info.arch == "arm64"
        assert info.gpu_type == "mps"

    @patch("comad_eye.device.platform")
    def test_linux_detection_without_psutil(self, mock_platform):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.processor.return_value = "Intel"

        # Simulate psutil not available
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("No module named 'psutil'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with patch("os.cpu_count", return_value=8):
                # Also mock nvidia-smi to fail
                with patch("subprocess.run", side_effect=FileNotFoundError):
                    info = detect_device()

        assert info.os_name == "Linux"
        assert info.arch == "x86_64"


# ---------------------------------------------------------------------------
# get_ollama_model_details (mocked HTTP)
# ---------------------------------------------------------------------------

class TestGetOllamaModelDetails:
    @patch("comad_eye.device.httpx.post")
    def test_successful_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "model_info": {
                "general.parameter_size": "8B",
            },
            "details": {
                "family": "llama",
                "quantization_level": "Q4_K_M",
                "parameter_size": "8B",
            },
            "size": 4_700_000_000,
        }
        mock_post.return_value = mock_resp

        result = get_ollama_model_details(
            "http://localhost:11434", ["llama3.1:8b"]
        )

        assert "llama3.1:8b" in result
        detail = result["llama3.1:8b"]
        assert detail["size_gb"] == pytest.approx(4.4, abs=0.2)
        assert detail["family"] == "llama"

    @patch("comad_eye.device.httpx.post")
    def test_failed_request(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        result = get_ollama_model_details(
            "http://localhost:11434", ["missing-model"]
        )
        assert result["missing-model"] == {}

    @patch("comad_eye.device.httpx.post")
    def test_non_200_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_post.return_value = mock_resp

        result = get_ollama_model_details(
            "http://localhost:11434", ["unknown"]
        )
        # Non-200 responses are silently skipped — no entry for the model
        assert "unknown" not in result

    @patch("comad_eye.device.httpx.post")
    def test_multiple_models(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "model_info": {},
            "details": {"parameter_size": "7B"},
            "size": 3_500_000_000,
        }
        mock_post.return_value = mock_resp

        result = get_ollama_model_details(
            "http://localhost:11434", ["model-a", "model-b"]
        )
        assert len(result) == 2
        assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# evaluate_all_models (integration of fitness + details)
# ---------------------------------------------------------------------------

class TestEvaluateAllModels:
    @patch("comad_eye.device.get_ollama_model_details")
    def test_evaluates_all(self, mock_details):
        mock_details.return_value = {
            "model-a": {"size_gb": 4.0, "parameter_size": "8B"},
            "model-b": {"size_gb": 18.0, "parameter_size": "32B"},
        }
        device = DeviceInfo(total_ram_gb=64.0, cpu_cores=10, gpu_type="mps")
        results = evaluate_all_models(device, "http://localhost:11434", ["model-a", "model-b"])

        assert len(results) == 2
        assert results[0].name == "model-a"
        assert results[0].fitness == "safe"

    @patch("comad_eye.device.get_ollama_model_details")
    def test_handles_missing_details(self, mock_details):
        mock_details.return_value = {"model-a": {}}
        device = DeviceInfo(total_ram_gb=64.0, cpu_cores=10, gpu_type="mps")
        results = evaluate_all_models(device, "http://localhost:11434", ["model-a"])

        assert len(results) == 1
        assert results[0].fitness == "unknown"
