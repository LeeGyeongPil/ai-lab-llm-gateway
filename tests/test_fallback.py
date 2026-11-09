import time
import unittest

from gateway import chaos as chaos_module
from tests.helpers import MSGS, calls, gateway_with, tmp_log


class FallbackTest(unittest.TestCase):
    def test_rate_limit_retries_then_fallback(self):  # AC-4
        gw = gateway_with(scenario="rate_limit", num_retries=2)
        log = tmp_log()
        rec = calls.ask(gw, "primary", MSGS, "fallback", log)
        attempts = chaos_module.chaos.attempts
        self.assertEqual(len(attempts), 3)                         # primary 를 3번 불렀다
        self.assertTrue(all(a["error_type"] == "RateLimitError" for a in attempts))
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(rec["model"], "gpt-4o-mini")               # backup 이 답했다
        self.assertTrue(rec["fallback_used"])
        self.assertTrue(calls.read_calls(log)[0]["fallback_used"])

    def test_timeout_falls_back(self):  # AC-5
        gw = gateway_with(scenario="timeout", num_retries=0)
        t0 = time.perf_counter()
        rec = calls.ask(gw, "primary", MSGS, "fallback", tmp_log())
        self.assertLess(time.perf_counter() - t0, 3)
        attempts = chaos_module.chaos.attempts
        self.assertEqual([a["error_type"] for a in attempts], ["Timeout"])
        self.assertEqual(rec["model"], "gpt-4o-mini")
        self.assertTrue(rec["fallback_used"])

    def test_no_fallback_surfaces_error_type(self):
        gw = gateway_with(scenario="server_error", num_retries=0)
        gw.router.fallbacks = []
        rec = calls.ask(gw, "primary", MSGS, "fallback", tmp_log())
        self.assertEqual(rec["status"], "error")
        self.assertEqual(rec["error_type"], "InternalServerError")


if __name__ == "__main__":
    unittest.main()
