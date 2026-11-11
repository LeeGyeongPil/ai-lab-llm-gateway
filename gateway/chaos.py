"""chaos 공급자 — 일부러 오류·지연을 내는 가짜 공급자.

모델 문자열 `chaos/<행동>` 으로 부르면 LiteLLM Router 가 이 핸들러를 호출한다.
핸들러는 진짜 LiteLLM 예외(RateLimitError 등)를 던지므로,
재시도·백오프·폴백은 Router 의 실제 코드가 그대로 돈다.
시도할 때마다 attempts 에 기록해서 "Router 가 몇 번 불렀는지" 를 눈으로 확인한다.

행동:
  ok                성공
  server_error      항상 500 (InternalServerError)
  rate_limit        항상 429 (RateLimitError)
  slow-<ms>         <ms> 만큼 걸린 뒤 성공. 단 timeout 보다 길면 timeout 에서 Timeout 예외
  flaky-<패턴>      패턴(F=실패, S=성공)을 호출 순서대로 반복. 예: flaky-FFS
"""
import threading
import time

import litellm
from litellm import CustomLLM, ModelResponse

from .i18n import GatewayError

MAX_ATTEMPTS = 1000  # 기록이 무한히 쌓이지 않게 하는 상한


class ChaosLLM(CustomLLM):
    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self.attempts = []   # 각 시도: dict(t, behavior, outcome, error_type)
        self._flaky_pos = {}  # 패턴별 현재 위치

    def reset(self):
        with self._lock:
            self.attempts.clear()
            self._flaky_pos.clear()

    def _record(self, behavior, outcome, error_type=None):
        with self._lock:
            if len(self.attempts) < MAX_ATTEMPTS:
                self.attempts.append({"t": time.perf_counter(), "behavior": behavior,
                                      "outcome": outcome, "error_type": error_type})

    def _ok_response(self, model, model_response):
        # 가짜 성공 응답. 토큰은 고정값이라 비용은 "계산 안 됨" 으로 표시된다.
        model_response.choices[0].message.content = "(chaos 공급자의 성공 응답)"
        model_response.model = f"chaos/{model}"
        model_response.usage = litellm.Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        return model_response

    def completion(self, model, messages=None, model_response=None, timeout=None, **kwargs):
        behavior = model  # "chaos/rate_limit" 에서 접두사를 뗀 "rate_limit"
        if behavior == "ok":
            self._record(behavior, "ok")
            return self._ok_response(model, model_response)

        if behavior == "server_error":
            self._record(behavior, "error", "InternalServerError")
            raise litellm.InternalServerError("500 injected", llm_provider="chaos", model=model)

        if behavior == "rate_limit":
            self._record(behavior, "error", "RateLimitError")
            raise litellm.RateLimitError("429 injected", llm_provider="chaos", model=model)

        if behavior.startswith("slow-"):
            delay = int(behavior[5:].removesuffix("ms")) / 1000
            limit = float(timeout) if timeout else None
            if limit is not None and delay > limit:
                # 진짜 HTTP 클라이언트처럼 timeout 에서 포기한다
                time.sleep(limit)
                self._record(behavior, "error", "Timeout")
                raise litellm.Timeout("timeout injected", model=model, llm_provider="chaos")
            time.sleep(delay)
            self._record(behavior, "ok")
            return self._ok_response(model, model_response)

        if behavior.startswith("flaky-"):
            pattern = behavior[6:]
            with self._lock:
                pos = self._flaky_pos.get(pattern, 0)
                self._flaky_pos[pattern] = pos + 1
            if pattern[pos % len(pattern)] == "F":
                self._record(behavior, "error", "InternalServerError")
                raise litellm.InternalServerError("flaky failure", llm_provider="chaos", model=model)
            self._record(behavior, "ok")
            return self._ok_response(model, model_response)

        raise GatewayError("unknown_chaos_behavior", behavior=behavior)


# 프로세스에 하나만 둔다. litellm 에 공급자로 등록한다.
chaos = ChaosLLM()


def register():
    """litellm 에 chaos 공급자를 등록한다 (여러 번 불러도 안전)."""
    litellm.custom_provider_map = [{"provider": "chaos", "custom_handler": chaos}]
