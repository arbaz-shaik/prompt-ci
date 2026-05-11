# prompt-ci

**Regression tests for your prompts. As a GitHub Action.**

Most teams running LLMs in production have zero automated regression testing on their prompts. Someone tweaks a system message to fix one case, silently breaks five others, and you find out when a customer complains.

This repo is the smallest viable thing that fixes that. About 200 lines of Python.

---

## What it does

When you open a PR that touches `prompts/` or `evals/`, the action:

1. Runs your eval set against the prompt on `main`
2. Runs the same eval set against the prompt on the PR branch
3. Diffs accuracy, cost, and p95 latency
4. Posts a sticky comment on the PR
5. Fails the build if accuracy drops more than your threshold

## Example PR comment

> ## prompt-ci eval results
>
> _Model: `gpt-4o-mini`_
>
> | Metric | main | this PR | Δ |
> |---|---|---|---|
> | Accuracy | 86.7% | 93.3% | +6.6pp ✅ |
> | Cost / call | $0.00021 | $0.00019 | -$0.00002 ✅ |
> | p95 latency | 1.84s | 1.91s | +0.07s ⚠️ |
> | Cases | 30 | 30 | |
>
> ### By category
>
> | Category | main | this PR |
> |---|---|---|
> | account | 5/6 | 6/6 ✅ |
> | billing | 7/8 | 8/8 ✅ |
> | feature_request | 5/5 | 5/5 |
> | other | 3/4 | 4/4 ✅ |
> | technical | 6/7 | 5/7 ⚠️ |
>
> ###  Quality improved

The point of the screenshot is the moment a teammate's "small wording tweak" PR shows a regression on the `technical` category and they catch it before merge — instead of in production.

## Why this and not [bigger eval platform]

There are real eval platforms — Braintrust, Promptfoo, Langsmith, Arize. They're great. They're also platforms: accounts, dashboards, datasets, teams.

This is the opposite of that. One workflow file, two scripts, your existing repo, your existing CI. No SaaS account. No new vendor. The minimum viable version of "prompts are code, treat them like code."

If you outgrow it, swap it for a real platform. If you don't, you don't.

## Quick start

```bash
git clone <this repo>
cd prompt-ci
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...   # or ANTHROPIC_API_KEY for Claude models
python scripts/run_evals.py prompts/classifier.txt evals/classifier.jsonl out.json
```

To wire it into a repo of your own:

1. Copy `scripts/`, `.github/workflows/prompt-ci.yml`, and `requirements.txt`
2. Put your prompts in `prompts/` (one file per prompt)
3. Put your eval cases in `evals/<name>.jsonl`
4. Add `OPENAI_API_KEY` (or your provider key) as a repo secret
5. Open a PR that changes a prompt — watch the comment land

## Eval format

Each line of the JSONL is one case. Two scoring modes:

**Exact match** (deterministic):
```json
{"id": "bill_01", "category": "billing", "input": "...", "expected": "billing"}
```

**Rubric** (LLM-as-judge — for cases without one right answer):
```json
{"id": "summary_01", "category": "summarisation", "input": "...", "rubric": "Output is under 50 words and mentions the deadline."}
```

Use exact-match wherever you can. Rubrics are slower, more expensive, and noisier.

## Customising

- **Model**: pass as the 4th arg to `run_evals.py` (`gpt-4o-mini`, `claude-3-5-haiku-latest`, etc — anything `litellm` supports)
- **Regression threshold**: 4th arg to `compare.py`, default `0.05` (5pp drop fails the build)
- **Multiple prompts**: extend the workflow with a matrix over prompt files, or run them sequentially in one job

## Honest limitations

Calling these out so nobody is surprised:

- **It costs API calls every PR.** A 30-case eval on `gpt-4o-mini` is fractions of a cent; a 500-case eval on a frontier model is real money. Size your eval set deliberately.
- **LLM-as-judge is noisy.** Rubric-graded cases will flap between PASS and FAIL on borderline outputs. Rely on exact-match when you can; sample-size your way out of judge noise when you can't.
- **It's not a dataset manager.** If you need versioned datasets, drift detection, or human review queues, you want a real platform.
- **Single threshold is blunt.** A 5pp accuracy drop in one category can be invisible in the global metric. Read the per-category table before merging.

## License

MIT. Use it, fork it, change the variable names, ship it.
