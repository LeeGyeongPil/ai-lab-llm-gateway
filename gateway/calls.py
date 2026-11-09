"""ask() — 게이트웨이를 통한 호출 1번과 그 기록.

지연은 앱 쪽 time.perf_counter() 로 직접 잰다. 토큰·비용은 응답 객체에서 읽는다.
(LiteLLM 콜백은 타이밍이 일정하지 않아서 쓰지 않는다.)
"""
import json
import os
import time
from datetime import datetime, timezone

import litellm

from . import chaos as chaos_module
from .config import provider_of

DEFAULT_LOG = os.path.join("runs", "calls.jsonl")


def ask(gw, alias, messages, scene, log_path=DEFAULT_LOG):
    """alias 를 부르고 CallRecord(dict) 를 calls.jsonl 에 한 줄 덧붙여 돌려준다.

    돌려주는 dict 의 `_attempts` 는 chaos 가 본 시도 목록(파일에는 저장하지 않음),
    `_content` 는 응답 문장.
    """
    chaos = chaos_module.chaos
    n0 = len(chaos.attempts)
    if not gw.deployments(alias):
        known = sorted({d["model_name"] for d in gw.router.model_list})
        raise ValueError(f"alias {alias!r} is not in model_list of the gateway config. Available: {', '.join(known)}")
    first_model = gw.deployments(alias)[0]["litellm_params"]["model"]
    t0 = time.perf_counter()
    content, reasoning, error_type, resp = None, None, None, None
    try:
        resp = gw.router.completion(model=alias, messages=messages)
        status = "ok"
        content = resp.choices[0].message.content
        # qwen3 의 '생각' 텍스트 (없으면 None)
        reasoning = resp.choices[0].message.get("reasoning_content")
    except Exception as e:                       # 실패도 기록해야 하므로 모두 잡는다
        status, error_type = "error", type(e).__name__
    latency_ms = (time.perf_counter() - t0) * 1000

    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scene": scene, "alias": alias,
        "provider": provider_of(first_model), "model": first_model,
        "prompt_tokens": None, "completion_tokens": None, "cost_usd": None,
        "latency_ms": round(latency_ms, 1), "status": status, "error_type": error_type,
        "fallback_used": False, "mock": first_model in gw.mock_models,
        "prompt_tokens_counted": None,
    }
    if resp is not None:
        hidden = resp._hidden_params or {}
        answered = hidden.get("litellm_model_name") or resp.model
        # 응답한 배포의 원래 모델 문자열 찾기 (접두사 포함 형태)
        for dep in gw.router.model_list:
            m = dep["litellm_params"]["model"]
            if m == answered or m.endswith("/" + str(answered)) or str(answered).endswith("/" + m):
                answered = m
                break
        rec["model"], rec["provider"] = answered, provider_of(answered)
        rec["mock"] = answered in gw.mock_models
        rec["prompt_tokens"] = resp.usage.prompt_tokens
        rec["completion_tokens"] = resp.usage.completion_tokens
        if rec["provider"] != "chaos":           # chaos 응답은 가격표에 없다 -> None("계산 안 됨")
            rec["cost_usd"] = hidden.get("response_cost")
        headers = hidden.get("additional_headers") or {}
        rec["fallback_used"] = (headers.get("x-litellm-attempted-fallbacks") or 0) > 0
        try:                                     # 내가 직접 센 프롬프트 토큰 (mock 은 usage 가 고정값이라 따로 센다)
            rec["prompt_tokens_counted"] = litellm.token_counter(model=answered, messages=messages)
        except Exception:
            pass

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    out = dict(rec)
    out["_content"] = content
    out["_reasoning"] = reasoning
    out["_attempts"] = [dict(a, t=a["t"] - t0) for a in chaos.attempts[n0:]]
    return out


def read_calls(log_path=DEFAULT_LOG):
    if not os.path.exists(log_path):
        return []
    with open(log_path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
