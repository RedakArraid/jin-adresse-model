from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
os.environ["MODEL_PATH"] = str(APP / "model_config.json")
os.environ["BAN_DB_PATH"] = "/tmp/address-matcher-api-test-no-ban.sqlite"
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient
import api


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        api.get_matcher.cache_clear()
        cls.client = TestClient(api.app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["model_version"], "V5.3-local-BAN")

    def test_score_endpoint(self):
        r = self.client.post("/score", json={
            "address_a":"370 RTE DE ST CANADET 13100 AIX EN PROVENCE",
            "address_b":"370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
            "use_ban":False,
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["decision"], "MEME_ADRESSE")

    def test_short_input_rejected(self):
        r = self.client.post("/score", json={"address_a":"ab", "address_b":"10 rue A 75001 Paris"})
        self.assertEqual(r.status_code, 422)

    def test_whitespace_only_input_rejected(self):
        r = self.client.post("/score", json={"address_a":"     ", "address_b":"10 rue A 75001 Paris"})
        self.assertEqual(r.status_code, 422)

    def test_too_long_input_rejected(self):
        r = self.client.post("/score", json={"address_a":"x"*501, "address_b":"10 rue A 75001 Paris"})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
