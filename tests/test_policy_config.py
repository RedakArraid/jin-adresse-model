from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from matcher import AddressMatcher


class PolicyConfigTests(unittest.TestCase):
    def test_review_cap_is_loaded_from_config(self):
        cfg = json.loads((APP / "model_config.json").read_text(encoding="utf-8"))
        cfg["decision_policy"]["score_caps"]["NOM_VOIE_PROCHE_NON_IDENTIQUE"] = 83.0

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "model_config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            matcher = AddressMatcher(path, Path(td) / "no-ban.sqlite")
            result = matcher.score(
                "12 avenue jean jaures 75019 paris",
                "12 avenue jean jauresx 75019 paris",
                use_ban=False,
            )

        self.assertEqual(result["decision"], "A_CONTROLER")
        self.assertLessEqual(result["score_final"], 83.0)

    def test_city_review_cap_is_loaded_from_config(self):
        cfg = json.loads((APP / "model_config.json").read_text(encoding="utf-8"))
        cfg["decision_policy"]["score_caps"]["COMMUNE_PROCHE_NON_IDENTIQUE"] = 84.0

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "model_config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            matcher = AddressMatcher(path, Path(td) / "no-ban.sqlite")
            result = matcher.score(
                "370 rte de st canadet 13100 aix en providence",
                "370 route de saint canadet 13100 aix en provence",
                use_ban=False,
            )

        self.assertEqual(result["decision"], "A_CONTROLER")
        self.assertLessEqual(result["score_final"], 84.0)

    def test_exact_match_floor_is_loaded_from_config(self):
        cfg = json.loads((APP / "model_config.json").read_text(encoding="utf-8"))
        cfg["decision_policy"]["score_floors"]["STRUCTURE_IDENTIQUE"] = 97.0

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "model_config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            matcher = AddressMatcher(path, Path(td) / "no-ban.sqlite")
            result = matcher.score(
                "187 bld de pontoise 75015 paris",
                "187 boulevard de pontoise 75015 paris",
                use_ban=False,
            )

        self.assertEqual(result["decision"], "MEME_ADRESSE")
        self.assertGreaterEqual(result["score_final"], 97.0)


if __name__ == "__main__":
    unittest.main()
