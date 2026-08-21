# Resolve — Agentic Dispute Intelligence (Living POC)

**Live demo:** https://bj-nanda.github.io/resolve/ · **White paper:** [`whitepaper.pdf`](whitepaper.pdf)

Resolve is a product prototype exploring how an agentic AI layer could fix the highest-volume
customer pain at a major card issuer: dispute and investigation resolution. It is built entirely
on **public data** — 21,000+ real Capital One complaint narratives from the CFPB Consumer
Complaint Database — and refreshes itself nightly from the live CFPB API (plus on-demand via the Actions "Run workflow" button) via GitHub Actions.

*Independent research project by Bharathwaj Nandagopal. Not affiliated with Capital One.*

## The three agents

| Agent | What it does | How it's built |
|---|---|---|
| **Sentinel** | Discovers root-cause complaint themes with no labels and flags emerging-issue spikes (caught a 2.5–3.5σ surge in "merchant disputes — evidence ignored"; independently rediscovered the 360 Savings incident) | TF-IDF + NMF topic model, share-of-volume spike detection |
| **Triage** | Routes each complaint narrative to its regulatory lane (Reg Z / Reg E / FCRA / FDCPA / servicing) with confidence-based auto-routing | TF-IDF + logistic regression — 86% accuracy at 64% auto-route coverage |
| **Investigator Copilot** | Turns a raw complaint into an evidence inventory and a drafted, citation-grounded response letter | Claude API structured extraction + deterministic grounding check + zero-tolerance citation validator in a generate→validate→retry loop |

The design principle throughout: **gates are code, not prompts.** The LLM does the understanding;
deterministic validators guarantee that no letter cites evidence that doesn't exist.

## How the living refresh works

```
GitHub Actions (nightly cron + manual dispatch)
  └─ fetch_data.py      — pulls latest Capital One complaints from the CFPB public API
  └─ triage.py          — retrains & evaluates the lane classifier
  └─ sentinel.py        — re-clusters themes, re-runs spike detection
  └─ copilot.py         — rebuilds demo cases (llm_copilot.py if API key secret is set)
  └─ build_demo.py      — regenerates index.html → GitHub Pages redeploys
```

No servers, no exposed keys. The optional LLM step reads `ANTHROPIC_API_KEY` from the repo's
encrypted Actions secrets and costs under $0.05/run.

## Deploy your own copy

1. Create a public repo named `resolve`, upload these files.
2. Settings → Pages → Source: *Deploy from branch* → `main`, root folder.
3. Settings → Actions → General → Workflow permissions: *Read and write*.
4. (Optional) Settings → Secrets → Actions → add `ANTHROPIC_API_KEY` for live LLM drafting.
5. Actions tab → "Refresh Resolve with latest CFPB data" → *Run workflow* for the first build.

## Run locally

See [`TESTING.md`](TESTING.md) for the full runbook — smoke tests, adversarial tests
(prompt-injection, fabricated citations), and the extraction eval.

## Data & methods notes

Narrative percentages are computed on complaints with published narratives (~38% of all
complaints); the trend view uses share-of-monthly-volume to stay robust to CFPB publication
lag, and the last two calendar months are excluded for the same reason. Regulatory-lane labels
are derived from the CFPB issue taxonomy; held-out metrics use an 80/20 stratified split.
