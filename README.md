# prompt-ci

**Regression tests for your prompts. As a GitHub Action.**

Most teams running LLMs in production have zero automated regression testing on their prompts. Someone tweaks a system message to fix one case, silently breaks five others, and you find out when a customer complains.

This repo is the smallest viable thing that fixes that. Around 280 lines of Python, one workflow file, no new SaaS.

---

## What it does

When you open a PR that touches `prompts/` or `evals/`, the action:

1. Runs your eval set against the prompt on `main`
2. Runs the same eval set against the prompt on the PR branch
3. Diffs accuracy, cost, and p95 latency
4. Posts a sticky comment on the PR with the results
5. Fails the build if accuracy drops more than your threshold

## Example PR comment

> ## prompt-ci eval results
>
> _Model: `groq/llama-3.3-70b-versatile`_
>
> | Metric | main | this PR | Delta | |
> |---|---|---|---|---|
> | Accuracy | 100.0% | 0.0% | -100.0pp | `[WARN]` |
> | Cost / call | $0.00010 | $0.00014 | +$0.00005 | `[WARN]` |
> | p95 latency | 0.22s | 0.84s | +0.62s | `[WARN]` |
> | Cases | 30 | 30 | | |
>
> ### By category
>
> | Category | main | this PR | |
> |---|---|---|---|
> | account | 6/6 | 0/6 | `[WARN]` |
> | billing | 8/8 | 0/8 | `[WARN]` |
> | feature_request | 5/5 | 0/5 | `[WARN]` |
> | other | 4/4 | 0/4 | `[WARN]` |
> | technical | 7/7 | 0/7 | `[WARN]` |
>
> ### [FAIL] Regression detected
> Accuracy dropped by **100.0pp**, exceeding threshold of 5pp. Build failed.

The whole point: the moment a teammate's "harmless wording tweak" PR breaks 30 out of 30 cases and the bot catches it before merge. Not in production. Not at 2am from a customer complaint.

See PR #2 in this repo for a real example of a deliberate regression being caught.

## Why this and not a bigger eval platform

There are real eval platforms — Braintrust, Promptfoo, Langsmith, Arize. They're great. They're also platforms: accounts, dashboards, datasets, teams.

This is the opposite of that. One workflow file, two scripts, your existing repo, your existing CI. No SaaS account. No new vendor. The minimum viable version of "prompts are code, treat them like code."

If you outgrow it, swap it for a real platform. If you don't, you don't.

## Quick start

This repo uses **Groq** by default because it has a generous free tier (no credit card, 14,400 requests/day on Llama 3.3 70B). You can swap in any model litellm supports.

### 1. Get a Groq API key

Sign up at https://console.groq.com (Google or GitHub auth, no card needed). Create an API key from the Keys page. It starts with `gsk_`.

### 2. Clone and install

```bash
git clone https://github.com/arbaz-shaik/prompt-ci.git
cd prompt-ci
python -m venv .venv
.venv\Scripts\activate   # on Windows
# or: source .venv/bin/activate   on Mac/Linux
pip install -r requirements.txt
```

### 3. Run an eval locally

```bash
# Windows PowerShell
$env:GROQ_API_KEY = "gsk_your_key"

# Mac/Linux
export GROQ_API_KEY=gsk_your_key

python scripts/run_evals.py prompts/classifier.txt evals/classifier.jsonl results.json
```

You should see 30 cases evaluated, hitting 100% accuracy.

### 4. Wire it into your own repo

1. Copy `scripts/`, `.github/workflows/prompt-ci.yml`, and `requirements.txt`
2. Put your prompts in `prompts/` (one file per prompt)
3. Put your eval cases in `evals/<name>.jsonl`
4. Add `GROQ_API_KEY` as a repo secret (Settings → Secrets and variables → Actions)
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

- **Model**: pass as the 4th arg to `run_evals.py`. Any litellm-supported model works (`groq/llama-3.3-70b-versatile`, `groq/llama-3.1-8b-instant`, `gpt-4o-mini`, `claude-3-5-haiku-latest`, etc). Set the matching env var for that provider.
- **Regression threshold**: 4th arg to `compare.py`, default `0.05` (5pp drop fails the build).
- **Multiple prompts**: extend the workflow with a matrix over prompt files, or run them sequentially in one job.

## Honest limitations

- **It costs API calls every PR.** On Groq's free tier, a 30-case eval is free and stays well under the daily quota. Larger evals on paid models can add up — size your eval set deliberately.
- **It throttles on free tiers.** The runner sleeps 2.1s between calls to stay under Groq's 30 requests/minute free tier. A 30-case eval takes around 60s. Remove the sleep if you're on a paid tier.
- **LLM-as-judge is noisy.** Rubric-graded cases will flap between PASS and FAIL on borderline outputs. Rely on exact-match when you can.
- **It's not a dataset manager.** If you need versioned datasets, drift detection, or human review queues, you want a real platform.
- **Single threshold is blunt.** A 5pp accuracy drop in one category can be invisible in the global metric. Read the per-category table before merging.

## License

MIT. Use it, fork it, ship it.