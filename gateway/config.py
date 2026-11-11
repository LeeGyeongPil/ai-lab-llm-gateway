"""gateway.yaml 을 읽어 litellm.Router 를 만든다.

mode 에 따라 달라지는 것:
  mock : 모든 실제 공급자 배포에 mock_response 를 넣는다 (키·네트워크 불필요).
         chaos 배포는 그대로 둔다 -> 오류 주입과 Router 의 재시도·폴백은 진짜로 돈다.
  real : 키가 있는 클라우드 공급자와 켜져 있는 Ollama 는 진짜로 부른다.
         키가 없거나 Ollama 가 꺼져 있으면 그 배포만 mock 으로 남긴다.
"""
import copy
import os
import urllib.request

import yaml
from litellm import Router

from . import chaos as chaos_module

MOCK_TEXT = "(연습용 목 응답) 게이트웨이는 여러 LLM 공급자를 한 가지 방식으로 부르게 해 주는 중간 계층입니다."
KEY_FOR_PREFIX = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
OLLAMA_DEFAULT = "http://localhost:11434"
REAL_OLLAMA_TIMEOUT = 180  # 공유 자원이라 느릴 수 있다 -> 넉넉하게. 느린 것을 오류로 보지 않는다.


def provider_of(model):
    """모델 문자열에서 공급자를 읽는다. 접두사가 없으면 OpenAI."""
    return model.split("/", 1)[0] if "/" in model else "openai"


def ollama_base():
    return os.environ.get("OLLAMA_API_BASE") or OLLAMA_DEFAULT


def ollama_alive(base=None):
    """Ollama 서버가 응답하는지 2초 안에 확인한다."""
    try:
        with urllib.request.urlopen((base or ollama_base()) + "/api/tags", timeout=2):
            return True
    except Exception:
        return False


class Gateway:
    """Router 와 부가 정보(어떤 모델이 mock 인지, 안내 (code, params) 목록)를 묶은 것."""

    def __init__(self, router, mock_models, notices, mode):
        self.router = router
        self.mock_models = mock_models  # mock 으로 도는 배포의 모델 문자열 집합
        self.notices = notices
        self.mode = mode

    def deployments(self, alias):
        return [d for d in self.router.model_list if d["model_name"] == alias]


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_gateway(path, mode="mock", scenario=None):
    cfg = copy.deepcopy(load_yaml(path))
    notices = []
    mock_models = set()

    # real 모드에서 Ollama 가 꺼져 있으면 안내하고 mock 으로 진행
    ollama_up = False
    if mode == "real":
        ollama_up = ollama_alive()
        if not ollama_up:
            notices.append(("ollama_unreachable", {"base": ollama_base()}))  # (code, params): the CLI renders it

    # 시나리오가 있으면 primary 배포의 모델·timeout 을 덮어쓴다
    if scenario:
        use_real = mode == "real" and ollama_up
        override = cfg["scenarios"][scenario]["real" if use_real else "mock"]
        for dep in cfg["model_list"]:
            if dep["model_name"] == "primary":
                dep["litellm_params"].update(override)

    for dep in cfg["model_list"]:
        params = dep["litellm_params"]
        model = params["model"]
        if str(params.get("api_base", "")).startswith("os.environ/"):
            params["api_base"] = ollama_base()   # yaml 의 환경변수 표기를 직접 풀어 준다
        provider = provider_of(model)
        if provider == "chaos":
            continue                              # 오류 주입 공급자는 항상 진짜로 돈다
        is_ollama = provider == "ollama_chat"
        if mode == "mock":
            real_ok = False
        elif is_ollama:
            real_ok = ollama_up
        else:
            real_ok = bool(os.environ.get(KEY_FOR_PREFIX.get(provider, "")))
        if real_ok:
            if is_ollama:
                params.setdefault("timeout", REAL_OLLAMA_TIMEOUT)
        else:
            params["mock_response"] = MOCK_TEXT
            mock_models.add(model)

    chaos_module.register()
    chaos_module.chaos.reset()
    rs = cfg.get("router_settings", {})
    router = Router(
        model_list=cfg["model_list"],
        fallbacks=cfg.get("fallbacks", []),
        num_retries=rs.get("num_retries", 0),
        timeout=rs.get("timeout"),
        routing_strategy=rs.get("routing_strategy", "simple-shuffle"),
    )
    return Gateway(router, mock_models, notices, mode)
