from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ban_local import LocalBANGeocoder, official_pair_features
from score_address_pair_v3 import (
    jaccard_tokens,
    make_city_map,
    make_features,
    safe_ratio,
    safe_token_set,
)


class AddressMatcher:
    def __init__(self, model_path: str | Path | None = None, ban_db_path: str | Path | None = None):
        self.model_path = Path(model_path or os.environ.get("MODEL_PATH", "/app/model_config.json"))
        self.pkg = json.loads(self.model_path.read_text(encoding="utf-8"))
        self.city_map = make_city_map(self.pkg.get("cities", []))
        self.ban = LocalBANGeocoder(ban_db_path)

    @staticmethod
    def _structural_rule(pa: Dict[str, str], pb: Dict[str, str]) -> Optional[Tuple[str, str, float]]:
        numa, numb = pa.get("numero", ""), pb.get("numero", "")
        sa, sb = pa.get("suffixe", ""), pb.get("suffixe", "")
        cpa, cpb = pa.get("code_postal", ""), pb.get("code_postal", "")
        ca, cb = pa.get("ville_norm", ""), pb.get("ville_norm", "")
        va, vb = pa.get("nom_voie", ""), pb.get("nom_voie", "")
        ta, tb = pa.get("type_voie", ""), pb.get("type_voie", "")

        if cpa and cpb and cpa != cpb:
            return "DIFFERENTE", "CONFLIT_CODE_POSTAL", 4.0

        if ca and cb:
            city_sim = safe_ratio(ca, cb)
            if city_sim < 0.65:
                return "DIFFERENTE", "CONFLIT_COMMUNE", 4.0
            if city_sim < 0.88:
                return "A_CONTROLER", "COMMUNE_AMBIGUE", 80.0

        if numa and numb and numa != numb:
            return "DIFFERENTE", "CONFLIT_NUMERO", 4.0

        if numa and numb and numa == numb and sa != sb and (sa or sb):
            return "DIFFERENTE", "CONFLIT_SUFFIXE_NUMERO", 4.0

        if ta and tb and ta != tb:
            return "DIFFERENTE", "CONFLIT_TYPE_VOIE", 8.0

        if va and vb and va != vb:
            street_set = safe_token_set(va, vb)
            street_ratio = safe_ratio(va, vb)
            street_jac = jaccard_tokens(va, vb)
            strong_location = (
                (not cpa or not cpb or cpa == cpb)
                and (not ca or not cb or safe_ratio(ca, cb) >= 0.95)
                and (not numa or not numb or numa == numb)
            )
            same_tokens = sorted(va.split()) == sorted(vb.split())
            if strong_location and max(street_set, street_ratio) < 0.72:
                return "DIFFERENTE", "CONFLIT_NOM_VOIE", 15.0
            if strong_location and not same_tokens:
                return "A_CONTROLER", "NOM_VOIE_PROCHE_NON_IDENTIQUE", 89.0

        return None

    @staticmethod
    def _strong_exact_match(pa: Dict[str, str], pb: Dict[str, str]) -> bool:
        """High-confidence match only when all key structural fields agree.

        Conflict rules are evaluated first, so this rule cannot override an
        explicit number, suffix, postal-code, city or strong street conflict.
        """
        required_pairs = (
            (pa.get("numero", ""), pb.get("numero", "")),
            (pa.get("type_voie", ""), pb.get("type_voie", "")),
            (pa.get("nom_voie", ""), pb.get("nom_voie", "")),
            (pa.get("code_postal", ""), pb.get("code_postal", "")),
            (pa.get("ville_norm", ""), pb.get("ville_norm", "")),
        )
        if not all(a and b and a == b for a, b in required_pairs):
            return False
        return pa.get("suffixe", "") == pb.get("suffixe", "")

    def text_score(self, address_a: str, address_b: str) -> Dict[str, Any]:
        f, pa, pb = make_features(address_a, address_b, self.city_map)
        z = float(self.pkg["intercept"])
        for name in self.pkg["features"]:
            z += float(self.pkg["coefficients"][name]) * float(f.get(name, 0.0) or 0.0)
        p = 1.0 / (1.0 + math.exp(-max(min(z, 60.0), -60.0)))
        score = p * 100.0

        if p >= self.pkg["threshold_match"]:
            decision = "MEME_ADRESSE"
        elif p <= self.pkg["threshold_different"]:
            decision = "DIFFERENTE"
        else:
            decision = "A_CONTROLER"
        reason = "MODELE_V3"

        rule = self._structural_rule(pa, pb)
        if rule is not None:
            rule_decision, rule_reason, score_cap = rule
            decision = rule_decision
            reason = rule_reason
            score = min(score, score_cap)
        elif self._strong_exact_match(pa, pb):
            decision = "MEME_ADRESSE"
            reason = "STRUCTURE_IDENTIQUE"
            score = max(score, 99.0)

        return {
            "score": round(score, 2),
            "raw_model_score": round(p * 100.0, 2),
            "decision": decision,
            "decision_reason": reason,
            "parsed_A": pa,
            "parsed_B": pb,
            "features": f,
            "threshold_different": round(self.pkg["threshold_different"] * 100, 2),
            "threshold_match": round(self.pkg["threshold_match"] * 100, 2),
        }

    def score(self, address_a: str, address_b: str, use_ban: bool = True) -> Dict[str, Any]:
        text = self.text_score(address_a, address_b)
        ban_available = self.ban.available()
        base = {
            "score_final": text["score"],
            "decision": text["decision"],
            "decision_reason": text["decision_reason"],
            "score_text_v3": text["score"],
            "raw_model_score": text["raw_model_score"],
            "decision_text_v3": text["decision"],
            "parsed_A": text["parsed_A"],
            "parsed_B": text["parsed_B"],
            "ban_used": False,
            "ban_available": ban_available,
            "model_version": "V5.3-local-BAN",
        }
        if not use_ban or not ban_available:
            if text["decision_reason"] == "MODELE_V3":
                base["decision_reason"] = "BAN_LOCALE_DESACTIVEE" if not use_ban else "BAN_LOCALE_ABSENTE_FALLBACK_V3"
            return base

        ga = self.ban.lookup(address_a, text["parsed_A"])
        gb = self.ban.lookup(address_b, text["parsed_B"])
        pf = official_pair_features(ga, gb)

        hard_text_conflict = (
            text["decision"] == "DIFFERENTE"
            and str(text["decision_reason"]).startswith("CONFLIT_")
        )
        text_p = text["score"] / 100.0
        official_p = pf["official_pair_score"]
        final_p = 0.72 * text_p + 0.28 * official_p if pf["usable_both"] else text_p
        decision = text["decision"]
        reason = text["decision_reason"] if text["decision_reason"] != "MODELE_V3" else "V3_PLUS_BAN_LOCALE"

        exact_a = ga.existence_status == "CONFIRMED_HOUSENUMBER"
        exact_b = gb.existence_status == "CONFIRMED_HOUSENUMBER"
        if hard_text_conflict:
            decision = "DIFFERENTE"
            final_p = min(final_p, text_p)
            reason = text["decision_reason"]
        elif pf["same_official_id"] and exact_a and exact_b:
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
                if text["raw_model_score"] >= 90.0:
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
        elif text["decision"] == "MEME_ADRESSE":
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
