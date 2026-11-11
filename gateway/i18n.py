"""Display language (English / Korean): one message table, language selection, coded errors.

Language priority: --lang en|ko > AI_LAB_LLM_GATEWAY_LANG > LC_ALL > LC_MESSAGES > LANG.
A value starting with "ko" selects Korean; anything else (unset, C, POSIX, other languages) is English.
Only human-readable text is translated; calls.jsonl, table shapes and exit codes never change.
"""
import os

LANGS = ("en", "ko")
ENV_VAR = "AI_LAB_LLM_GATEWAY_LANG"
LOCALE_VARS = ("LC_ALL", "LC_MESSAGES", "LANG")

MESSAGES = {
    "en": {
        "help.description": (
            "LLM gateway demo - read it from top to bottom.\n\n"
            "  uv run demo.py                         # tour: the 4 scenes in order (mock mode by default)\n"
            "  uv run demo.py swap | fallback | compare | summary\n"
            "  uv run demo.py ask \"question\" --model smart\n"
            "  uv run demo.py swap --mode real        # real calls with local Ollama / your own keys\n"
            "  uv run demo.py swap --lang ko          # Korean output"
        ),
        "help.mode": "mock (default, no keys needed) or real; the DEMO_MODE environment variable sets the default",
        "help.log": "call log file",
        "help.lang": ("output language, en or ko. Priority: --lang > AI_LAB_LLM_GATEWAY_LANG > "
                      "LC_ALL > LC_MESSAGES > LANG; anything other than Korean falls back to English"),
        "help.scenario": "failure to inject (default: all three in turn)",
        "help.model": "model alias from configs/gateway.yaml",
        "help.question": "question to send",
        "loading": "Loading LiteLLM... (the first run takes about 10 seconds)",
        "banner.mock.1": "* Practice (mock) mode - the answer text, token counts (fixed 10/20) and latency are fake.",
        "banner.mock.2": "  Real: Router retries, fallbacks and backoff, price-table cost math, the effect of swapping config.",
        "banner.real.1": "real mode - providers with a key, and a running Ollama, are called for real. It may be slow.",
        "banner.real.2": "  Providers without a key and a stopped Ollama continue as mock, marked with a MOCK badge.",
        "label.notice": "Notice:",
        "label.local_reply": "local reply:",
        "label.thinking": "thinking (start):",
        "label.answer": "Answer:",
        "local.empty": "(empty reply: the thinking step used all the tokens)",
        "scene.swap.title": "\n[1/4] swap - same code, only the alias (model string) differs",
        "swap.mock_note": ("  * mock tokens are fixed values, so read the cost column only as "
                           "'unit-price comparison at the same token count'."),
        "scene.fallback.title": "\n[2/4] fallback - retry inside the same group, then fall back to another group (backup)",
        "fallback.scenario_line": "\n  scenario {name}: primary={model} (retries {retries}, timeout {timeout}s)",
        "fallback.no_attempts": ("  (in real mode primary has no per-attempt record, so only the final result is shown. "
                                 "Per-attempt detail is accurate in mock mode)"),
        "scene.compare.title": ("\n[3/4] compare - same 10 requests, only the config file differs "
                                "(primary repeats fail, fail, success)"),
        "compare.footnote": ("  * Values differ in two places: num_retries, fallbacks (the rest is comments, "
                             "diff configs/no-fallback.yaml configs/with-fallback.yaml)"),
        "scene.summary.title": "\n[4/4] summary - aggregate of the call records in {log}",
        "summary.empty": "  No records. Run `uv run demo.py` first.",
        "summary.saved": "  Saved the Markdown table to {path}.",
        "done": "\nDone. {secs:.1f}s in total",
        "col.config": "config",
        "col.success": "success",
        "col.fallbacks_count": "fallbacks",
        "col.avg_latency": "avg latency (ms)",
        "col.p50_latency": "p50 latency (ms)",
        "col.total_cost": "total est. cost (USD)",
        "col.alias": "alias",
        "col.provider": "provider",
        "col.model": "actual model",
        "col.tokens": "input/output tokens",
        "col.counted": "prompt tokens counted",
        "col.cost": "est. cost (price table, USD)",
        "col.latency": "latency (ms)",
        "col.mock": "MOCK",
        "col.status": "status",
        "col.calls": "calls",
        "col.success_rate": "success rate",
        "col.fallbacks": "fallbacks",
        "col.mock_calls": "MOCK calls",
        "cell.real": "real",
        "cost.not_computed": "not computed",
        "cost.local_free": "local (free)",
        "price_note": ("Estimated cost is based on the price table built into litellm 1.108.3 "
                       "and may differ from the real bill."),
        "tl.attempt": "  +{t:5.2f}s  attempt {i}  chaos/{behavior} -> {result}",
        "tl.success": "success",
        "tl.answered": "answered",
        "tl.answered_fallback": "answered after falling back",
        "tl.final_failure": "final failure",
        "report.title": "Call summary",
        "notice.ollama_unreachable": "Cannot connect to Ollama, continuing with mock ({base})",
        "error.unknown_alias": ("alias '{alias}' is not in model_list of the gateway config. "
                                "Available: {available}"),
        "error.unknown_chaos_behavior": "Unknown chaos behavior: {behavior}",
        "error.io_error": "Cannot read or write the file: {path} ({reason}). Check that the path exists and is writable.",
    },
    "ko": {
        "help.description": (
            "LLM 게이트웨이 데모 — 위에서 아래로 읽으면 된다.\n\n"
            "  uv run demo.py                         # tour: 4장면을 순서대로 (기본 mock 모드)\n"
            "  uv run demo.py swap | fallback | compare | summary\n"
            "  uv run demo.py ask \"질문\" --model smart\n"
            "  uv run demo.py swap --mode real        # 로컬 Ollama·내 키로 진짜 호출\n"
            "  uv run demo.py swap --lang en          # 영어 출력"
        ),
        "help.mode": "mock(기본, 키 불필요) 또는 real. 환경변수 DEMO_MODE 로 기본값을 정한다",
        "help.log": "호출 기록 파일",
        "help.lang": ("출력 언어 en 또는 ko. 우선순위: --lang > AI_LAB_LLM_GATEWAY_LANG > "
                      "LC_ALL > LC_MESSAGES > LANG, 한국어가 아니면 영어"),
        "help.scenario": "주입할 실패 (기본: 세 가지를 차례로)",
        "help.model": "configs/gateway.yaml 의 모델 별칭",
        "help.question": "보낼 질문",
        "loading": "LiteLLM 불러오는 중… (처음엔 10초쯤 걸립니다)",
        "banner.mock.1": "※ 연습용 목(mock) 모드 — 응답 문장·토큰 수(10/20 고정)·지연은 가짜입니다.",
        "banner.mock.2": "  진짜인 것: Router 의 재시도·폴백·백오프, 가격표 비용 계산, 설정 교체 효과.",
        "banner.real.1": "real 모드 — Ollama·키가 있는 공급자는 진짜로 부릅니다. 느릴 수 있습니다.",
        "banner.real.2": "  키가 없는 공급자와 꺼진 Ollama 는 MOCK 배지를 단 채 mock 으로 진행합니다.",
        "label.notice": "안내:",
        "label.local_reply": "local 응답:",
        "label.thinking": "생각 앞부분:",
        "label.answer": "응답:",
        "local.empty": "(빈 응답: 생각 단계가 토큰을 다 씀)",
        "scene.swap.title": "\n[1/4] swap — 같은 코드, 별칭(모델 문자열)만 다르다",
        "swap.mock_note": "  * mock 의 토큰은 고정값이라 비용 열은 '같은 토큰량일 때의 단가 비교'로만 읽으세요.",
        "scene.fallback.title": "\n[2/4] fallback — 같은 그룹에서 재시도, 그다음 다른 그룹(backup)으로 폴백",
        "fallback.scenario_line": "\n  시나리오 {name}: primary={model} (재시도 {retries}회, timeout {timeout}s)",
        "fallback.no_attempts": "  (real 모드 primary 는 시도 단위 기록이 없어 최종 결과만 보입니다. 시도 단위는 mock 모드가 정확)",
        "scene.compare.title": "\n[3/4] compare — 같은 요청 10개, 설정 파일만 다르다 (primary 는 실패·실패·성공 반복)",
        "compare.footnote": ("  * 값이 다른 곳: num_retries, fallbacks 두 곳 "
                             "(나머지는 주석 차이, diff configs/no-fallback.yaml configs/with-fallback.yaml)"),
        "scene.summary.title": "\n[4/4] summary — {log} 에 쌓인 호출 기록 집계",
        "summary.empty": "  기록이 없습니다. 먼저 `uv run demo.py` 를 실행하세요.",
        "summary.saved": "  마크다운 표를 {path} 에 저장했습니다.",
        "done": "\n끝. 총 {secs:.1f}초",
        "col.config": "설정",
        "col.success": "성공",
        "col.fallbacks_count": "폴백 횟수",
        "col.avg_latency": "평균 지연(ms)",
        "col.p50_latency": "p50 지연(ms)",
        "col.total_cost": "총 추정 비용(USD)",
        "col.alias": "별칭",
        "col.provider": "공급자",
        "col.model": "실제 모델",
        "col.tokens": "입력/출력 토큰",
        "col.counted": "직접 센 프롬프트",
        "col.cost": "추정 비용(가격표,USD)",
        "col.latency": "지연(ms)",
        "col.mock": "MOCK",
        "col.status": "상태",
        "col.calls": "호출 수",
        "col.success_rate": "성공률",
        "col.fallbacks": "폴백",
        "col.mock_calls": "MOCK 호출",
        "cell.real": "실제",
        "cost.not_computed": "계산 안 됨",
        "cost.local_free": "로컬(무료)",
        "price_note": "추정 비용은 litellm 1.108.3 내장 가격표 기준이며 실제 청구와 다를 수 있습니다.",
        "tl.attempt": "  +{t:5.2f}s  시도 {i}  chaos/{behavior} -> {result}",
        "tl.success": "성공",
        "tl.answered": "응답",
        "tl.answered_fallback": "폴백으로 넘어가 응답",
        "tl.final_failure": "최종 실패",
        "report.title": "호출 요약",
        "notice.ollama_unreachable": "Ollama에 연결할 수 없어 mock으로 진행합니다 ({base})",
        "error.unknown_alias": ("별칭 {alias} 이 configs/gateway.yaml model_list 에 없습니다. "
                                "사용 가능: {available}"),
        "error.unknown_chaos_behavior": "알 수 없는 chaos 행동: {behavior}",
        "error.io_error": "파일을 읽거나 쓸 수 없습니다: {path} ({reason}). 경로가 있고 쓸 수 있는지 확인하세요.",
    },
}

_override = None  # set by the CLI after it reads --lang; None means "decide from the environment"


def _from_value(value):
    """'ko_KR.UTF-8' -> 'ko', anything else -> 'en'. Returns None for an empty value."""
    if not value:
        return None
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_lang(cli=None, env=None):
    """Apply the priority --lang > AI_LAB_LLM_GATEWAY_LANG > LC_ALL > LC_MESSAGES > LANG."""
    env = os.environ if env is None else env
    if cli in LANGS:
        return cli
    own = (env.get(ENV_VAR) or "").strip().lower()
    if own in LANGS:                       # an invalid value is ignored and the locale decides
        return own
    for var in LOCALE_VARS:
        found = _from_value(env.get(var))
        if found:
            return found
    return "en"


def lang_from_argv(argv):
    """Read --lang before argparse runs, so --help can already be translated."""
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1] if argv[i + 1] in LANGS else None
        if a.startswith("--lang="):
            v = a.split("=", 1)[1]
            return v if v in LANGS else None
    return None


def set_lang(lang):
    """Pin the language for this process (None goes back to the environment)."""
    global _override
    _override = lang if lang in LANGS else None


def get_lang():
    return _override or resolve_lang()


def t(key, lang=None, **params):
    text = MESSAGES[lang or get_lang()][key]
    return text.format(**params) if params else text


class GatewayError(ValueError):
    """Library error with a stable `code` and `params`; the CLI renders it in the chosen language.

    str(error) is always English, so library users see readable text.
    """

    def __init__(self, code, **params):
        self.code = code
        self.params = params
        super().__init__(render_error(code, params, "en"))


def render_error(code, params, lang=None):
    return t("error." + code, lang, **params)


def render_notice(code, params, lang=None):
    return t("notice." + code, lang, **params)
