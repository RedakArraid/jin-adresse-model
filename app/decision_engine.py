from __future__ import annotations

from typing import Any, Dict

from address_domain import AddressEvidence


class DecisionEngine:
    def __init__(self, policy: Dict[str, Any], threshold_different: float, threshold_match: float):
        self.policy = policy
        self.threshold_different = float(threshold_different)
        self.threshold_match = float(threshold_match)

    def _cap(self, reason: str) -> float:
        return float(self.policy["score_caps"][reason])

    def _floor(self, reason: str) -> float:
        return float(self.policy["score_floors"][reason])

    def apply_text(self, raw_model_score: float, evidence: AddressEvidence) -> Dict[str, Any]:
        p = float(raw_model_score) / 100.0
        if p >= self.threshold_match:
            decision = "MEME_ADRESSE"
        elif p <= self.threshold_different:
            decision = "DIFFERENTE"
        else:
            decision = "A_CONTROLER"
        reason = "MODELE_SIMILARITE"
        score = float(raw_model_score)

        if evidence.postcode.status == "CONFLICT":
            return self._result("DIFFERENTE", "CONFLIT_CODE_POSTAL", min(score, self._cap("CONFLIT_CODE_POSTAL")))

        if evidence.number.status == "CONFLICT":
            return self._result("DIFFERENTE", "CONFLIT_NUMERO", min(score, self._cap("CONFLIT_NUMERO")))

        if evidence.suffix.status == "CONFLICT":
            return self._result(
                "DIFFERENTE",
                "CONFLIT_SUFFIXE_NUMERO",
                min(score, self._cap("CONFLIT_SUFFIXE_NUMERO")),
            )

        if evidence.street_type.status == "CONFLICT":
            return self._result(
                "DIFFERENTE",
                "CONFLIT_TYPE_VOIE",
                min(score, self._cap("CONFLIT_TYPE_VOIE")),
            )

        if evidence.city.status == "CONFLICT":
            return self._result("DIFFERENTE", "CONFLIT_COMMUNE", min(score, self._cap("CONFLIT_COMMUNE")))

        if evidence.street_name.status == "CONFLICT" and evidence.strong_location:
            return self._result(
                "DIFFERENTE",
                "CONFLIT_NOM_VOIE",
                min(score, self._cap("CONFLIT_NOM_VOIE")),
            )

        if evidence.city.status == "TYPO_LIKELY":
            return self._result(
                "A_CONTROLER",
                "COMMUNE_PROCHE_NON_IDENTIQUE",
                min(score, self._cap("COMMUNE_PROCHE_NON_IDENTIQUE")),
            )

        if evidence.street_name.status == "TYPO_LIKELY" and evidence.strong_location:
            return self._result(
                "A_CONTROLER",
                "NOM_VOIE_PROCHE_NON_IDENTIQUE",
                min(score, self._cap("NOM_VOIE_PROCHE_NON_IDENTIQUE")),
            )

        if evidence.exact_structure:
            return self._result(
                "MEME_ADRESSE",
                "STRUCTURE_IDENTIQUE",
                max(score, self._floor("STRUCTURE_IDENTIQUE")),
            )

        return self._result(decision, reason, score)

    def apply_ban(
        self,
        text_result: Dict[str, Any],
        official_pair: Dict[str, Any],
        address_a_ban,
        address_b_ban,
    ) -> Dict[str, Any]:
        ban_policy = self.policy["ban"]
        text_score = float(text_result["score"])
        text_p = text_score / 100.0
        official_p = float(official_pair["official_pair_score"])

        if official_pair["usable_both"]:
            final_p = (
                float(ban_policy["text_weight"]) * text_p
                + float(ban_policy["official_weight"]) * official_p
            )
        else:
            final_p = text_p

        decision = text_result["decision"]
        reason = text_result["decision_reason"]

        hard_text_conflict = (
            decision == "DIFFERENTE"
            and str(reason).startswith("CONFLIT_")
        )
        guarded_review = reason in set(ban_policy["guarded_review_reasons"])

        exact_a = address_a_ban.existence_status == "CONFIRMED_HOUSENUMBER"
        exact_b = address_b_ban.existence_status == "CONFIRMED_HOUSENUMBER"

        if hard_text_conflict:
            return self._result(decision, reason, min(final_p * 100.0, text_score))

        if guarded_review:
            return self._result(
                "A_CONTROLER",
                reason,
                min(final_p * 100.0, float(ban_policy["guarded_review_max_score"])),
            )

        if official_pair["same_official_id"] and exact_a and exact_b:
            return self._result(
                "MEME_ADRESSE",
                "MEME_ID_BAN",
                max(final_p * 100.0, self._floor("MEME_ID_BAN")),
            )

        if exact_a and exact_b:
            dist = official_pair["official_distance_m"]
            strong_same = (
                official_pair["official_number_same"]
                and official_pair["official_suffix_same"]
                and official_pair["official_postcode_same"]
                and official_pair["official_city_same"]
                and official_pair["official_street_similarity"] >= float(ban_policy["same_street_min"])
                and (dist is None or dist <= float(ban_policy["same_distance_max_m"]))
            )
            strong_conflict = (
                (
                    not official_pair["official_number_same"]
                    or not official_pair["official_suffix_same"]
                    or not official_pair["official_city_same"]
                    or not official_pair["official_postcode_same"]
                )
                and dist is not None
                and dist > float(ban_policy["conflict_distance_min_m"])
            ) or (
                official_pair["official_street_similarity"] < float(ban_policy["street_conflict_below"])
                and dist is not None
                and dist > float(ban_policy["street_conflict_distance_min_m"])
            )

            if strong_same:
                return self._result(
                    "MEME_ADRESSE",
                    "BAN_LOCALE_COHERENTE",
                    max(final_p * 100.0, self._floor("BAN_LOCALE_COHERENTE")),
                )

            if strong_conflict:
                if float(text_result["raw_model_score"]) >= float(ban_policy["strong_text_score_min"]):
                    return self._result(
                        "A_CONTROLER",
                        "TEXTE_FORT_MAIS_CONFLIT_BAN",
                        min(final_p * 100.0, float(ban_policy["text_conflict_review_max_score"])),
                    )
                return self._result(
                    "DIFFERENTE",
                    "CONFLIT_BAN_LOCALE",
                    min(final_p * 100.0, float(ban_policy["conflict_different_max_score"])),
                )

            if (
                text_result["decision"] == "MEME_ADRESSE"
                and official_p < float(ban_policy["official_ambiguous_below"])
            ):
                return self._result("A_CONTROLER", "PREUVE_BAN_AMBIGUE", final_p * 100.0)

        if text_result["decision"] == "MEME_ADRESSE":
            if (
                address_a_ban.existence_status == "NOT_FOUND"
                and address_b_ban.existence_status == "NOT_FOUND"
            ):
                return self._result(
                    "A_CONTROLER",
                    "DEUX_ADRESSES_NON_TROUVEES_DANS_BAN",
                    min(final_p * 100.0, float(ban_policy["both_not_found_max_score"])),
                )

            weak = {"NOT_FOUND", "WEAK", "PLAUSIBLE_HOUSENUMBER"}
            if address_a_ban.existence_status in weak or address_b_ban.existence_status in weak:
                return self._result(
                    "A_CONTROLER",
                    "EXISTENCE_EXACTE_NON_CONFIRMEE",
                    min(final_p * 100.0, float(ban_policy["existence_not_confirmed_max_score"])),
                )

        return self._result(decision, reason, final_p * 100.0)

    @staticmethod
    def _result(decision: str, reason: str, score: float) -> Dict[str, Any]:
        return {
            "decision": decision,
            "decision_reason": reason,
            "score": round(min(max(float(score), 0.0), 100.0), 2),
        }
