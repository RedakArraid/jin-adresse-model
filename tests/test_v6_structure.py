from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
SCRIPT = ROOT / "scripts" / "download_ban.py"
sys.path.insert(0, str(APP))

from matcher import AddressMatcher

spec = importlib.util.spec_from_file_location("download_ban_v6", SCRIPT)
download_ban = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(download_ban)


class V6StructureTests(unittest.TestCase):
    def setUp(self):
        self.model = APP / "model_config.json"

    def test_city_typo_is_review_without_ban(self):
        matcher = AddressMatcher(self.model, "/tmp/no-v6-ban.sqlite")
        result = matcher.score(
            "370 RTE DE ST CANADET 13100 AIX EN providence",
            "370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
            use_ban=False,
        )
        self.assertEqual(result["decision"], "A_CONTROLER")
        self.assertEqual(result["decision_reason"], "COMMUNE_PROCHE_NON_IDENTIQUE")
        self.assertLessEqual(result["confidence_score"], 89.0)
        self.assertGreater(result["similarity_score"], result["confidence_score"])
        self.assertEqual(result["field_evidence"]["city"]["status"], "TYPO_LIKELY")

    def test_hard_number_conflict_wins_over_city_typo(self):
        matcher = AddressMatcher(self.model, "/tmp/no-v6-ban.sqlite")
        result = matcher.score(
            "370 RTE DE ST CANADET 13100 AIX EN providence",
            "371 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
            use_ban=False,
        )
        self.assertEqual(result["decision"], "DIFFERENTE")
        self.assertEqual(result["decision_reason"], "CONFLIT_NUMERO")

    def test_canonical_keys_are_exposed(self):
        matcher = AddressMatcher(self.model, "/tmp/no-v6-ban.sqlite")
        result = matcher.score(
            "187 bld de pontoise 75015 paris",
            "187 boulevard de pontoise 75015 paris",
            use_ban=False,
        )
        canonical = result["canonical_A"]
        self.assertEqual(canonical["house_key"], "187|")
        self.assertEqual(canonical["street_key"], "boulevard|de pontoise")
        self.assertEqual(canonical["locality_key"], "75015|paris")
        self.assertIn("address_key", canonical)
        self.assertTrue(result["field_evidence"]["exact_structure"])

    def test_local_ban_canonicalizes_city_typo(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            csv_path = td / "adresses-with-ids-13.csv"
            db_path = td / "ban.sqlite"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "id_ban", "numero", "rep", "nom_voie", "code_postal",
                        "code_insee", "nom_commune", "lon", "lat",
                    ],
                    delimiter=";",
                )
                writer.writeheader()
                writer.writerow({
                    "id_ban": "TEST-370",
                    "numero": "370",
                    "rep": "",
                    "nom_voie": "Route de Saint Canadet",
                    "code_postal": "13100",
                    "code_insee": "13001",
                    "nom_commune": "Aix-en-Provence",
                    "lon": "5.44",
                    "lat": "43.55",
                })

            con = download_ban.init_db(db_path)
            try:
                download_ban.import_department_atomic(con, csv_path, "13")
            finally:
                con.close()

            matcher = AddressMatcher(self.model, db_path)
            result = matcher.score(
                "370 RTE DE ST CANADET 13100 AIX EN providence",
                "370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
                use_ban=True,
            )

            self.assertEqual(result["canonical_A"]["locality_status"], "TYPO_CORRECTED")
            self.assertEqual(result["canonical_A"]["city"], "aix en provence")
            self.assertEqual(result["canonical_A"]["city_code"], "13001")
            self.assertEqual(result["field_evidence"]["city"]["status"], "NORMALIZED_EXACT")
            self.assertEqual(result["decision"], "MEME_ADRESSE")
            self.assertGreaterEqual(result["score_final"], 99.0)


if __name__ == "__main__":
    unittest.main()
