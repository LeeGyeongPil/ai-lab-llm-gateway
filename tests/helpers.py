"""테스트 공용 도구: 설정을 임시 yaml 로 바꿔 Router 를 만든다 (전부 mock 모드)."""
import copy
import os
import tempfile

import yaml

import gateway  # noqa: F401  (litellm import 전에 환경변수 설정)
from gateway import calls, config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATEWAY_YAML = os.path.join(ROOT, "configs", "gateway.yaml")


def gateway_with(path=GATEWAY_YAML, scenario=None, **router_overrides):
    """yaml 을 읽어 router_settings 를 덮어쓴 임시 파일로 mock 게이트웨이를 만든다."""
    cfg = copy.deepcopy(config.load_yaml(path))
    cfg["router_settings"].update(router_overrides)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    try:
        return config.build_gateway(f.name, "mock", scenario)
    finally:
        os.unlink(f.name)


def tmp_log():
    d = tempfile.mkdtemp()
    return os.path.join(d, "calls.jsonl")


MSGS = [{"role": "user", "content": "안녕"}]
