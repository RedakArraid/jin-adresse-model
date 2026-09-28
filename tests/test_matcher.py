from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from matcher import AddressMatcher


class MatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = AddressMatcher(APP / "model_config.json", "/tmp/does-not-exist-ban.sqlite")

    def score(self, a, b):
        return self.matcher.score(a, b, use_ban=False)

    def test_saint_canadet(self):
        r = self.score(
            "370 RTE DE ST CANADET 13100 AIX EN PROVENCE",
            "370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
        )
        self.assertEqual(r["decision"], "MEME_ADRESSE")
        self.assertGreaterEqual(r["score_final"], 95)

    def test_bv_is_boulevard(self):
        r = self.score(
            "187 bv de pontoise 95370 montigny les cormeilles",
            "187 boulevard de pontoise 95370 montigny-lès-cormeilles",
        )
        self.assertEqual(r["decision"], "MEME_ADRESSE")
        self.assertGreaterEqual(r["score_final"], 99.0)
        self.assertEqual(r["decision_reason"], "STRUCTURE_IDENTIQUE")
        self.assertEqual(r["parsed_A"]["type_voie"], "boulevard")
        self.assertEqual(r["parsed_A"]["nom_voie"], "de pontoise")

    def test_bvd_is_boulevard(self):
        r = self.score(
            "187 bvd de pontoise 95370 montigny les cormeilles",
            "187 boulevard de pontoise 95370 montigny les cormeilles",
        )
        self.assertEqual(r["decision"], "MEME_ADRESSE")
        self.assertGreaterEqual(r["score_final"], 99.0)

    def test_exact_structural_rule_does_not_override_suffix_conflict(self):
        r = self.score(
            "187 bis bv de pontoise 95370 montigny les cormeilles",
            "187 boulevard de pontoise 95370 montigny les cormeilles",
        )
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertEqual(r["decision_reason"], "CONFLIT_SUFFIXE_NUMERO")

    def test_city_name_inside_street_no_false_positive(self):
        r = self.score("10 rue de Paris 75001 Paris", "10 rue de Lyon 75001 Paris")
        self.assertEqual(r["parsed_A"]["nom_voie"], "de paris")
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertLessEqual(r["score_final"], 15)

    def test_large_house_number_conflict(self):
        r = self.score("1 rue A 75001 Paris", "999 rue A 75001 Paris")
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertEqual(r["decision_reason"], "CONFLIT_NUMERO")
        self.assertLessEqual(r["score_final"], 4)

    def test_adjacent_house_number_conflict(self):
        r = self.score("25 boulevard Voltaire 75011 Paris", "26 boulevard Voltaire 75011 Paris")
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertEqual(r["decision_reason"], "CONFLIT_NUMERO")

    def test_suffix_missing_conflict(self):
        r = self.score("14 rue Victor Hugo 92110 Clichy", "14 bis rue Victor Hugo 92110 Clichy")
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertEqual(r["decision_reason"], "CONFLIT_SUFFIXE_NUMERO")

    def test_suffix_value_conflict(self):
        r = self.score("14 bis rue Victor Hugo 92110 Clichy", "14 ter rue Victor Hugo 92110 Clichy")
        self.assertEqual(r["decision"], "DIFFERENTE")

    def test_postcode_conflict(self):
        r = self.score("25 boulevard Voltaire 75011 Paris", "25 boulevard Voltaire 69003 Lyon")
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertEqual(r["decision_reason"], "CONFLIT_CODE_POSTAL")

    def test_city_conflict_same_postcode(self):
        r = self.score("10 rue Victor Hugo 75001 Paris", "10 rue Victor Hugo 75001 Lyon")
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertEqual(r["decision_reason"], "CONFLIT_COMMUNE")

    def test_different_street_same_core(self):
        r = self.score("5 rue de Brest 29000 Quimper", "5 rue de Lorient 29000 Quimper")
        self.assertEqual(r["decision"], "DIFFERENTE")
        self.assertEqual(r["decision_reason"], "CONFLIT_NOM_VOIE")

    def test_near_homonym_is_not_automatic_match(self):
        r = self.score("12 avenue Victor Hugo 75015 Paris", "12 avenue Victor Huguet 75015 Paris")
        self.assertNotEqual(r["decision"], "MEME_ADRESSE")

    def test_unknown_city_same_address(self):
        r = self.score("12 R DE LA GARE 47200 MARMANDE", "12 rue de la Gare 47200 Marmande")
        self.assertEqual(r["parsed_A"]["ville_norm"], "marmande")
        self.assertEqual(r["decision"], "MEME_ADRESSE")

    def test_unknown_city_different_street(self):
        r = self.score("12 rue de la Gare 47200 Marmande", "12 rue Pasteur 47200 Marmande")
        self.assertEqual(r["decision"], "DIFFERENTE")

    def test_missing_postcode_does_not_force_city_conflict(self):
        r = self.score("12 rue Victor Hugo Paris", "12 rue Victor Hugo 75015 Paris")
        self.assertIn(r["decision"], {"MEME_ADRESSE", "A_CONTROLER"})

    def test_raw_model_score_is_exposed_for_audit(self):
        r = self.score("1 rue A 75001 Paris", "999 rue A 75001 Paris")
        self.assertIn("raw_model_score", r)
        self.assertGreaterEqual(r["raw_model_score"], r["score_final"])


if __name__ == "__main__":
    unittest.main()
