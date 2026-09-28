from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from score_address_pair_v3 import normalize_text, parse_address


class ParserTests(unittest.TestCase):
    def test_street_named_after_city_is_preserved(self):
        p = parse_address("10 rue de Paris 75001 Paris", {})
        self.assertEqual(p["nom_voie"], "de paris")
        self.assertEqual(p["ville_norm"], "paris")
        self.assertEqual(p["ville_source"], "postal_segment")

    def test_street_named_after_other_city_is_preserved(self):
        p = parse_address("18 avenue de Lyon 69003 Lyon", {})
        self.assertEqual(p["nom_voie"], "de lyon")
        self.assertEqual(p["ville_norm"], "lyon")

    def test_unknown_commune_is_parsed_nationally_from_postcode(self):
        p = parse_address("12 rue de la Gare 47200 Marmande", {})
        self.assertEqual(p["code_postal"], "47200")
        self.assertEqual(p["ville_norm"], "marmande")
        self.assertEqual(p["ville_source"], "postal_segment")

    def test_multiword_unknown_commune(self):
        p = parse_address("4 rue Centrale 74200 Thonon-les-Bains", {})
        self.assertEqual(p["ville_norm"], "thonon les bains")
        self.assertEqual(p["nom_voie"], "centrale")

    def test_cedex_is_not_part_of_city(self):
        p = parse_address("8 avenue de France 75013 Paris Cedex 13", {})
        self.assertEqual(p["ville_norm"], "paris")
        self.assertEqual(p["nom_voie"], "de france")

    def test_bis_ter_quater(self):
        self.assertEqual(parse_address("14B rue Victor Hugo 92110 Clichy", {})["suffixe"], "bis")
        self.assertEqual(parse_address("14T rue Victor Hugo 92110 Clichy", {})["suffixe"], "ter")
        self.assertEqual(parse_address("14Q rue Victor Hugo 92110 Clichy", {})["suffixe"], "quater")

    def test_abbreviations(self):
        a = normalize_text("370 RTE DE ST-CANADET 13100 AIX-EN-PROVENCE")
        b = normalize_text("370 route de Saint Canadet 13100 Aix en Provence")
        self.assertEqual(a, b)

    def test_bv_and_bvd_normalize_to_boulevard(self):
        expected = normalize_text("187 boulevard de pontoise 95370 montigny les cormeilles")
        self.assertEqual(
            normalize_text("187 bv de pontoise 95370 montigny les cormeilles"),
            expected,
        )
        self.assertEqual(
            normalize_text("187 bvd de pontoise 95370 montigny les cormeilles"),
            expected,
        )

    def test_without_postcode_is_conservative_without_dictionary(self):
        p = parse_address("10 rue Victor Hugo Paris", {})
        self.assertEqual(p["ville_norm"], "")
        self.assertEqual(p["nom_voie"], "victor hugo paris")


if __name__ == "__main__":
    unittest.main()
