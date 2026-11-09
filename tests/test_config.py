import os
import unittest

from tests.helpers import MSGS, ROOT, calls, config, gateway_with, tmp_log


class ConfigTest(unittest.TestCase):
    def run_ten(self, fname):
        gw = config.build_gateway(os.path.join(ROOT, "configs", fname), "mock")
        log = tmp_log()
        return [calls.ask(gw, "primary", MSGS, "compare", log) for _ in range(10)]

    def test_yaml_swap_changes_route(self):  # AC-6
        a = self.run_ten("no-fallback.yaml")
        b = self.run_ten("with-fallback.yaml")
        self.assertGreater(sum(r["status"] == "error" for r in a), 0)
        self.assertEqual(sum(r["fallback_used"] for r in a), 0)
        self.assertEqual(sum(r["status"] == "ok" for r in b), 10)
        self.assertGreater(sum(r["fallback_used"] for r in b), 0)

    def test_offline_price_map_env(self):
        import gateway  # noqa: F401
        self.assertEqual(os.environ["LITELLM_LOCAL_MODEL_COST_MAP"], "True")

    def test_real_mode_without_ollama_falls_back_to_mock(self):  # AC-9 (꺼진 경우)
        old = os.environ.get("OLLAMA_API_BASE")
        os.environ["OLLAMA_API_BASE"] = "http://127.0.0.1:9"
        try:
            gw = config.build_gateway(os.path.join(ROOT, "configs", "gateway.yaml"), "real")
        finally:
            if old is None:
                del os.environ["OLLAMA_API_BASE"]
            else:
                os.environ["OLLAMA_API_BASE"] = old
        self.assertTrue(any("Ollama에 연결할 수 없어 mock으로 진행" in n for n in gw.notices))
        rec = calls.ask(gw, "local", MSGS, "swap", tmp_log())
        self.assertEqual(rec["status"], "ok")
        self.assertTrue(rec["mock"])


    def test_unknown_alias_gives_friendly_error(self):  # AC-2 (오류 경로)
        gw = config.build_gateway(os.path.join(ROOT, "configs", "gateway.yaml"), "mock")
        with self.assertRaises(ValueError) as cm:
            calls.ask(gw, "nope", MSGS, "ask", tmp_log())
        self.assertIn("Available", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
