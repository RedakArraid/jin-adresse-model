from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

sys.path.insert(0, "/app")
try:
    from score_address_pair_v3 import normalize_text
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from score_address_pair_v3 import normalize_text

BASE_URL = "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv-with-ids"
ADDRESS_COLUMNS = (
    "id_ban", "numero", "rep", "nom_voie", "nom_voie_norm", "code_postal", "code_insee",
    "nom_commune", "nom_commune_norm", "lon", "lat", "label", "departement", "source_file",
)


def _schema(table: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id_ban TEXT PRIMARY KEY,
            numero TEXT,
            rep TEXT,
            nom_voie TEXT,
            nom_voie_norm TEXT,
            code_postal TEXT,
            code_insee TEXT,
            nom_commune TEXT,
            nom_commune_norm TEXT,
            lon REAL,
            lat REAL,
            label TEXT,
            departement TEXT,
            source_file TEXT
        )
    """


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=FILE")
    con.execute(_schema("ban_addresses"))
    con.execute(_schema("ban_staging"))
    con.execute("CREATE INDEX IF NOT EXISTS idx_ban_cp_num ON ban_addresses(code_postal, numero)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ban_city_num ON ban_addresses(nom_commune_norm, numero)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ban_cp_street ON ban_addresses(code_postal, nom_voie_norm)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ban_city_street ON ban_addresses(nom_commune_norm, nom_voie_norm)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ban_dep ON ban_addresses(departement)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_staging_dep ON ban_staging(departement)")
    con.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
    con.commit()
    return con


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Telechargement: {url}")
    with requests.get(url, stream=True, timeout=(15, 120)) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with tmp.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
    print(f"Fichier: {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")


def open_csv(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def detect_reader(path: Path):
    fh = open_csv(path)
    sample = fh.read(8192)
    fh.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(fh, delimiter=delimiter)
    fields = {str(x).strip().lower() for x in (reader.fieldnames or [])}
    required_groups = [
        {"nom_voie", "voie"},
        {"code_postal", "postcode"},
        {"nom_commune", "commune", "city"},
    ]
    missing = [sorted(g) for g in required_groups if not (fields & g)]
    if missing:
        fh.close()
        raise ValueError(f"CSV BAN invalide: colonnes obligatoires absentes: {missing}")
    return fh, reader


def pick(row: Dict[str, str], *names: str) -> str:
    lowered = {str(k).strip().lower(): (v or "") for k, v in row.items()}
    for name in names:
        if name.lower() in lowered:
            return str(lowered[name.lower()]).strip()
    return ""


def normalize_rep(rep: str) -> str:
    value = normalize_text(rep or "").strip()
    return {"b": "bis", "t": "ter", "q": "quater"}.get(value, value)


def row_to_tuple(row: Dict[str, str], dep: str, source_file: str):
    id_ban = pick(row, "id_ban", "id")
    numero = pick(row, "numero")
    rep = normalize_rep(pick(row, "rep", "suffixe"))
    nom_voie = pick(row, "nom_voie", "voie")
    cp = pick(row, "code_postal", "postcode")
    insee = pick(row, "code_insee", "citycode")
    commune = pick(row, "nom_commune", "commune", "city")
    lon = pick(row, "lon", "longitude")
    lat = pick(row, "lat", "latitude")
    if not nom_voie or not cp or not commune:
        raise ValueError("Ligne BAN invalide: voie, code postal ou commune manquant")
    if not id_ban:
        id_ban = f"{insee}-{normalize_text(nom_voie)}-{numero}-{rep}-{cp}"
    label = " ".join(x for x in [numero + ((" " + rep) if rep else ""), nom_voie, cp, commune] if x).strip()
    try:
        lon_v = float(lon.replace(",", ".")) if lon else None
    except ValueError:
        lon_v = None
    try:
        lat_v = float(lat.replace(",", ".")) if lat else None
    except ValueError:
        lat_v = None
    return (
        id_ban, numero, rep, nom_voie, normalize_text(nom_voie), cp, insee, commune,
        normalize_text(commune), lon_v, lat_v, label, dep, source_file,
    )


def stage_file(
    con: sqlite3.Connection,
    path: Path,
    dep: str,
    batch_size: int = 20000,
    fail_after: Optional[int] = None,
) -> int:
    con.execute("DELETE FROM ban_staging WHERE departement = ?", (dep,))
    con.commit()

    fh, reader = detect_reader(path)
    sql = f"INSERT OR REPLACE INTO ban_staging ({','.join(ADDRESS_COLUMNS)}) VALUES ({','.join('?' for _ in ADDRESS_COLUMNS)})"
    total = 0
    batch: List[tuple] = []
    try:
        for row in reader:
            batch.append(row_to_tuple(row, dep, path.name))
            if fail_after is not None and total + len(batch) >= fail_after:
                raise RuntimeError("Interruption d'import simulee")
            if len(batch) >= batch_size:
                con.executemany(sql, batch)
                con.commit()
                total += len(batch)
                print(f"  {total:,} lignes chargees en staging".replace(",", " "))
                batch.clear()
        if batch:
            con.executemany(sql, batch)
            con.commit()
            total += len(batch)
    finally:
        fh.close()

    staged = int(con.execute("SELECT COUNT(*) FROM ban_staging WHERE departement = ?", (dep,)).fetchone()[0])
    if total <= 0 or staged != total:
        raise RuntimeError(f"Validation staging echouee: attendu={total}, trouve={staged}")
    print(f"Staging valide: {total:,} lignes".replace(",", " "))
    return total


def refresh_metadata(con: sqlite3.Connection) -> None:
    rows = int(con.execute("SELECT COUNT(*) FROM ban_addresses").fetchone()[0])
    deps = [r[0] for r in con.execute("SELECT DISTINCT departement FROM ban_addresses WHERE departement <> '' ORDER BY departement").fetchall()]
    now = datetime.now(timezone.utc).isoformat()
    con.executemany(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
        [
            ("rows_total", str(rows)),
            ("departments_json", json.dumps(deps)),
            ("last_update", now),
        ],
    )


def publish_staged_department(con: sqlite3.Connection, dep: str, expected_rows: int) -> None:
    staged = int(con.execute("SELECT COUNT(*) FROM ban_staging WHERE departement = ?", (dep,)).fetchone()[0])
    if staged != expected_rows or staged <= 0:
        raise RuntimeError(f"Publication refusee: staging incomplet pour {dep} ({staged}/{expected_rows})")

    cols = ",".join(ADDRESS_COLUMNS)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM ban_addresses WHERE departement = ?", (dep,))
        con.execute(f"INSERT OR REPLACE INTO ban_addresses ({cols}) SELECT {cols} FROM ban_staging WHERE departement = ?", (dep,))
        live = int(con.execute("SELECT COUNT(*) FROM ban_addresses WHERE departement = ?", (dep,)).fetchone()[0])
        if live != expected_rows:
            raise RuntimeError(f"Publication incomplete pour {dep}: {live}/{expected_rows}")
        con.execute("DELETE FROM ban_staging WHERE departement = ?", (dep,))
        con.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
            (f"department_{dep}_loaded_at", datetime.now(timezone.utc).isoformat()),
        )
        refresh_metadata(con)
        con.commit()
    except Exception:
        con.rollback()
        raise


def import_department_atomic(con: sqlite3.Connection, path: Path, dep: str, fail_after: Optional[int] = None) -> int:
    try:
        count = stage_file(con, path, dep, fail_after=fail_after)
        publish_staged_department(con, dep, count)
        print(f"Import atomique termine: {dep} | {count:,} lignes".replace(",", " "))
        return count
    except Exception:
        con.execute("DELETE FROM ban_staging WHERE departement = ?", (dep,))
        con.commit()
        raise


def _dep_from_filename(path: Path) -> str:
    name = path.name
    for suffix in (".csv.gz", ".csv"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    if "adresses-with-ids-" in name:
        return name.rsplit("adresses-with-ids-", 1)[1].upper()
    return "LOCAL"


def main() -> None:
    p = argparse.ArgumentParser(description="Telecharge et indexe la BAN localement dans SQLite")
    p.add_argument("--departments", nargs="+", default=[], help="Ex: 13 75 69 2A")
    p.add_argument("--db", default=os.environ.get("BAN_DB_PATH", "/data/ban/ban.sqlite"))
    p.add_argument("--raw-dir", default="/data/ban/raw")
    p.add_argument("--from-file", action="append", default=[], help="Importer un CSV/CSV.GZ local au lieu de telecharger")
    p.add_argument("--keep-raw", action="store_true")
    args = p.parse_args()

    if not args.departments and not args.from_file:
        p.error("Indique --departments ou --from-file")

    db_path = Path(args.db)
    raw_dir = Path(args.raw_dir)
    con = init_db(db_path)
    try:
        for dep in args.departments:
            dep = dep.upper().strip()
            filename = f"adresses-with-ids-{dep}.csv.gz"
            path = raw_dir / filename
            url = f"{BASE_URL}/{filename}"
            download(url, path)
            import_department_atomic(con, path, dep)
            if not args.keep_raw:
                path.unlink(missing_ok=True)

        for spec in args.from_file:
            path = Path(spec)
            if not path.exists():
                raise FileNotFoundError(path)
            dep = _dep_from_filename(path)
            import_department_atomic(con, path, dep)

        stats = dict(con.execute("SELECT key, value FROM metadata").fetchall())
        print(f"BAN locale prete: {db_path} | {stats.get('rows_total', '0')} adresses")
    finally:
        con.close()


if __name__ == "__main__":
    main()
