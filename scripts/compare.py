"""
Compare two run_evals result files and emit a markdown PR comment.

Exits 1 if accuracy regresses by more than `threshold` (default 0.05).

Usage:
    python scripts/compare.py <main_results> <pr_results> <output_md> [threshold]
"""
import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def render(main: dict, pr: dict, threshold: float) -> tuple[str, int]:
    m = main["summary"]
    p = pr["summary"]

    acc_delta  = p["accuracy"] - m["accuracy"]
    cost_delta = p["avg_cost_per_call"] - m["avg_cost_per_call"]
    lat_delta  = p["p95_latency"] - m["p95_latency"]

    def marker(delta: float, good_higher: bool, eps: float) -> str:
        if abs(delta) < eps:
            return "`[--]`"
        return "`[OK]`" if (delta > 0) == good_higher else "`[WARN]`"

    md = []
    md.append("## prompt-ci eval results\n")
    md.append(f"_Model: `{pr.get('model', 'unknown')}`_\n")
    md.append("| Metric | main | this PR | Delta | |")
    md.append("|---|---|---|---|---|")
    md.append(
        f"| Accuracy | {m['accuracy']:.1%} | {p['accuracy']:.1%} | "
        f"{acc_delta*100:+.1f}pp | {marker(acc_delta, True, 0.005)} |"
    )
    sign = "+" if cost_delta >= 0 else "-"
    md.append(
        f"| Cost / call | ${m['avg_cost_per_call']:.5f} | ${p['avg_cost_per_call']:.5f} | "
        f"{sign}${abs(cost_delta):.5f} | {marker(cost_delta, False, 1e-6)} |"
    )
    md.append(
        f"| p95 latency | {m['p95_latency']:.2f}s | {p['p95_latency']:.2f}s | "
        f"{lat_delta:+.2f}s | {marker(lat_delta, False, 0.05)} |"
    )
    md.append(f"| Cases | {m['total']} | {p['total']} | | |")
    md.append("")

    # Per-category
    md.append("### By category\n")
    md.append("| Category | main | this PR | |")
    md.append("|---|---|---|---|")
    cats = sorted(set(m["by_category"]) | set(p["by_category"]))
    for cat in cats:
        mc = m["by_category"].get(cat, {"passed": 0, "total": 0})
        pc = p["by_category"].get(cat, {"passed": 0, "total": 0})
        m_str = f"{mc['passed']}/{mc['total']}"
        p_str = f"{pc['passed']}/{pc['total']}"
        if mc["total"] and pc["total"]:
            m_acc = mc["passed"] / mc["total"]
            p_acc = pc["passed"] / pc["total"]
            mark = "`[WARN]`" if p_acc < m_acc else ("`[OK]`" if p_acc > m_acc else "")
        else:
            mark = ""
        md.append(f"| {cat} | {m_str} | {p_str} | {mark} |")
    md.append("")

    # Failing cases
    if p["failures"]:
        md.append(f"<details><summary>{len(p['failures'])} failing case(s) on this PR</summary>\n")
        for f in p["failures"][:20]:
            inp = f["input"].replace("\n", " ")[:100]
            out = f["output"].replace("\n", " ")[:80]
            md.append(f"- **`{f['id']}`** _({f['category']})_")
            md.append(f"  - input: `{inp}`")
            md.append(f"  - got:   `{out}`")
        if len(p["failures"]) > 20:
            md.append(f"- _... and {len(p['failures']) - 20} more_")
        md.append("\n</details>\n")

    # Verdict
    if acc_delta < -threshold:
        md.append("### [FAIL] Regression detected")
        md.append(
            f"Accuracy dropped by **{abs(acc_delta)*100:.1f}pp**, "
            f"exceeding threshold of {threshold*100:.0f}pp. Build failed."
        )
        return "\n".join(md), 1

    if acc_delta > 0.005:
        md.append("### [PASS] Quality improved")
    else:
        md.append("### [PASS] No regression")
    return "\n".join(md), 0


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)

    main_path = sys.argv[1]
    pr_path   = sys.argv[2]
    out_path  = sys.argv[3]
    threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.05

    md, exit_code = render(load(main_path), load(pr_path), threshold)
    Path(out_path).write_text(md)
    print(md)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()