from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import json
import math

from ban_local import LocalBANGeocoder, official_pair_features
from score_address_pair_v3 import (
    make_city_map,
    make_features,
    normalize_text,
    safe_token_set,
    jaccard_tokens,
)


class AddressMatcher:
    def __init__(self, model_path: str | Path | None = None, ban_db_path: str | Path | None = None):
        self.model_path = Path(model_path or os.environ.get("MODEL_PATH", "/app/model_config.json"))
        self.pkg = json.loads(self.model_path.read_text(encoding="utf-8"))
        self.city_map = make_city_map(self.pkg["cities"])
        self.ban = LocalBANGeocoder(ban_db_path)

    def text_score(self, address_a: str, address_b: str) -> Dict[str, Any]:
        f, pa, pb = make_features(address_a, address_b, self.city_map)
        z = float(self.pkg["intercept"])
        for name in self.pkg["features"]:
            z += float(self.pkg["coefficients"][name]) * float(f.get(name, 0.0) or 0.0)
        p = 1.0 / (1.0 + math.exp(-max(min(z, 60.0), -60.0)))
        if p >= self.pkg["threshold_match"]:
            decision = "MEME_ADRESSE"
        elif p <= self.pkg["threshold_different"]:
            decision = "DIFFERENTE"
        else:
            decision = "A_CONTROLER"
        reason = "MODELE_V3"
        if decision == "MEME_ADRESSE" and pa.get("nom_voie") and pb.get("nom_voie") and pa["nom_voie"] != pb["nom_voie"]:
            street_sim = safe_token_set(pa["nom_voie"], pb["nom_voie"])
            street_jac = jaccard_tokens(pa["nom_voie"], pb["nom_voie"])
            same_core = (
                bool(pa.get("numero")) and pa.get("numero") == pb.get("numero")
                and bool(pa.get("code_postal")) and pa.get("code_postal") == pb.get("code_postal")
                and bool(pa.get("ville_norm")) and pa.get("ville_norm") == pb.get("ville_norm")
            )
            if same_core and street_sim < 0.84 and street_jac <= 0.50:
                decision = "A_CONTROLER"
                reason = "NOM_VOIE_PROCHE_MAIS_NON_EQUIVALENT"
        return {
            "score": round(p * 100, 2),
            "decision": decision,
            "decision_reason": reason,
            "parsed_A": pa,
            "parsed_B": pb,
            "threshold_different": round(self.pkg["threshold_different"] * 100, 2),
            "threshold_match": round(self.pkg["threshold_match"] * 100, 2),
        }

    def score(self, address_a: str, address_b: str, use_ban: bool = True) -> Dict[str, Any]:
        text = self.text_score(address_a, address_b)
        base = {
            "score_final": text["score"],
            "decision": text["decision"],
            "decision_reason": text["decision_reason"],
            "score_text_v3": text["score"],
            "decision_text_v3": text["decision"],
            "parsed_A": text["parsed_A"],
            "parsed_B": text["parsed_B"],
            "ban_used": False,
            "ban_available": self.ban.available(),
            "model_version": "V5-local-BAN",
        }
        if not use_ban or not self.ban.available():
            base["decision_reason"] = "BAN_LOCALE_DESACTIVEE" if not use_ban else "BAN_LOCALE_ABSENTE_FALLBACK_V3"
            return base

        ga = self.ban.lookup(address_a, text["parsed_A"])
        gb = self.ban.lookup(address_b, text["parsed_B"])
        pf = official_pair_features(ga, gb)
        text_p = text["score"] / 100.0
        official_p = pf["official_pair_score"]
        final_p = 0.72 * text_p + 0.28 * official_p if pf["usable_both"] else text_p
        decision = text["decision"]
        reason = "V3_PLUS_BAN_LOCALE"

        exact_a = ga.existence_status == "CONFIRMED_HOUSENUMBER"
        exact_b = gb.existence_status == "CONFIRMED_HOUSENUMBER"
        if pf["same_official_id"] and exact_a and exact_b:
            decision = "MEME_ADRESSE"
            final_p = max(final_p, 0.999)
            reason = "MEME_ID_BAN"
        elif exact_a and exact_b:
            dist = pf["official_distance_m"]
            strong_same = (
                pf["official_number_same"]
                and pf["official_suffix_same"]
                and pf["official_postcode_same"]
                and pf["official_city_same"]
                and pf["official_street_similarity"] >= 0.96
                and (dist is None or dist <= 20.0)
            )
            strong_conflict = (
                (not pf["official_number_same"] or not pf["official_suffix_same"] or not pf["official_city_same"] or not pf["official_postcode_same"])
                and dist is not None and dist > 25.0
            ) or (pf["official_street_similarity"] < 0.78 and dist is not None and dist > 80.0)
            if strong_same:
                decision = "MEME_ADRESSE"
                final_p = max(final_p, 0.985)
                reason = "BAN_LOCALE_COHERENTE"
            elif strong_conflict:
                if text_p >= 0.90:
                    decision = "A_CONTROLER"
                    final_p = min(final_p, 0.74)
                    reason = "TEXTE_FORT_MAIS_CONFLIT_BAN"
                else:
                    decision = "DIFFERENTE"
                    final_p = min(final_p, 0.20)
                    reason = "CONFLIT_BAN_LOCALE"
            elif text["decision"] == "MEME_ADRESSE" and official_p < 0.82:
                decision = "A_CONTROLER"
                reason = "PREUVE_BAN_AMBIGUE"
        else:
            if text["decision"] == "MEME_ADRESSE":
                if ga.existence_status == "NOT_FOUND" and gb.existence_status == "NOT_FOUND":
                    decision = "A_CONTROLER"
                    final_p = min(final_p, 0.90)
                    reason = "DEUX_ADRESSES_NON_TROUVEES_DANS_BAN"
                elif ga.existence_status in {"NOT_FOUND", "WEAK", "PLAUSIBLE_HOUSENUMBER"} or gb.existence_status in {"NOT_FOUND", "WEAK", "PLAUSIBLE_HOUSENUMBER"}:
                    decision = "A_CONTROLER"
                    final_p = min(final_p, 0.92)
                    reason = "EXISTENCE_EXACTE_NON_CONFIRMEE"

        base.update({
            "score_final": round(min(max(final_p, 0.0), 1.0) * 100.0, 2),
            "decision": decision,
            "decision_reason": reason,
            "ban_used": True,
            "official_pair": pf,
            "address_a_ban": ga.to_dict(),
            "address_b_ban": gb.to_dict(),
        })
        return base
