from __future__ import annotations

import argparse
import base64
from pathlib import Path


def reconstruct(output: Path, parts_dir: Path) -> Path:
    parts = sorted(parts_dir.glob("model.b64.part*"))
    if not parts:
        raise FileNotFoundError(f"Aucun fragment de modele dans {parts_dir}")
    payload = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(payload, validate=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruit le modele joblib depuis ses fragments Base64 versionnes")
    here = Path(__file__).resolve().parent
    parser.add_argument("--parts-dir", default=str(here / "model_parts"))
    parser.add_argument("--output", default=str(here / "modele_matching_adresses_v3.joblib"))
    args = parser.parse_args()
    path = reconstruct(Path(args.output), Path(args.parts_dir))
    print(f"Modele reconstruit: {path} ({path.stat().st_size} octets)")


if __name__ == "__main__":
    main()
