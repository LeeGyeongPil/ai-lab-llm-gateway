"""English/Korean display language: selection order, message tables, and every error path."""
import os
import string
import subprocess
import sys

import pytest

import demo
from gateway import calls, chaos as chaos_module, config, i18n, report
from tests.helpers import MSGS, ROOT, tmp_log

GATEWAY_YAML = os.path.join(ROOT, "configs", "gateway.yaml")
LOCALE_VARS = ("AI_LAB_LLM_GATEWAY_LANG", "LC_ALL", "LC_MESSAGES", "LANG")


def clean_env(**extra):
    """Environment for a child process: no locale variables except the ones given."""
    env = {k: v for k, v in os.environ.items() if k not in LOCALE_VARS}
    env.update(extra)
    return env


def run_demo(args, **env):
    return subprocess.run([sys.executable, os.path.join(ROOT, "demo.py"), *args], cwd=ROOT,
                          env=clean_env(**env), capture_output=True, text=True, timeout=300)


def has_hangul(s):
    return any("가" <= c <= "힣" for c in s)


# ---- selection order -------------------------------------------------------

@pytest.mark.parametrize("cli,env,expected", [
    ("en", {"AI_LAB_LLM_GATEWAY_LANG": "ko", "LANG": "ko_KR.UTF-8"}, "en"),     # --lang wins
    ("ko", {"AI_LAB_LLM_GATEWAY_LANG": "en", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"AI_LAB_LLM_GATEWAY_LANG": "ko", "LC_ALL": "en_US.UTF-8"}, "ko"),   # tool env beats locale
    (None, {"AI_LAB_LLM_GATEWAY_LANG": "en", "LC_ALL": "ko_KR.UTF-8"}, "en"),
    (None, {"LC_ALL": "ko_KR.UTF-8", "LC_MESSAGES": "en_US", "LANG": "en_US"}, "ko"),
    (None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US"}, "ko"),
    (None, {"LANG": "ko_KR.UTF-8"}, "ko"),
    (None, {"LANG": "en_US.UTF-8"}, "en"),
    (None, {"LANG": "C.UTF-8"}, "en"),
    (None, {"LANG": "C"}, "en"),
    (None, {"LANG": "POSIX"}, "en"),
    (None, {"LANG": "fr_FR.UTF-8"}, "en"),
    (None, {"AI_LAB_LLM_GATEWAY_LANG": "bogus", "LANG": "ko_KR.UTF-8"}, "ko"),  # invalid value is ignored
    (None, {}, "en"),
])
def test_resolve_lang_priority(cli, env, expected):
    assert i18n.resolve_lang(cli, env) == expected


def test_lang_from_argv_reads_both_forms():
    assert i18n.lang_from_argv(["--lang", "en", "swap"]) == "en"
    assert i18n.lang_from_argv(["swap", "--lang=ko"]) == "ko"
    assert i18n.lang_from_argv(["swap"]) is None


def test_set_lang_switches_output():
    i18n.set_lang("en")
    assert i18n.t("cost.local_free") == "local (free)"
    i18n.set_lang("ko")
    assert i18n.t("cost.local_free") == "로컬(무료)"


# ---- message tables --------------------------------------------------------

def placeholders(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_message_keys_match():
    assert set(i18n.MESSAGES["en"]) == set(i18n.MESSAGES["ko"])


def test_message_placeholders_match():
    for key, en in i18n.MESSAGES["en"].items():
        assert placeholders(en) == placeholders(i18n.MESSAGES["ko"][key]), key


def test_english_messages_have_no_hangul():
    for key, text in i18n.MESSAGES["en"].items():
        assert not has_hangul(text), key


# ---- tables and cost cells -------------------------------------------------

def sample_recs():
    gw = config.build_gateway(GATEWAY_YAML, "mock")
    return [calls.ask(gw, a, MSGS, "swap", tmp_log()) for a in ("openai", "local")]


def test_cost_text_per_language():
    rec = sample_recs()[1]
    chaos_rec = dict(rec, provider="chaos", cost_usd=None)
    i18n.set_lang("en")
    assert (report.cost_text(rec), report.cost_text(chaos_rec)) == ("local (free)", "not computed")
    i18n.set_lang("ko")
    assert (report.cost_text(rec), report.cost_text(chaos_rec)) == ("로컬(무료)", "계산 안 됨")


def test_tables_same_shape_in_both_languages():
    recs = sample_recs()
    out = {}
    for lang in ("en", "ko"):
        i18n.set_lang(lang)
        out[lang] = (report.swap_table(recs), report.summary_table(recs))
    for i in range(2):
        en, ko = out["en"][i].splitlines(), out["ko"][i].splitlines()
        assert len(en) == len(ko)
        assert [l.count("|") for l in en] == [l.count("|") for l in ko]
    assert not has_hangul(out["en"][0]) and not has_hangul(out["en"][1])
    assert "별칭" in out["ko"][0] and "alias" in out["en"][0]


def test_timeline_and_markdown_per_language(tmp_path):
    gw = config.build_gateway(GATEWAY_YAML, "mock", scenario="rate_limit")
    rec = calls.ask(gw, "primary", MSGS, "fallback", tmp_log())
    i18n.set_lang("en")
    assert "attempt 1" in report.timeline(rec) and not has_hangul(report.timeline(rec))
    path = str(tmp_path / "r.md")
    report.write_markdown([rec], path)
    text = open(path, encoding="utf-8").read()
    assert text.startswith("# Call summary") and not has_hangul(text)
    i18n.set_lang("ko")
    report.write_markdown([rec], path)
    assert open(path, encoding="utf-8").read().startswith("# 호출 요약")


# ---- error codes -----------------------------------------------------------

def test_gateway_error_carries_code_and_params():
    gw = config.build_gateway(GATEWAY_YAML, "mock")
    with pytest.raises(ValueError) as cm:                  # still a ValueError for existing callers
        calls.ask(gw, "nope", MSGS, "ask", tmp_log())
    err = cm.value
    assert isinstance(err, i18n.GatewayError)
    assert err.code == "unknown_alias" and err.params["alias"] == "nope"
    assert "Available" in str(err) and not has_hangul(str(err))


def test_unknown_chaos_behavior_error():
    with pytest.raises(i18n.GatewayError) as cm:
        chaos_module.chaos.completion("bogus", messages=MSGS, model_response=None)
    assert cm.value.code == "unknown_chaos_behavior" and cm.value.params == {"behavior": "bogus"}


@pytest.mark.parametrize("code,params", [
    ("unknown_alias", {"alias": "x", "available": "a, b"}),
    ("unknown_chaos_behavior", {"behavior": "x"}),
    ("io_error", {"path": "runs/x.jsonl", "reason": "Permission denied"}),
])
def test_every_error_code_renders_in_both_languages(code, params):
    en = i18n.render_error(code, params, "en")
    ko = i18n.render_error(code, params, "ko")
    assert en != ko and not has_hangul(en) and has_hangul(ko)
    assert all(str(v) in en and str(v) in ko for v in params.values())


def test_notice_renders_in_both_languages():
    en = i18n.render_notice("ollama_unreachable", {"base": "http://x"}, "en")
    ko = i18n.render_notice("ollama_unreachable", {"base": "http://x"}, "ko")
    assert "Ollama" in en and not has_hangul(en) and "http://x" in en
    assert "연결할 수 없어" in ko


# ---- CLI end to end (subprocess, locale given explicitly) ------------------

def test_cli_unknown_alias_english():
    r = run_demo(["--lang", "en", "ask", "hi", "--model", "nope"], LANG="ko_KR.UTF-8")
    assert r.returncode == 2
    assert "not in" in r.stderr and not has_hangul(r.stderr) and "Traceback" not in r.stderr


def test_cli_unknown_alias_korean():
    r = run_demo(["--lang", "ko", "ask", "hi", "--model", "nope"], LANG="en_US.UTF-8")
    assert r.returncode == 2
    assert "없습니다" in r.stderr and "Traceback" not in r.stderr


def bad_log(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("x")                  # a file where a directory is needed -> OSError for any user
    return str(blocker / "calls.jsonl")


@pytest.mark.parametrize("lang,word", [("en", "Cannot"), ("ko", "없습니다")])
def test_cli_unwritable_log(tmp_path, lang, word):
    r = run_demo(["--lang", lang, "--log", bad_log(tmp_path), "ask", "hi", "--model", "smart"])
    assert r.returncode == 1
    assert word in r.stderr and "Traceback" not in r.stderr
    assert has_hangul(r.stderr) == (lang == "ko")


# ---- in-process CLI paths --------------------------------------------------

def test_main_permission_error_is_rendered(monkeypatch, capsys):
    def boom(*a, **k):
        raise PermissionError(13, "Permission denied", "runs/calls.jsonl")
    monkeypatch.setattr(calls, "ask", boom)
    for lang in ("en", "ko"):
        code = demo.main(["--lang", lang, "swap"])
        err = capsys.readouterr().err
        assert code == 1 and "runs/calls.jsonl" in err and "Traceback" not in err
        assert has_hangul(err) == (lang == "ko")


def test_main_report_write_failure_is_rendered(monkeypatch, capsys, tmp_path):
    log = tmp_log()
    calls.ask(config.build_gateway(GATEWAY_YAML, "mock"), "openai", MSGS, "swap", log)
    monkeypatch.setattr(demo, "REPORT", bad_log(tmp_path))
    assert demo.main(["--lang", "en", "--log", log, "summary"]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_main_help_is_translated(capsys):
    texts = {}
    for lang in ("en", "ko"):
        with pytest.raises(SystemExit) as cm:
            demo.main(["--lang", lang, "--help"])
        assert cm.value.code == 0
        texts[lang] = capsys.readouterr().out
    assert "AI_LAB_LLM_GATEWAY_LANG" in texts["en"] and "LC_ALL" in texts["en"]
    assert not has_hangul(texts["en"]) and has_hangul(texts["ko"])


def test_main_language_switch_changes_output(capsys):
    outs = {}
    for lang in ("en", "ko"):
        assert demo.main(["--lang", lang, "swap"]) == 0
        outs[lang] = capsys.readouterr().out
    assert not has_hangul(outs["en"]) and has_hangul(outs["ko"])
    assert len(outs["en"].splitlines()) == len(outs["ko"].splitlines())


def test_lang_flag_accepted_after_subcommand(capsys):
    assert demo.main(["swap", "--lang", "en"]) == 0
    assert not has_hangul(capsys.readouterr().out)
