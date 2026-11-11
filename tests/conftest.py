"""Pin the display language for every test so results do not depend on the host locale."""
import pytest

LANG_VARS = ("AI_LAB_LLM_GATEWAY_LANG", "LC_ALL", "LC_MESSAGES", "LANG")


@pytest.fixture(autouse=True)
def _pin_language(monkeypatch):
    """Korean by default (existing assertions are Korean); tests that need another language set it explicitly."""
    for var in LANG_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AI_LAB_LLM_GATEWAY_LANG", "ko")
    from gateway import i18n
    i18n.set_lang(None)
    yield
    i18n.set_lang(None)
