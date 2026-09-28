from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from matcher import AddressMatcher


class DecisionCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = AddressMatcher(APP / "model_config.json", "/tmp/does-not-exist-ban.sqlite")
        cls.cases = json.loads((ROOT / "tests" / "corpus_decisions.json").read_text(encoding="utf-8"))

    def test_corpus(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                result = self.matcher.score(case["address_a"], case["address_b"], use_ban=False)
                self.assertEqual(result["decision"], case["expected_decision"])
                self.assertEqual(result["decision_reason"], case["expected_reason"])
                if "max_score" in case:
                    self.assertLessEqual(result["score_final"], float(case["max_score"]))
                if "min_score" in case:
                    self.assertGreaterEqual(result["score_final"], float(case["min_score"]))


if __name__ == "__main__":
    unittest.main()
