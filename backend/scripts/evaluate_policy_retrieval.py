import json
from pathlib import Path

from app.policies import search_policy


def evaluate() -> int:
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/policy_retrieval_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    correct = 0
    failures: list[str] = []
    for case in cases:
        results = search_policy(case["query"])
        top = results[0] if results else None
        passed = bool(
            top
            and top.policy_type == case["policy_type"]
            and top.section_title in case["sections"]
        )
        if passed:
            correct += 1
        else:
            failures.append(
                f"- {case['query']!r}: got "
                f"{(top.policy_type, top.section_title) if top else None!r}"
            )
    print(f"Policy retrieval cases: {len(cases)}")
    print(f"Top-1 correct: {correct}")
    print(f"Accuracy: {correct / len(cases):.2f}")
    if failures:
        print("Failures:")
        print("\n".join(failures))
    return 0 if not failures else 1


def main() -> None:
    raise SystemExit(evaluate())


if __name__ == "__main__":
    main()
