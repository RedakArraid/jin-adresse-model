from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from score_address_pair_v3 import parse_address, safe_ratio, safe_token_set


@dataclass
class CanonicalAddress:
    raw: str
    normalized: str
    number: str = ""
    number_end: str = ""
    suffix: str = ""
    street_type: str = ""
    street_name: str = ""
    postcode: str = ""
    city_input: str = ""
    city_canonical: str = ""
    city_code: str = ""
    city_source: str = ""
    locality_status: str = "UNRESOLVED"
    locality_score: float = 0.0
    ban_id: str = ""
    longitude: Optional[float] = None
    latitude: Optional[float] = None

    @property
    def city(self) -> str:
        return self.city_canonical or self.city_input

    @property
    def house_key(self) -> str:
        number = f"{self.number}-{self.number_end}" if self.number_end else self.number
        return f"{number}|{self.suffix}"

    @property
    def street_key(self) -> str:
        return f"{self.street_type}|{self.street_name}"

    @property
    def locality_key(self) -> str:
        return f"{self.postcode}|{self.city_code or self.city}"

    @property
    def address_key(self) -> str:
        return f"{self.house_key}|{self.street_key}|{self.locality_key}"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["city"] = self.city
        data["house_key"] = self.house_key
        data["street_key"] = self.street_key
        data["locality_key"] = self.locality_key
        data["address_key"] = self.address_key
        return data

    def to_lookup_dict(self) -> Dict[str, str]:
        return {
            "norm": self.normalized,
            "numero": self.number,
            "numero_fin": self.number_end,
            "suffixe": self.suffix,
            "type_voie": self.street_type,
            "nom_voie": self.street_name,
            "code_postal": self.postcode,
            "ville_norm": self.city,
            "ville_source": self.city_source,
        }

    def to_parsed_dict(self) -> Dict[str, str]:
        # Backward-compatible parsed representation: preserve the locality
        # extracted from the input, while canonical_* exposes resolved values.
        return {
            "norm": self.normalized,
            "numero": self.number,
            "numero_fin": self.number_end,
            "suffixe": self.suffix,
            "type_voie": self.street_type,
            "nom_voie": self.street_name,
            "code_postal": self.postcode,
            "ville_norm": self.city_input,
            "ville_source": self.city_source,
        }


@dataclass
class FieldEvidence:
    status: str
    left: str = ""
    right: str = ""
    similarity: Optional[float] = None
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AddressEvidence:
    number: FieldEvidence
    suffix: FieldEvidence
    street_type: FieldEvidence
    street_name: FieldEvidence
    postcode: FieldEvidence
    city: FieldEvidence
    strong_location: bool = False
    exact_structure: bool = False
    summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number.to_dict(),
            "suffix": self.suffix.to_dict(),
            "street_type": self.street_type.to_dict(),
            "street_name": self.street_name.to_dict(),
            "postcode": self.postcode.to_dict(),
            "city": self.city.to_dict(),
            "strong_location": self.strong_location,
            "exact_structure": self.exact_structure,
            "summary": dict(self.summary),
        }


class AddressResolver:
    def __init__(self, geocoder, policy: Dict[str, Any]):
        self.geocoder = geocoder
        self.policy = policy

    def canonicalize(self, raw: str, use_locality_resolver: bool = False) -> CanonicalAddress:
        parsed = parse_address(raw, {})
        address = CanonicalAddress(
            raw=raw,
            normalized=parsed["norm"],
            number=parsed.get("numero", ""),
            number_end=parsed.get("numero_fin", ""),
            suffix=parsed.get("suffixe", ""),
            street_type=parsed.get("type_voie", ""),
            street_name=parsed.get("nom_voie", ""),
            postcode=parsed.get("code_postal", ""),
            city_input=parsed.get("ville_norm", ""),
            city_canonical=parsed.get("ville_norm", ""),
            city_source=parsed.get("ville_source", ""),
        )

        if (
            use_locality_resolver
            and self.geocoder.available()
            and address.postcode
            and address.city_input
        ):
            resolver_policy = self.policy.get("resolver", {})
            result = self.geocoder.resolve_locality(
                address.postcode,
                address.city_input,
                min_similarity=float(resolver_policy.get("city_auto_correct_min", 0.90)),
                ambiguity_margin=float(resolver_policy.get("city_ambiguity_margin", 0.03)),
                limit=int(resolver_policy.get("max_city_candidates", 100)),
            )
            address.locality_status = result.status
            address.locality_score = result.similarity
            if result.status in {"EXACT", "TYPO_CORRECTED"}:
                address.city_canonical = result.city_norm
                address.city_code = result.city_code
                address.city_source = "ban_locality"
            elif result.status == "AMBIGUOUS":
                address.city_source = "postal_segment_ambiguous"
        return address


class AddressComparator:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy

    @staticmethod
    def _simple(left: str, right: str, empty_equal: bool = False) -> FieldEvidence:
        if not left and not right:
            return FieldEvidence("EXACT" if empty_equal else "MISSING", left, right, 1.0 if empty_equal else None)
        if not left or not right:
            return FieldEvidence("UNKNOWN", left, right, None)
        if left == right:
            return FieldEvidence("EXACT", left, right, 1.0)
        return FieldEvidence("CONFLICT", left, right, 0.0)

    @staticmethod
    def _suffix(left: str, right: str) -> FieldEvidence:
        if left == right:
            return FieldEvidence("EXACT", left, right, 1.0)
        if not left or not right:
            return FieldEvidence("CONFLICT", left, right, 0.0, "suffix_missing_one")
        return FieldEvidence("CONFLICT", left, right, 0.0)

    @staticmethod
    def _number(a: CanonicalAddress, b: CanonicalAddress) -> FieldEvidence:
        left, right = a.number, b.number
        if not left and not right:
            return FieldEvidence("MISSING", left, right)
        if not left or not right:
            return FieldEvidence("UNKNOWN", left, right)

        left_end = a.number_end or left
        right_end = b.number_end or right
        left_label = f"{left}-{left_end}" if a.number_end else left
        right_label = f"{right}-{right_end}" if b.number_end else right
        if left == right and left_end == right_end:
            return FieldEvidence("EXACT", left_label, right_label, 1.0)

        try:
            left_start_i, left_end_i = int(left), int(left_end)
            right_start_i, right_end_i = int(right), int(right_end)
        except ValueError:
            return FieldEvidence("CONFLICT", left_label, right_label, 0.0)

        left_is_range = left_start_i != left_end_i
        right_is_range = right_start_i != right_end_i
        endpoint_match = (
            left_is_range
            and not right_is_range
            and right_start_i in {left_start_i, left_end_i}
        ) or (
            right_is_range
            and not left_is_range
            and left_start_i in {right_start_i, right_end_i}
        )
        if endpoint_match:
            return FieldEvidence(
                "NORMALIZED_EXACT",
                left_label,
                right_label,
                1.0,
                "range_endpoint_match",
            )

        inside_range = (
            left_is_range
            and not right_is_range
            and left_start_i < right_start_i < left_end_i
        ) or (
            right_is_range
            and not left_is_range
            and right_start_i < left_start_i < right_end_i
        )
        if inside_range:
            return FieldEvidence(
                "TYPO_LIKELY",
                left_label,
                right_label,
                0.5,
                "number_inside_range",
            )
        return FieldEvidence("CONFLICT", left_label, right_label, 0.0)

    @staticmethod
    def _street_core(value: str) -> str:
        particles = {"a", "au", "aux", "d", "de", "des", "du", "l", "la", "le", "les"}
        tokens = value.split()
        while tokens and tokens[0] in particles:
            tokens.pop(0)
        return " ".join(tokens) or value

    def _city(self, a: CanonicalAddress, b: CanonicalAddress) -> FieldEvidence:
        left, right = a.city, b.city
        if not left and not right:
            return FieldEvidence("MISSING", left, right)
        if not left or not right:
            return FieldEvidence("UNKNOWN", left, right)

        if left == right:
            normalized = (
                a.city_input != b.city_input
                or a.locality_status == "TYPO_CORRECTED"
                or b.locality_status == "TYPO_CORRECTED"
            )
            return FieldEvidence(
                "NORMALIZED_EXACT" if normalized else "EXACT",
                left,
                right,
                1.0,
                "locality_resolved" if normalized else "",
            )

        similarity = safe_ratio(left, right)
        conflict_below = float(self.policy["similarity"]["city_conflict_below"])
        if similarity < conflict_below:
            return FieldEvidence("CONFLICT", left, right, similarity)
        return FieldEvidence("TYPO_LIKELY", left, right, similarity)

    def _street(self, left: str, right: str) -> FieldEvidence:
        if not left and not right:
            return FieldEvidence("MISSING", left, right)
        if not left or not right:
            return FieldEvidence("UNKNOWN", left, right)
        if left == right:
            return FieldEvidence("EXACT", left, right, 1.0)

        if self._street_core(left) == self._street_core(right):
            return FieldEvidence(
                "NORMALIZED_EXACT",
                left,
                right,
                1.0,
                "optional_street_particles",
            )

        similarity = max(safe_token_set(left, right), safe_ratio(left, right))
        conflict_below = float(self.policy["similarity"]["street_conflict_below"])
        if similarity < conflict_below:
            return FieldEvidence("CONFLICT", left, right, similarity)
        return FieldEvidence("TYPO_LIKELY", left, right, similarity)

    def compare(self, a: CanonicalAddress, b: CanonicalAddress) -> AddressEvidence:
        number = self._number(a, b)
        suffix = self._suffix(a.suffix, b.suffix)
        street_type = self._simple(a.street_type, b.street_type)
        street_name = self._street(a.street_name, b.street_name)
        postcode = self._simple(a.postcode, b.postcode)
        city = self._city(a, b)

        exact_statuses = {"EXACT", "NORMALIZED_EXACT"}
        city_ok = city.status in {"EXACT", "NORMALIZED_EXACT", "TYPO_LIKELY"}
        strong_location = (
            postcode.status == "EXACT"
            and number.status in exact_statuses
            and city_ok
        )

        exact_structure = (
            bool(a.number and b.number)
            and bool(a.street_type and b.street_type)
            and bool(a.street_name and b.street_name)
            and bool(a.postcode and b.postcode)
            and bool(a.city and b.city)
            and number.status in exact_statuses
            and suffix.status in exact_statuses
            and street_type.status in exact_statuses
            and street_name.status in exact_statuses
            and postcode.status in exact_statuses
            and city.status in exact_statuses
        )

        items = [number, suffix, street_type, street_name, postcode, city]
        summary: Dict[str, int] = {}
        for item in items:
            summary[item.status] = summary.get(item.status, 0) + 1

        return AddressEvidence(
            number=number,
            suffix=suffix,
            street_type=street_type,
            street_name=street_name,
            postcode=postcode,
            city=city,
            strong_location=strong_location,
            exact_structure=exact_structure,
            summary=summary,
        )
