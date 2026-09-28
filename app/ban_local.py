from __future__ import annotations

import json
import math
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from score_address_pair_v3 import normalize_text


def _norm_suffix(value: str) -> str:
    v = normalize_text(value or "").strip()
    return {"b": "bis", "t": "ter", "q": "quater"}.get(v, v)


def _haversine_m(lat1, lon1, lat2, lon2) -> Optional[float]:
    if any(v is None for v in (lat1, lon1, lat2, lon2)):
        return None
    r = 6371000.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _street_anchor(street: str) -> str:
    ignore = {"de", "du", "des", "la", "le", "les", "aux", "au", "d"}
    tokens = [t for t in normalize_text(street).split() if t not in ignore]
    if not tokens:
        tokens = normalize_text(street).split()
    return max(tokens, key=len) if tokens else ""


@dataclass
class LocalBanResult:
    query: str
    database_status: str = "UNAVAILABLE"
    existence_status: str = "UNAVAILABLE"
    quality_score: float = 0.0
    id_ban: str = ""
    label: str = ""
    numero: str = ""
    suffixe: str = ""
    nom_voie: str = ""
    code_postal: str = ""
    code_insee: str = ""
    nom_commune: str = ""
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    candidate_count: int = 0
    street_similarity: float = 0.0
    number_match: Optional[bool] = None
    suffix_match: Optional[bool] = None
    postcode_match: Optional[bool] = None
    city_similarity: float = 0.0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LocalBANGeocoder:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or os.environ.get("BAN_DB_PATH", "/data/ban/ban.sqlite"))
        self._signature_cache: Optional[Tuple[int, int]] = None
        self._available_cache: Optional[bool] = None
        self._stats_cache: Optional[Dict[str, Any]] = None

    def _signature(self) -> Optional[Tuple[int, int]]:
        try:
            stat = self.db_path.stat()
            return stat.st_size, stat.st_mtime_ns
        except OSError:
            return None

    def _refresh_cache_if_changed(self) -> None:
        sig = self._signature()
        if sig != self._signature_cache:
            self._signature_cache = sig
            self._available_cache = None
            self._stats_cache = None

    def available(self) -> bool:
        self._refresh_cache_if_changed()
        if self._available_cache is not None:
            return self._available_cache
        if self._signature_cache is None or self._signature_cache[0] < 1024:
            self._available_cache = False
            return False
        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=3) as con:
                row = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ban_addresses'").fetchone()
                self._available_cache = bool(row)
        except sqlite3.Error:
            self._available_cache = False
        return self._available_cache

    def stats(self) -> Dict[str, Any]:
        self._refresh_cache_if_changed()
        if self._stats_cache is not None:
            return dict(self._stats_cache)
        if not self.available():
            self._stats_cache = {"available": False, "path": str(self.db_path), "rows": 0, "departments": []}
            return dict(self._stats_cache)
        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5) as con:
                has_meta = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'").fetchone()
                meta = dict(con.execute("SELECT key, value FROM metadata").fetchall()) if has_meta else {}
                if "rows_total" in meta:
                    rows = int(meta["rows_total"])
                else:
                    rows = int(con.execute("SELECT COUNT(*) FROM ban_addresses").fetchone()[0])
                if "departments_json" in meta:
                    deps = json.loads(meta["departments_json"])
                else:
                    deps = [r[0] for r in con.execute("SELECT DISTINCT departement FROM ban_addresses ORDER BY departement").fetchall() if r[0]]
            self._stats_cache = {"available": True, "path": str(self.db_path), "rows": rows, "departments": deps, "metadata": meta}
        except (sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
            self._stats_cache = {"available": False, "path": str(self.db_path), "rows": 0, "departments": [], "error": str(exc)}
        return dict(self._stats_cache)

    def _candidate_rows(self, con: sqlite3.Connection, cp: str, numero: str, ville: str, street: str, limit: int) -> List[sqlite3.Row]:
        columns = "id_ban, numero, rep, nom_voie, nom_voie_norm, code_postal, code_insee, nom_commune, nom_commune_norm, lon, lat, label"
        anchor = _street_anchor(street)

        if cp and numero:
            return con.execute(
                f"SELECT {columns} FROM ban_addresses WHERE code_postal = ? AND numero = ? ORDER BY nom_voie_norm, rep LIMIT ?",
                (cp, numero, limit),
            ).fetchall()

        if cp and street:
            rows = con.execute(
                f"SELECT {columns} FROM ban_addresses WHERE code_postal = ? AND (nom_voie_norm = ? OR nom_voie_norm LIKE ?) "
                "ORDER BY CASE WHEN nom_voie_norm = ? THEN 0 ELSE 1 END, nom_voie_norm LIMIT ?",
                (cp, street, street + "%", street, limit),
            ).fetchall()
            if rows:
                return rows
            if anchor:
                return con.execute(
                    f"SELECT {columns} FROM ban_addresses WHERE code_postal = ? AND instr(nom_voie_norm, ?) > 0 "
                    "ORDER BY ABS(LENGTH(nom_voie_norm) - ?), nom_voie_norm LIMIT ?",
                    (cp, anchor, len(street), limit),
                ).fetchall()

        if ville and numero:
            return con.execute(
                f"SELECT {columns} FROM ban_addresses WHERE nom_commune_norm = ? AND numero = ? ORDER BY nom_voie_norm, rep LIMIT ?",
                (ville, numero, limit),
            ).fetchall()

        if ville and street:
            rows = con.execute(
                f"SELECT {columns} FROM ban_addresses WHERE nom_commune_norm = ? AND (nom_voie_norm = ? OR nom_voie_norm LIKE ?) "
                "ORDER BY CASE WHEN nom_voie_norm = ? THEN 0 ELSE 1 END, nom_voie_norm LIMIT ?",
                (ville, street, street + "%", street, limit),
            ).fetchall()
            if rows:
                return rows
            if anchor:
                return con.execute(
                    f"SELECT {columns} FROM ban_addresses WHERE nom_commune_norm = ? AND instr(nom_voie_norm, ?) > 0 "
                    "ORDER BY ABS(LENGTH(nom_voie_norm) - ?), nom_voie_norm LIMIT ?",
                    (ville, anchor, len(street), limit),
                ).fetchall()
        return []

    def lookup(self, query: str, parsed: Dict[str, str], limit: int = 250) -> LocalBanResult:
        if not self.available():
            return LocalBanResult(query=query, error="BAN locale non importee")

        numero = str(parsed.get("numero") or "").strip()
        suffixe = _norm_suffix(parsed.get("suffixe") or "")
        cp = str(parsed.get("code_postal") or "").strip()
        ville = normalize_text(parsed.get("ville_norm") or "")
        street = normalize_text(parsed.get("nom_voie") or "")

        if not ((cp or ville) and (numero or street)):
            return LocalBanResult(
                query=query,
                database_status="OK",
                existence_status="INSUFFICIENT_QUERY",
                error="Code postal/commune et numero/voie insuffisants pour une recherche locale bornee",
            )

        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5) as con:
                con.row_factory = sqlite3.Row
                rows = self._candidate_rows(con, cp, numero, ville, street, int(limit))
        except sqlite3.Error as exc:
            return LocalBanResult(query=query, database_status="ERROR", existence_status="UNAVAILABLE", error=str(exc))

        if not rows:
            return LocalBanResult(query=query, database_status="OK", existence_status="NOT_FOUND", candidate_count=0)

        ranked = []
        for row in rows:
            rstreet = row["nom_voie_norm"] or normalize_text(row["nom_voie"] or "")
            rcity = row["nom_commune_norm"] or normalize_text(row["nom_commune"] or "")
            rrep = _norm_suffix(row["rep"] or "")
            street_sim = fuzz.token_set_ratio(street, rstreet) / 100.0 if street and rstreet else 0.5
            city_sim = fuzz.ratio(ville, rcity) / 100.0 if ville and rcity else 0.5
            number_match = bool(numero and str(row["numero"] or "") == numero) if numero else None
            suffix_match = (suffixe == rrep) if numero else None
            cp_match = bool(cp and str(row["code_postal"] or "") == cp) if cp else None
            label_sim = fuzz.token_set_ratio(normalize_text(query), normalize_text(row["label"] or "")) / 100.0
            number_score = 1.0 if number_match is True else (0.5 if number_match is None else 0.0)
            suffix_score = 1.0 if suffix_match is True else (0.5 if suffix_match is None else 0.0)
            cp_score = 1.0 if cp_match is True else (0.5 if cp_match is None else 0.0)
            quality = (
                0.43 * street_sim
                + 0.17 * label_sim
                + 0.14 * number_score
                + 0.10 * suffix_score
                + 0.08 * cp_score
                + 0.08 * city_sim
            )
            ranked.append((quality, street_sim, city_sim, number_match, suffix_match, cp_match, row))

        ranked.sort(key=lambda x: (-x[0], str(x[-1]["id_ban"] or "")))
        quality, street_sim, city_sim, number_match, suffix_match, cp_match, row = ranked[0]

        if numero:
            if number_match and suffix_match and cp_match is not False and street_sim >= 0.80 and quality >= 0.76:
                status = "CONFIRMED_HOUSENUMBER"
            elif number_match and street_sim >= 0.72 and quality >= 0.64:
                status = "PLAUSIBLE_HOUSENUMBER"
            else:
                status = "WEAK"
        else:
            status = "CONFIRMED_STREET" if street_sim >= 0.90 and quality >= 0.72 else "PLAUSIBLE_STREET"

        return LocalBanResult(
            query=query,
            database_status="OK",
            existence_status=status,
            quality_score=round(float(quality), 6),
            id_ban=str(row["id_ban"] or ""),
            label=str(row["label"] or ""),
            numero=str(row["numero"] or ""),
            suffixe=str(row["rep"] or ""),
            nom_voie=str(row["nom_voie"] or ""),
            code_postal=str(row["code_postal"] or ""),
            code_insee=str(row["code_insee"] or ""),
            nom_commune=str(row["nom_commune"] or ""),
            longitude=float(row["lon"]) if row["lon"] is not None else None,
            latitude=float(row["lat"]) if row["lat"] is not None else None,
            candidate_count=len(rows),
            street_similarity=round(float(street_sim), 6),
            number_match=number_match,
            suffix_match=suffix_match,
            postcode_match=cp_match,
            city_similarity=round(float(city_sim), 6),
        )


def official_pair_features(a: LocalBanResult, b: LocalBanResult) -> Dict[str, Any]:
    usable_a = a.database_status == "OK" and a.existence_status not in {"NOT_FOUND", "UNAVAILABLE", "INSUFFICIENT_QUERY"}
    usable_b = b.database_status == "OK" and b.existence_status not in {"NOT_FOUND", "UNAVAILABLE", "INSUFFICIENT_QUERY"}
    street_sim = fuzz.token_set_ratio(normalize_text(a.nom_voie), normalize_text(b.nom_voie)) / 100.0 if a.nom_voie and b.nom_voie else 0.0
    city_sim = fuzz.ratio(normalize_text(a.nom_commune), normalize_text(b.nom_commune)) / 100.0 if a.nom_commune and b.nom_commune else 0.0
    dist = _haversine_m(a.latitude, a.longitude, b.latitude, b.longitude)
    same_id = bool(a.id_ban and b.id_ban and a.id_ban == b.id_ban)
    num_same = bool(a.numero and b.numero and a.numero == b.numero)
    suffix_same = _norm_suffix(a.suffixe) == _norm_suffix(b.suffixe) if a.numero and b.numero else False
    cp_same = bool(a.code_postal and b.code_postal and a.code_postal == b.code_postal)
    city_same = bool(a.code_insee and b.code_insee and a.code_insee == b.code_insee) or city_sim >= 0.98
    distance_score = 0.0 if dist is None else math.exp(-dist / 30.0)
    quality = min(a.quality_score, b.quality_score) if usable_a and usable_b else 0.0
    pair = (
        0.24 * street_sim
        + 0.17 * float(num_same)
        + 0.12 * float(suffix_same)
        + 0.12 * float(cp_same)
        + 0.10 * float(city_same)
        + 0.13 * distance_score
        + 0.12 * quality
    )
    if same_id:
        pair = 1.0
    return {
        "usable_both": bool(usable_a and usable_b),
        "same_official_id": same_id,
        "official_street_similarity": round(street_sim, 6),
        "official_number_same": num_same,
        "official_suffix_same": suffix_same,
        "official_postcode_same": cp_same,
        "official_city_same": city_same,
        "official_distance_m": None if dist is None else round(dist, 3),
        "official_pair_score": round(min(max(pair, 0.0), 1.0), 6),
    }
