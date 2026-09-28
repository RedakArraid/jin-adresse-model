from __future__ import annotations

import csv
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
SCRIPT = ROOT / "scripts" / "download_ban.py"
sys.path.insert(0, str(APP))

from ban_local import LocalBANGeocoder
from matcher import AddressMatcher
from score_address_pair_v3 import parse_address

spec = importlib.util.spec_from_file_location("download_ban", SCRIPT)
download_ban = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(download_ban)

FIELDS = ["id_ban", "numero", "rep", "nom_voie", "code_postal", "code_insee", "nom_commune", "lon", "lat"]


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
        w.writeheader()
        w.writerows(rows)


class BanTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)
        self.db = self.dir / "ban.sqlite"

    def tearDown(self):
        self.td.cleanup()

    def rows(self):
        return [
            {"id_ban":"PARIS-1","numero":"10","rep":"","nom_voie":"Rue de Paris","code_postal":"75001","code_insee":"75056","nom_commune":"Paris","lon":"2.35","lat":"48.86"},
            {"id_ban":"LYON-1","numero":"10","rep":"","nom_voie":"Rue de Lyon","code_postal":"75001","code_insee":"75056","nom_commune":"Paris","lon":"2.351","lat":"48.861"},
            {"id_ban":"HUGO-14","numero":"14","rep":"","nom_voie":"Rue Victor Hugo","code_postal":"92110","code_insee":"92024","nom_commune":"Clichy","lon":"2.30","lat":"48.90"},
            {"id_ban":"HUGO-14B","numero":"14","rep":"bis","nom_voie":"Rue Victor Hugo","code_postal":"92110","code_insee":"92024","nom_commune":"Clichy","lon":"2.3001","lat":"48.9001"},
        ]

    def import_rows(self, rows=None, dep="75"):
        p = self.dir / f"adresses-with-ids-{dep}.csv"
        write_csv(p, rows or self.rows())
        con = download_ban.init_db(self.db)
        try:
            download_ban.import_department_atomic(con, p, dep)
        finally:
            con.close()

    def test_lookup_uses_street_not_arbitrary_postcode_slice(self):
        self.import_rows()
        g = LocalBANGeocoder(self.db)
        p = parse_address("rue de Lyon 75001 Paris", {})
        r = g.lookup("rue de Lyon 75001 Paris", p)
        self.assertEqual(r.id_ban, "LYON-1")
        self.assertIn(r.existence_status, {"CONFIRMED_STREET", "PLAUSIBLE_STREET"})

    def test_number_and_suffix_are_discriminating(self):
        self.import_rows(dep="92")
        g = LocalBANGeocoder(self.db)
        r = g.lookup("14 bis rue Victor Hugo 92110 Clichy", parse_address("14 bis rue Victor Hugo 92110 Clichy", {}))
        self.assertEqual(r.id_ban, "HUGO-14B")
        self.assertEqual(r.existence_status, "CONFIRMED_HOUSENUMBER")

    def test_not_found(self):
        self.import_rows()
        g = LocalBANGeocoder(self.db)
        r = g.lookup("999 rue Inconnue 75001 Paris", parse_address("999 rue Inconnue 75001 Paris", {}))
        self.assertEqual(r.existence_status, "NOT_FOUND")

    def test_near_street_typo_remains_review_with_ban(self):
        rows = [{
            "id_ban":"JAURES-12",
            "numero":"12",
            "rep":"",
            "nom_voie":"Avenue Jean Jaures",
            "code_postal":"75019",
            "code_insee":"75056",
            "nom_commune":"Paris",
            "lon":"2.38",
            "lat":"48.88",
        }]
        self.import_rows(rows=rows, dep="75")
        m = AddressMatcher(APP / "model_config.json", self.db)
        r = m.score(
            "12 avenue jean jaures 75019 paris",
            "12 avenue jean jauresx 75019 paris",
            use_ban=True,
        )
        self.assertEqual(r["decision"], "A_CONTROLER")
        self.assertEqual(r["decision_reason"], "NOM_VOIE_PROCHE_NON_IDENTIQUE")
        self.assertLessEqual(r["score_final"], 89.0)

    def test_stats_come_from_metadata(self):
        self.import_rows()
        g = LocalBANGeocoder(self.db)
        s = g.stats()
        self.assertTrue(s["available"])
        self.assertEqual(s["rows"], 4)
        self.assertIn("rows_total", s["metadata"])
        self.assertEqual(s["departments"], ["75"])

    def test_failed_import_keeps_live_department_unchanged(self):
        old = self.dir / "adresses-with-ids-13.csv"
        write_csv(old, [{"id_ban":"OLD","numero":"1","rep":"","nom_voie":"Rue Ancienne","code_postal":"13001","code_insee":"13055","nom_commune":"Marseille","lon":"5.3","lat":"43.3"}])
        con = download_ban.init_db(self.db)
        try:
            download_ban.import_department_atomic(con, old, "13")
            new = self.dir / "new.csv"
            write_csv(new, [
                {"id_ban":"NEW1","numero":"2","rep":"","nom_voie":"Rue Nouvelle","code_postal":"13001","code_insee":"13055","nom_commune":"Marseille","lon":"5.3","lat":"43.3"},
                {"id_ban":"NEW2","numero":"3","rep":"","nom_voie":"Rue Nouvelle","code_postal":"13001","code_insee":"13055","nom_commune":"Marseille","lon":"5.3","lat":"43.3"},
            ])
            with self.assertRaises(RuntimeError):
                download_ban.import_department_atomic(con, new, "13", fail_after=1)
            live = con.execute("SELECT id_ban FROM ban_addresses WHERE departement='13'").fetchall()
            self.assertEqual(live, [("OLD",)])
            staged = con.execute("SELECT COUNT(*) FROM ban_staging WHERE departement='13'").fetchone()[0]
            self.assertEqual(staged, 0)
        finally:
            con.close()

    def test_invalid_csv_does_not_replace_live_data(self):
        self.import_rows(dep="75")
        bad = self.dir / "bad.csv"
        bad.write_text("id_ban;numero\nX;1\n", encoding="utf-8")
        con = sqlite3.connect(self.db)
        try:
            before = con.execute("SELECT COUNT(*) FROM ban_addresses WHERE departement='75'").fetchone()[0]
        finally:
            con.close()
        con = download_ban.init_db(self.db)
        try:
            with self.assertRaises(ValueError):
                download_ban.import_department_atomic(con, bad, "75")
            after = con.execute("SELECT COUNT(*) FROM ban_addresses WHERE departement='75'").fetchone()[0]
            self.assertEqual(after, before)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
