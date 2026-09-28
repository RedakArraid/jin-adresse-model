from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(APP))

from matcher import AddressMatcher


class MatcherTests(unittest.TestCase):
    def test_text_only_saint_canadet(self):
        m = AddressMatcher(APP / "modele_matching_adresses_v3.joblib", "/tmp/does-not-exist-ban.sqlite")
        r = m.score(
            "370 RTE DE ST CANADET 13100 AIX EN PROVENCE",
            "370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
            use_ban=True,
        )
        self.assertEqual(r["decision"], "MEME_ADRESSE")
        self.assertGreaterEqual(r["score_final"], 95)
        self.assertFalse(r["ban_used"])

    def test_local_ban_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            csv_path = td / "adresses-with-ids-13.csv"
            db_path = td / "ban.sqlite"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["id_ban", "numero", "rep", "nom_voie", "code_postal", "code_insee", "nom_commune", "lon", "lat"], delimiter=";")
                w.writeheader()
                w.writerow({
                    "id_ban": "TEST-SAINT-CANADET-370",
                    "numero": "370",
                    "rep": "",
                    "nom_voie": "Route de Saint-Canadet",
                    "code_postal": "13100",
                    "code_insee": "13001",
                    "nom_commune": "Aix-en-Provence",
                    "lon": "5.44",
                    "lat": "43.55",
                })
            subprocess.run([
                sys.executable, str(SCRIPTS / "download_ban.py"), "--db", str(db_path), "--from-file", str(csv_path)
            ], check=True, env={**os.environ, "PYTHONPATH": str(APP)})
            m = AddressMatcher(APP / "modele_matching_adresses_v3.joblib", db_path)
            r = m.score(
                "370 RTE DE ST CANADET 13100 AIX EN PROVENCE",
                "370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
                use_ban=True,
            )
            self.assertTrue(r["ban_used"])
            self.assertEqual(r["decision"], "MEME_ADRESSE")
            self.assertEqual(r["address_a_ban"]["id_ban"], "TEST-SAINT-CANADET-370")
            self.assertEqual(r["address_b_ban"]["id_ban"], "TEST-SAINT-CANADET-370")


if __name__ == "__main__":
    unittest.main()
