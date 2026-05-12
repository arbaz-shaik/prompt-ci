"""
Run an eval set against a prompt and write JSON results.

Usage:
    python scripts/run_evals.py <prompt_path> <evals_path> <output_path> [model]
"""
import json
import sys
import time
from pathlib import Path

import litellm

# Rough $/1M tokens. Add your own as needed.
COST_RATES = {
    "groq/llama-3.3-70b-versatile": (0.59, 0.79),
    "groq/llama-3.1-8b-instant":    (0.05, 0.08),
    "gpt-4o-mini":                  (0.15, 0.60),
    "gpt-4o":                       (2.50, 10.00),
    "claude-3-5-haiku-latest":      (0.80, 4.00),
    "claude-3-5-sonnet-latest":     (3.00, 15.00),
}


def load_prompt(path: str) -> str:
    return Path(path).read_text().strip()


def load_evals(path: str) -> list[dict]:
    cases = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def run_case(prompt: str, case: dict, model: str) -> tuple[str, float, float]:
    start = time.time()
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": case["input"]},
        ],
        temperature=0,
        num_retries=5,
    )
    latency = time.time() - start
    output = response.choices[0].message.content or ""
    cost = estimate_cost(response.usage, model)
    return output, latency, cost


def estimate_cost(usage, model: str) -> float:
    in_rate, out_rate = COST_RATES.get(model, (1.0, 1.0))
    return (usage.prompt_tokens * in_rate + usage.completion_tokens * out_rate) / 1_000_000


def score_exact(output: str, expected: str) -> bool:
    return output.strip().lower() == expected.strip().lower()


def score_rubric(output: str, rubric: str, judge_model: str) -> bool:
    judge_prompt = (
        "You are an evaluator. Judge whether the output satisfies the rubric.\n\n"
        f"Rubric: {rubric}\n\n"
        f"Output: {output}\n\n"
        "Reply with exactly one word: PASS or FAIL."
    )
    response = litellm.completion(
        model=judge_model,
        messages=[{"role": "user", "content": judge_prompt}],
        temperature=0,
        num_retries=5,
    )
    verdict = (response.choices[0].message.content or "").strip().upper()
    return verdict.startswith("PASS")


def run_evals(prompt_path: str, evals_path: str, model: str) -> list[dict]:
    prompt = load_prompt(prompt_path)
    cases = load_evals(evals_path)

    results = []
    for i, case in enumerate(cases):
        if i > 0:
            time.sleep(2.1)  # stay under Groq free tier 30 RPM
        output, latency, cost = run_case(prompt, case, model)
        if "expected" in case:
            passed = score_exact(output, case["expected"])
        elif "rubric" in case:
            passed = score_rubric(output, case["rubric"], model)
        else:
            raise ValueError(f"Case {case.get('id')} has neither 'expected' nor 'rubric'")

        results.append({
            "id":       case.get("id"),
            "category": case.get("category", "default"),
            "input":    case["input"],
            "output":   output,
            "passed":   passed,
            "latency":  latency,
            "cost":     cost,
        })
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {case.get('id', '?'):20s}  ({latency:.2f}s)")
    return results


def summarize(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    accuracy = passed / total if total else 0.0
    total_cost = sum(r["cost"] for r in results)
    avg_cost = total_cost / total if total else 0.0
    latencies = sorted(r["latency"] for r in results)
    p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)] if latencies else 0.0

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        bucket = by_category.setdefault(cat, {"total": 0, "passed": 0})
        bucket["total"] += 1
        if r["passed"]:
            bucket["passed"] += 1

    failures = [
        {"id": r["id"], "category": r["category"], "input": r["input"], "output": r["output"]}
        for r in results if not r["passed"]
    ]

    return {
        "accuracy":          accuracy,
        "total":             total,
        "passed":            passed,
        "avg_cost_per_call": avg_cost,
        "total_cost":        total_cost,
        "p95_latency":       p95,
        "by_category":       by_category,
        "failures":          failures,
    }


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)

    prompt_path = sys.argv[1]
    evals_path  = sys.argv[2]
    output_path = sys.argv[3]
    model       = sys.argv[4] if len(sys.argv) > 4 else "groq/llama-3.3-70b-versatile"

    print(f"Running evals: prompt={prompt_path}  evals={evals_path}  model={model}")
    results = run_evals(prompt_path, evals_path, model)
    summary = summarize(results)

    Path(output_path).write_text(json.dumps(
        {"model": model, "results": results, "summary": summary},
        indent=2,
    ))

    print()
    print(f"Accuracy:    {summary['accuracy']:.1%}  ({summary['passed']}/{summary['total']})")
    print(f"Total cost:  ${summary['total_cost']:.4f}")
    print(f"p95 latency: {summary['p95_latency']:.2f}s")


if __name__ == "__main__":
    main()