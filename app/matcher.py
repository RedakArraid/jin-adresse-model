from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from address_domain import AddressComparator, AddressEvidence, AddressResolver, CanonicalAddress
from ban_local import LocalBANGeocoder, official_pair_features
from decision_engine import DecisionEngine
from score_address_pair_v3 import make_city_map, make_features


class AddressMatcher:
    def __init__(self, model_path: str | Path | None = None, ban_db_path: str | Path | None = None):
        self.model_path = Path(model_path or os.environ.get("MODEL_PATH", "/app/model_config.json"))
        self.pkg = json.loads(self.model_path.read_text(encoding="utf-8"))
        self.city_map = make_city_map(self.pkg.get("cities", []))
        self.policy = self.pkg["decision_policy"]
        self.version = self.pkg.get("runtime_version", self.pkg.get("version", "unknown"))
        self.ban = LocalBANGeocoder(ban_db_path)
        self.resolver = AddressResolver(self.ban, self.policy)
        self.comparator = AddressComparator(self.policy)
        self.decision_engine = DecisionEngine(
            self.policy,
            threshold_different=float(self.pkg["threshold_different"]),
            threshold_match=float(self.pkg["threshold_match"]),
        )

    def _raw_model_score(self, address_a: str, address_b: str) -> Tuple[float, Dict[str, Any]]:
        features, _, _ = make_features(address_a, address_b, self.city_map)
        z = float(self.pkg["intercept"])
        for name in self.pkg["features"]:
            z += float(self.pkg["coefficients"][name]) * float(features.get(name, 0.0) or 0.0)
        p = 1.0 / (1.0 + math.exp(-max(min(z, 60.0), -60.0)))
        return p * 100.0, features

    def _analyze_text(
        self,
        address_a: str,
        address_b: str,
        resolve_locality: bool,
    ) -> Tuple[Dict[str, Any], CanonicalAddress, CanonicalAddress, AddressEvidence]:
        raw_model_score, features = self._raw_model_score(address_a, address_b)
        canonical_a = self.resolver.canonicalize(address_a, use_locality_resolver=resolve_locality)
        canonical_b = self.resolver.canonicalize(address_b, use_locality_resolver=resolve_locality)
        evidence = self.comparator.compare(canonical_a, canonical_b)
        decision = self.decision_engine.apply_text(raw_model_score, evidence)

        result = {
            "score": decision["score"],
            "raw_model_score": round(raw_model_score, 2),
            "similarity_score": round(raw_model_score, 2),
            "confidence_score": decision["score"],
            "decision": decision["decision"],
            "decision_reason": decision["decision_reason"],
            "parsed_A": canonical_a.to_parsed_dict(),
            "parsed_B": canonical_b.to_parsed_dict(),
            "canonical_A": canonical_a.to_dict(),
            "canonical_B": canonical_b.to_dict(),
            "field_evidence": evidence.to_dict(),
            "features": features,
            "threshold_different": round(float(self.pkg["threshold_different"]) * 100.0, 2),
            "threshold_match": round(float(self.pkg["threshold_match"]) * 100.0, 2),
        }
        return result, canonical_a, canonical_b, evidence

    def text_score(self, address_a: str, address_b: str) -> Dict[str, Any]:
        result, _, _, _ = self._analyze_text(
            address_a,
            address_b,
            resolve_locality=False,
        )
        return result

    @staticmethod
    def _enrich_canonical_from_ban(canonical: CanonicalAddress, ban_result) -> None:
        if ban_result.existence_status in {
            "CONFIRMED_HOUSENUMBER",
            "PLAUSIBLE_HOUSENUMBER",
            "CONFIRMED_STREET",
            "PLAUSIBLE_STREET",
        }:
            canonical.ban_id = ban_result.id_ban or canonical.ban_id
            canonical.longitude = ban_result.longitude
            canonical.latitude = ban_result.latitude
            if not canonical.city_code:
                canonical.city_code = ban_result.code_insee or ""
            if ban_result.nom_commune and canonical.locality_status in {"UNRESOLVED", "NOT_FOUND"}:
                canonical.city_canonical = canonical.city_canonical or ban_result.nom_commune

    def score(self, address_a: str, address_b: str, use_ban: bool = True) -> Dict[str, Any]:
        ban_available = self.ban.available()
        resolve_locality = bool(use_ban and ban_available)
        text, canonical_a, canonical_b, evidence = self._analyze_text(
            address_a,
            address_b,
            resolve_locality=resolve_locality,
        )

        base = {
            "score_final": text["score"],
            "similarity_score": text["similarity_score"],
            "confidence_score": text["confidence_score"],
            "decision": text["decision"],
            "decision_reason": text["decision_reason"],
            "score_text": text["score"],
            "decision_text": text["decision"],
            "score_text_v3": text["score"],
            "raw_model_score": text["raw_model_score"],
            "decision_text_v3": text["decision"],
            "parsed_A": text["parsed_A"],
            "parsed_B": text["parsed_B"],
            "canonical_A": text["canonical_A"],
            "canonical_B": text["canonical_B"],
            "field_evidence": text["field_evidence"],
            "ban_used": False,
            "ban_available": ban_available,
            "model_version": self.version,
        }

        if not use_ban or not ban_available:
            if text["decision_reason"] == "MODELE_SIMILARITE":
                base["decision_reason"] = (
                    "BAN_LOCALE_DESACTIVEE"
                    if not use_ban
                    else "BAN_LOCALE_ABSENTE_FALLBACK_V6"
                )
            return base

        ga = self.ban.lookup(address_a, canonical_a.to_lookup_dict())
        gb = self.ban.lookup(address_b, canonical_b.to_lookup_dict())
        self._enrich_canonical_from_ban(canonical_a, ga)
        self._enrich_canonical_from_ban(canonical_b, gb)

        official_pair = official_pair_features(ga, gb)
        final_decision = self.decision_engine.apply_ban(
            text,
            official_pair,
            ga,
            gb,
        )

        base.update({
            "score_final": final_decision["score"],
            "confidence_score": final_decision["score"],
            "decision": final_decision["decision"],
            "decision_reason": final_decision["decision_reason"],
            "ban_used": True,
            "official_pair": official_pair,
            "address_a_ban": ga.to_dict(),
            "address_b_ban": gb.to_dict(),
            "canonical_A": canonical_a.to_dict(),
            "canonical_B": canonical_b.to_dict(),
            "field_evidence": evidence.to_dict(),
        })
        return base
