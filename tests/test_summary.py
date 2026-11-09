import json
import unittest

from gateway import report
from tests.helpers import MSGS, calls, gateway_with, tmp_log

FIELDS = ["ts", "scene", "alias", "provider", "model", "prompt_tokens", "completion_tokens",
          "cost_usd", "latency_ms", "status", "error_type", "fallback_used", "mock"]


class SummaryTest(unittest.TestCase):
    def test_calls_jsonl_fields_and_p50(self):  # AC-7
        gw = gateway_with()
        log = tmp_log()
        for alias in ["openai", "openai", "openai", "local"]:
            calls.ask(gw, alias, MSGS, "swap", log)
        with open(log, encoding="utf-8") as f:
            lines = [json.loads(x) for x in f]
        self.assertEqual(len(lines), 4)
        for rec in lines:
            for field in FIELDS:
                self.assertIn(field, rec)
        s = {x["alias"]: x for x in report.summarize(lines)}
        self.assertEqual(s["openai"]["calls"], 3)
        self.assertEqual(s["openai"]["success_rate"], 1.0)
        self.assertAlmostEqual(s["openai"]["total_cost_usd"], sum(r["cost_usd"] for r in lines[:3]), places=12)
        lat = sorted(r["latency_ms"] for r in lines[:3])
        self.assertEqual(s["openai"]["p50_latency_ms"], lat[1])   # 손 계산: 3개의 가운데 값

    def test_summary_counts_failures_and_even_median(self):
        recs = [dict(alias="x", status=st, fallback_used=False, cost_usd=c, latency_ms=l, mock=True)
                for st, c, l in [("ok", 1.0, 10), ("error", None, 30)]]
        s = report.summarize(recs)[0]
        self.assertEqual(s["success_rate"], 0.5)
        self.assertEqual(s["p50_latency_ms"], 20)
        self.assertEqual(s["total_cost_usd"], 1.0)


if __name__ == "__main__":
    unittest.main()
