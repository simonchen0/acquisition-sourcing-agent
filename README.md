# Acquisition Sourcing Agent

A local, single-user app for search fund acquisition discovery and **explicitly initiated** investment evaluation. It has no sign-in and no Docker or Postgres. It reads API keys from the root `.env` and keeps everything in SQLite under `.data/`. There is no CRM or outreach automation.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env      # then paste your keys into .env
uv sync
uv run python -m app      # → http://127.0.0.1:8000
```

That one process serves the UI and runs the background job worker. Stop it with Ctrl-C. Queued or interrupted jobs resume the next time it starts. To use another port, set `PORT` in `.env`.

### Keys (`.env`)

| Variable | Purpose |
| --- | --- |
| `BRAVE_SEARCH_API_KEY` | Brave Search API token (discovery) |
| `BRAVE_STORAGE_RIGHTS_CONFIRMED=true` | Required before discovery stores results; confirm your Brave plan permits it |
| `BRAVE_EXPORT_RIGHTS_CONFIRMED=true` | Optional: lets Brave-sourced rows appear in exports |
| `OPENAI_API_KEY` (or `AI_API_KEY`) | OpenAI key for investment evaluation (optional) |
| `AI_MODEL` | Default `gpt-4.1-mini`; any chat-completions model with JSON mode |
| `APOLLO_API_KEY` | Reserved for the planned Apollo pipeline ([plan](docs/plans/ai-sourcing-pipeline.md)); not used yet |

Without keys, criteria, imports, profiles, document storage/previews, financial corrections, and exports still work. Discovery and AI evaluation then report that they need configuration; they never fabricate results. Default spend caps are $10 per search, $0.25 per evaluation, and $100 per month. Change them under Settings.

### Local safety

There is no sign-in, so the server binds to `127.0.0.1` only. It rejects requests whose `Host` is not loopback (DNS-rebinding guard) and requires a per-process page token on every write. That stops other websites from triggering paid API calls. Uploaded documents are Fernet-encrypted in `.data/documents`. The key is generated into `.data/document.key` unless you set `DOCUMENT_ENCRYPTION_KEY`. Back up `.data/` as a whole.

## What is implemented

- Six-section guided questionnaire: searchable industry and location choices, preserved custom options, exclusions, optional financial ranges, currencies, customer/revenue models, Yes/No characteristics with requirement strength, brokered/proprietary/both, and 100/250/500 targets **per category**. Review and save criteria before sourcing.
- Documented Brave Search API integration for both proprietary candidates and publicly indexed business-for-sale listings. No marketplace scraping, private-platform access, or invented companies. Original URLs and snippets remain linked to candidates.
- Separate dashboards, factual sorting, job-specific lists, company profiles, public contact extraction, supported manual fact verification, and cross-result deduplication. Search snippets and authorized imports are unverified until evidence is reviewed. Unknowns become **Needs Verification**, known conflicts become **Excluded**, and preferences never exclude.
- Persistent jobs with checkpoints, a renewable lease, bounded transient retries, cancellation, duplicate-active-job prevention, and collection preserved after failures. Browser closure does not stop the worker. Target shortfalls and exhausted budgets are explicit.
- Authorized CSV/XLSX import; CSV/Excel sourcing exports with spreadsheet formula protection and licensing gates. No investment scores in sourcing tables or exports.
- Separate standalone or sourced-company evaluation workspaces, encrypted uploads, PDF/CSV/XLSX/TXT extraction with source locations, explicit text previews, editable financial inputs, on-demand OpenAI analysis, deterministic financial ratios, validated literal citations, customizable category frameworks/presets, version history, readable Markdown and JSON reports.
- Restricted URL schemes, confidential-material deletion, per-operation budgets, monthly cost reservations, and provider usage records.

See [data sources and API setup](docs/providers.md) and [cost estimates](docs/costs.md).

## Screening and scoring

Source facts have `value`, `status`, `source`, and a supporting quote. Snippet financials are **reported**, not independently verified. Unknown currency prevents mandatory financial criteria from being satisfied. Facts manually confirmed by the account holder can satisfy screening; this is clearly identified as user-reviewed evidence, not independent platform verification. Location and industry filters require explicit supported facts, rather than inferring them from a search query. SDE is never substituted for EBITDA.

Evaluation scores exist only in versioned evaluation records. Upload does not extract or analyze; **Preview text** performs local extraction, and **Evaluate Investment** alone queues paid AI analysis. A criterion contributes to scoring only when it has reported/calculated support with exact uploaded-document quotes. Missing criteria are unscored and weights are normalized over supported evidence. Overall scores additionally require at least 70% weighted evidence coverage, financial-performance evidence, and supported revenue plus EBITDA or operating income for the same period/currency. Otherwise the report returns **Insufficient Information**. Valid quotes do not prove the AI's interpretation is correct: reports remain preliminary, and narrative findings require diligence.

Financial calculations use Decimal arithmetic and separate currencies/periods. Claimed adjustments and third-party estimates are displayed separately and excluded from deterministic calculations. User-reviewed figures replace extracted values for the same metric/year/currency. Contradictions and rejected citations/amounts are flagged. Reruns create new versions. Correct latest extracted financial figures through **Use latest extracted figures for correction**, save, and explicitly rerun.

## Tests

```bash
uv sync
.venv/bin/pytest -q
node --check app/static/app.js
```

Tests use a temp SQLite database and blank out `.env` keys, so they never call paid providers. See the [validation report](docs/validation.md).
