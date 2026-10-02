from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "fictional_address_cases.json"
sys.path.insert(0, str(APP))

from matcher import AddressMatcher


def check_case(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    decision = result["decision"]
    score = float(result["score_final"])
    expected = case["expected_decisions"]
    if decision not in expected:
        errors.append(f"decision={decision}, attendu={expected}")
    if "min_score" in case and score < float(case["min_score"]):
        errors.append(f"score={score:.2f} < min={float(case['min_score']):.2f}")
    if "max_score" in case and score > float(case["max_score"]):
        errors.append(f"score={score:.2f} > max={float(case['max_score']):.2f}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalue le modele sur un corpus fictif d'adresses")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--strict", action="store_true", help="Retourne un code non nul si un cas echoue")
    parser.add_argument("--show-success", action="store_true", help="Affiche aussi les cas conformes")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    matcher = AddressMatcher(APP / "model_config.json", ROOT / "data" / "ban" / "benchmark-no-ban.sqlite")
    failures: list[tuple[dict[str, Any], dict[str, Any], list[str]]] = []
    decisions: Counter[str] = Counter()

    for case in cases:
        result = matcher.score(case["address_a"], case["address_b"], use_ban=False)
        decisions[result["decision"]] += 1
        errors = check_case(case, result)
        status = "ECHEC" if errors else "OK"
        if errors:
            failures.append((case, result, errors))
        if errors or args.show_success:
            print(
                f"[{status}] {case['id']}: {result['score_final']:.2f} "
                f"{result['decision']} ({result['decision_reason']})"
            )
            for error in errors:
                print(f"  - {error}")

    print()
    print(f"Cas: {len(cases)} | conformes: {len(cases) - len(failures)} | echecs: {len(failures)}")
    print("Decisions: " + ", ".join(f"{key}={value}" for key, value in sorted(decisions.items())))

    if failures:
        print("\nCas a examiner:")
        for case, result, _ in failures:
            print(f"- {case['id']} [{case['category']}]: {case['rationale']}")
            print(f"  A: {case['address_a']}")
            print(f"  B: {case['address_b']}")
            print(f"  parse A: {result['parsed_A']}")
            print(f"  parse B: {result['parsed_B']}")

    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
