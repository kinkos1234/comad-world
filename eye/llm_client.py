"""LLM 클라이언트 — Ollama 네이티브 API (/api/chat) 래퍼

num_ctx(컨텍스트 윈도우)를 설정하기 위해 OpenAI 호환 API 대신
Ollama 네이티브 API를 직접 사용한다.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from utils.config import LLMSettings, load_settings
from utils.logger import log_llm_call, setup_logger

logger = setup_logger()


class CircuitBreaker:
    """Simple circuit breaker for LLM calls.

    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing recovery).
    After `failure_threshold` consecutive failures, opens the circuit for
    `recovery_timeout` seconds. One test call is allowed in HALF_OPEN state.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"  # closed | open | half_open

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self._state = "half_open"
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = "open"
            logger.warning(
                "Circuit breaker OPEN after %d consecutive failures. "
                "Recovery in %ds.",
                self._failure_count, int(self._recovery_timeout),
            )

    def check(self) -> None:
        """Raise if circuit is open."""
        if self.state == "open":
            raise RuntimeError(
                f"LLM circuit breaker open — {self._failure_count} consecutive "
                f"failures. Retry after {int(self._recovery_timeout)}s."
            )


class LLMClient:
    """Ollama 네이티브 API 클라이언트."""

    def __init__(self, settings: LLMSettings | None = None):
        self._settings = settings or load_settings().llm
        # base_url에서 /v1 제거하여 네이티브 API 엔드포인트 구성
        base = self._settings.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self._base_url = base
        self._call_count = 0
        self._total_tokens_in = 0
        self._total_tokens_out = 0
        self._circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def usage_stats(self) -> dict[str, int]:
        """LLM 사용 통계를 반환한다."""
        return {
            "calls": self._call_count,
            "tokens_in": self._total_tokens_in,
            "tokens_out": self._total_tokens_out,
            "tokens_total": self._total_tokens_in + self._total_tokens_out,
        }

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        task_type: str | None = None,
    ) -> str:
        """단일 LLM 호출. timeout 시 프롬프트 자동 축소 재시도.

        task_type이 지정되면 task_overrides에서 파라미터를 조회하여 적용한다.
        명시적으로 전달된 temperature/max_tokens는 task_overrides보다 우선한다.
        """
        self._circuit.check()

        # 태스크별 오버라이드 조회
        overrides = (
            self._settings.task_overrides.get(task_type)
            if task_type
            else None
        )

        temp = (
            temperature
            if temperature is not None
            else (
                overrides.temperature
                if overrides and overrides.temperature is not None
                else self._settings.temperature
            )
        )
        resolved_max_tokens = (
            max_tokens
            if max_tokens is not None
            else (
                overrides.max_tokens
                if overrides and overrides.max_tokens is not None
                else None  # _call_api falls back to settings
            )
        )
        resolved_num_ctx = (
            overrides.num_ctx
            if overrides and overrides.num_ctx is not None
            else None  # _call_api falls back to settings
        )

        max_retries = 3

        current_prompt = prompt
        current_system = system

        for attempt in range(max_retries):
            messages: list[dict[str, str]] = []
            if current_system:
                messages.append({"role": "system", "content": current_system})
            messages.append({"role": "user", "content": current_prompt})

            try:
                content = self._call_api(
                    messages,
                    temp,
                    json_mode,
                    max_tokens=resolved_max_tokens,
                    num_ctx=resolved_num_ctx,
                )

                # JSON 모드일 때 파싱 검증
                if json_mode:
                    json.loads(content)

                self._circuit.record_success()
                return content

            except json.JSONDecodeError:
                logger.warning(
                    f"JSON 파싱 실패 (attempt {attempt + 1}/{max_retries})"
                )
                if attempt == max_retries - 1:
                    raise
            except (httpx.TimeoutException, httpx.ReadTimeout) as e:
                self._circuit.record_failure()
                logger.error(
                    f"LLM timeout (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    # degrade: 프롬프트 축소 후 재시도
                    current_prompt, current_system = self._degrade_prompt(
                        current_prompt, current_system, attempt + 1,
                    )
                    logger.info(
                        f"프롬프트 축소 적용 — "
                        f"prompt {len(prompt)}→{len(current_prompt)}자, "
                        f"system {len(system)}→{len(current_system)}자"
                    )
                else:
                    raise
            except Exception as e:
                self._circuit.record_failure()
                logger.error(
                    f"LLM 호출 실패 (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError("LLM 호출 최대 재시도 초과")

    def _call_api(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        json_mode: bool,
        max_tokens: int | None = None,
        num_ctx: int | None = None,
    ) -> str:
        """Ollama 네이티브 API 호출 (스트리밍 모드).

        stream=True로 토큰을 하나씩 받아 타임아웃을 회피한다.
        로컬 모델이 느려도 토큰이 계속 오는 한 연결이 유지된다.

        max_tokens와 num_ctx가 None이면 settings 전역 값을 사용한다.
        """
        start = time.monotonic()

        effective_max_tokens = max_tokens if max_tokens is not None else self._settings.max_tokens
        effective_num_ctx = num_ctx if num_ctx is not None else self._settings.num_ctx

        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_ctx": effective_num_ctx,
            },
        }

        # qwen3 계열 thinking 모델: thinking 켜되, format:json 회피
        is_thinking_model = "qwen3" in self._settings.model.lower()
        if is_thinking_model:
            # thinking 예산 확보 (thinking + 실제 출력)
            payload["options"]["num_predict"] = effective_max_tokens * 4
            # format:"json"은 thinking과 충돌 → 프롬프트로 JSON 유도
            if json_mode:
                for msg in messages:
                    if msg["role"] == "user":
                        msg["content"] += "\n\nIMPORTANT: 반드시 유효한 JSON만 출력하라. 설명 없이 JSON만."
                        break
        elif json_mode:
            payload["format"] = "json"

        # 스트리밍: connect/write는 짧게, read는 토큰 간격 기준
        stream_read_timeout = min(self._settings.timeout, 120.0)
        timeout = httpx.Timeout(
            connect=30.0,
            read=stream_read_timeout,
            write=30.0,
            pool=30.0,
        )

        content_parts: list[str] = []
        t_in = 0
        t_out = 0

        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 각 스트림 청크에서 토큰 수집
                    msg = chunk.get("message", {})
                    token = msg.get("content", "")
                    if token:
                        content_parts.append(token)

                    # 마지막 청크에 사용량 정보
                    if chunk.get("done"):
                        t_in = chunk.get("prompt_eval_count", 0)
                        t_out = chunk.get("eval_count", 0)

        content = "".join(content_parts)

        # thinking 모델: content가 비어있으면 eval_count 토큰이
        # 전부 thinking에 쓰인 것 → 빈 문자열 반환 (재시도 유도)
        if is_thinking_model and not content.strip() and t_out > 0:
            logger.warning(
                f"thinking 모델 응답이 비어있음 "
                f"(thinking에 {t_out}토큰 소비)"
            )

        # qwen3 thinking 모델: <think>...</think> 잔여 토큰 제거
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL)

        # thinking 모델 + JSON 모드: 자유 텍스트에서 JSON 추출
        if is_thinking_model and json_mode and content.strip():
            content = self._extract_json_from_text(content)

        elapsed = int((time.monotonic() - start) * 1000)

        self._call_count += 1
        self._total_tokens_in += t_in
        self._total_tokens_out += t_out
        log_llm_call(
            prompt=messages[-1]["content"][:500],
            response=content[:500],
            model=self._settings.model,
            tokens_in=t_in,
            tokens_out=t_out,
            duration_ms=elapsed,
        )

        return content

    @staticmethod
    def _degrade_prompt(
        prompt: str,
        system: str,
        attempt: int,
    ) -> tuple[str, str]:
        """timeout 후 프롬프트를 축소한다.

        단계별 축소 전략:
          1차: 프롬프트 텍스트를 60%로 축소
          2차: 프롬프트 텍스트를 40%로 축소 + 시스템 프롬프트 절반 축소
        """
        if attempt == 1:
            # 60% 유지
            cutoff = int(len(prompt) * 0.6)
            if cutoff < len(prompt):
                prompt = prompt[:cutoff] + "\n\n(텍스트 일부 생략)"
        elif attempt >= 2:
            # 40% 유지 + 시스템 축소
            cutoff = int(len(prompt) * 0.4)
            if cutoff < len(prompt):
                prompt = prompt[:cutoff] + "\n\n(텍스트 일부 생략)"
            sys_cutoff = int(len(system) * 0.5)
            if sys_cutoff < len(system):
                system = system[:sys_cutoff]

        return prompt, system

    @staticmethod
    def _extract_json_from_text(text: str) -> str:
        """자유 텍스트에서 JSON 객체/배열을 추출한다.

        thinking 모델이 format:"json" 없이 생성한 응답에서
        첫 번째 유효한 JSON을 찾아 반환한다.
        """
        text = text.strip()

        # 이미 유효한 JSON이면 그대로 반환
        try:
            json.loads(text)
            return text
        except (json.JSONDecodeError, ValueError):
            pass

        # ```json ... ``` 코드 블록 추출
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if code_block:
            candidate = code_block.group(1).strip()
            try:
                json.loads(candidate)
                return candidate
            except (json.JSONDecodeError, ValueError):
                pass

        # 첫 번째 { ... 마지막 } 또는 [ ... ] 추출
        for open_ch, close_ch in [("{", "}"), ("[", "]")]:
            start = text.find(open_ch)
            end = text.rfind(close_ch)
            if start != -1 and end > start:
                candidate = text[start : end + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except (json.JSONDecodeError, ValueError):
                    pass

        # 추출 실패 시 원본 반환 (상위에서 JSONDecodeError 처리)
        return text

    def generate_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        task_type: str | None = None,
    ) -> dict[str, Any]:
        """JSON 응답을 반환하는 LLM 호출."""
        content = self.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            json_mode=True,
            task_type=task_type,
        )
        return json.loads(content)
