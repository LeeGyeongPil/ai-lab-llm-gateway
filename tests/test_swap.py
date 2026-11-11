import unittest

import litellm

from tests.helpers import MSGS, calls, gateway_with, tmp_log


class SwapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gw = gateway_with()
        log = tmp_log()
        # 같은 ask() 호출, 별칭만 다르다
        cls.recs = {a: calls.ask(gw, a, MSGS, "swap", log)
                    for a in ["openai", "anthropic", "gemini", "local"]}

    def test_four_providers_one_interface(self):  # AC-2
        self.assertEqual([r["provider"] for r in self.recs.values()],
                         ["openai", "anthropic", "gemini", "ollama_chat"])
        for r in self.recs.values():
            self.assertEqual(r["status"], "ok")
            self.assertTrue(r["mock"])

    def test_cost_matches_price_table(self):  # AC-3
        def price(model):
            info = litellm.model_cost.get(model) or litellm.model_cost[model.split("/", 1)[-1]]
            return info["input_cost_per_token"], info["output_cost_per_token"]
        costs = {}
        for alias in ["openai", "anthropic", "gemini"]:
            r = self.recs[alias]
            inp, out = price(r["model"])
            expect = r["prompt_tokens"] * inp + r["completion_tokens"] * out
            self.assertAlmostEqual(r["cost_usd"], expect, places=12)
            costs[alias] = r["cost_usd"]
        self.assertGreater(costs["anthropic"], costs["gemini"])
        self.assertGreater(costs["gemini"], costs["openai"])
        # 로컬은 무료로, 미등록(chaos)은 "계산 안 됨" 으로 구분해 표시
        from gateway import i18n, report
        chaos_rec = dict(self.recs["openai"], provider="chaos", cost_usd=None)
        i18n.set_lang("ko")                      # 언어를 명시한다 (호스트 로캘에 의존하지 않기)
        self.assertEqual(report.cost_text(self.recs["local"]), "로컬(무료)")
        self.assertEqual(report.cost_text(chaos_rec), "계산 안 됨")
        i18n.set_lang("en")
        self.assertEqual(report.cost_text(self.recs["local"]), "local (free)")
        self.assertEqual(report.cost_text(chaos_rec), "not computed")


if __name__ == "__main__":
    unittest.main()
