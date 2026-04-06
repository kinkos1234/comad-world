"""디바이스 스펙 감지 + 모델 적합도 판정

서버 시작 시 RAM, CPU 등을 감지하고,
Ollama 모델 크기와 비교하여 safe/warning/danger 판정을 내린다.
"""

from __future__ import annotations

import logging
import platform
import re
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("comadeye")


@dataclass
class DeviceInfo:
    """시스템 하드웨어 정보."""
    total_ram_gb: float = 0.0
    cpu_cores: int = 0
    cpu_brand: str = ""
    gpu_type: str = ""  # "mps", "cuda", "cpu"
    os_name: str = ""
    arch: str = ""


@dataclass
class ModelRecommendation:
    """모델별 적합도 판정 결과."""
    name: str
    size_gb: float = 0.0
    parameter_size: str = ""  # e.g. "32B", "7B"
    fitness: str = "unknown"  # safe / warning / danger / unknown
    reason: str = ""


def detect_device() -> DeviceInfo:
    """현재 시스템의 하드웨어 스펙을 감지한다."""
    info = DeviceInfo()

    # OS / Architecture
    info.os_name = platform.system()  # Darwin, Linux, Windows
    info.arch = platform.machine()  # arm64, x86_64

    # RAM
    try:
        import psutil
        info.total_ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        # psutil 없으면 macOS sysctl 시도
        if info.os_name == "Darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True, timeout=3,
                )
                info.total_ram_gb = round(int(result.stdout.strip()) / (1024 ** 3), 1)
            except Exception:
                pass
        elif info.os_name == "Linux":
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            info.total_ram_gb = round(kb / (1024 ** 2), 1)
                            break
            except Exception:
                pass

    # CPU cores
    try:
        import os
        info.cpu_cores = os.cpu_count() or 0
    except Exception:
        pass

    # CPU brand
    info.cpu_brand = platform.processor() or ""

    # GPU type detection
    if info.os_name == "Darwin" and info.arch == "arm64":
        info.gpu_type = "mps"
    else:
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                info.gpu_type = "cuda"
            else:
                info.gpu_type = "cpu"
        except Exception:
            info.gpu_type = "cpu"

    logger.info(
        f"디바이스 감지: RAM={info.total_ram_gb}GB, "
        f"CPU={info.cpu_cores}코어, GPU={info.gpu_type}, "
        f"OS={info.os_name}/{info.arch}"
    )
    return info


def _parse_parameter_size(param_str: str) -> float:
    """파라미터 크기 문자열을 십억(B) 단위 숫자로 변환한다.

    Examples: "32B" -> 32.0, "7.5B" -> 7.5, "3.5B" -> 3.5
    """
    if not param_str:
        return 0.0
    match = re.search(r"([\d.]+)\s*[Bb]", param_str)
    if match:
        return float(match.group(1))
    return 0.0


def _estimate_required_ram(size_gb: float, param_billions: float) -> float:
    """모델 실행에 필요한 예상 RAM(GB)을 추정한다.

    Ollama는 모델 파일 크기 외에 KV cache, 런타임 오버헤드가 필요.
    경험적으로 모델 파일 크기 × 1.2 + 2GB 오버헤드.
    """
    if size_gb > 0:
        return size_gb * 1.2 + 2.0
    # size_gb 없으면 파라미터 수로 추정 (Q4 양자화 기준: ~0.5GB/B)
    if param_billions > 0:
        return param_billions * 0.5 * 1.2 + 2.0
    return 0.0


def evaluate_model_fitness(
    device: DeviceInfo,
    model_name: str,
    size_gb: float = 0.0,
    parameter_size: str = "",
) -> ModelRecommendation:
    """디바이스 스펙 대비 모델 적합도를 판정한다."""
    rec = ModelRecommendation(
        name=model_name,
        size_gb=size_gb,
        parameter_size=parameter_size,
    )

    param_b = _parse_parameter_size(parameter_size)
    # 모델 이름에서 파라미터 크기 추정 시도
    if param_b == 0.0:
        match = re.search(r"(\d+(?:\.\d+)?)[bB]", model_name)
        if match:
            param_b = float(match.group(1))
            rec.parameter_size = f"{param_b}B"

    required_ram = _estimate_required_ram(size_gb, param_b)

    if device.total_ram_gb <= 0 or required_ram <= 0:
        rec.fitness = "unknown"
        rec.reason = "디바이스 RAM 또는 모델 크기를 확인할 수 없습니다"
        return rec

    # 남은 RAM 여유 (OS + 다른 프로세스용 ~4GB 예약)
    available_for_model = device.total_ram_gb - 4.0
    ratio = required_ram / available_for_model if available_for_model > 0 else 999

    if ratio <= 0.6:
        rec.fitness = "safe"
        rec.reason = (
            f"충분한 여유 (필요 ~{required_ram:.0f}GB / "
            f"가용 ~{available_for_model:.0f}GB)"
        )
    elif ratio <= 0.85:
        rec.fitness = "warning"
        rec.reason = (
            f"여유 부족 가능 (필요 ~{required_ram:.0f}GB / "
            f"가용 ~{available_for_model:.0f}GB) — 느려질 수 있음"
        )
    else:
        rec.fitness = "danger"
        rec.reason = (
            f"RAM 초과 위험 (필요 ~{required_ram:.0f}GB / "
            f"가용 ~{available_for_model:.0f}GB) — 500 에러 가능"
        )

    # Thinking 모델 경고 (qwen3 계열)
    if "qwen3" in model_name.lower():
        if rec.fitness == "safe":
            rec.fitness = "warning"
        rec.reason += (
            " | ⚠️ thinking 모델: JSON 구조화 작업에서 3~5배 느림. "
            "llama3.1 계열 권장"
        )

    return rec


def get_ollama_model_details(
    base_url: str,
    model_names: list[str],
) -> dict[str, dict[str, Any]]:
    """Ollama API로 각 모델의 상세 정보(크기, 파라미터)를 조회한다."""
    details: dict[str, dict[str, Any]] = {}

    for name in model_names:
        try:
            resp = httpx.post(
                f"{base_url}/api/show",
                json={"name": name},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                model_info = data.get("model_info", {})

                # 파라미터 크기 추출
                param_size = ""
                for key, val in model_info.items():
                    if "parameter" in key.lower() and "size" in key.lower():
                        param_size = str(val)
                        break
                # details에서도 시도
                if not param_size:
                    details_section = data.get("details", {})
                    param_size = details_section.get("parameter_size", "")

                # 모델 파일 크기 (bytes → GB)
                size_bytes = data.get("size", 0)
                size_gb = round(size_bytes / (1024 ** 3), 1) if size_bytes else 0.0

                details[name] = {
                    "size_gb": size_gb,
                    "parameter_size": param_size,
                    "family": data.get("details", {}).get("family", ""),
                    "quantization": data.get("details", {}).get(
                        "quantization_level", ""
                    ),
                }
        except Exception as e:
            logger.debug(f"모델 상세 조회 실패 ({name}): {e}")
            details[name] = {}

    return details


def evaluate_all_models(
    device: DeviceInfo,
    base_url: str,
    model_names: list[str],
) -> list[ModelRecommendation]:
    """모든 사용 가능한 모델의 적합도를 한번에 판정한다."""
    model_details = get_ollama_model_details(base_url, model_names)

    recommendations = []
    for name in model_names:
        detail = model_details.get(name, {})
        rec = evaluate_model_fitness(
            device=device,
            model_name=name,
            size_gb=detail.get("size_gb", 0.0),
            parameter_size=detail.get("parameter_size", ""),
        )
        recommendations.append(rec)

    return recommendations
