# Acquisition Sourcing Agent

A local, single-user app for search fund acquisition sourcing, plus **explicitly initiated** investment evaluation. It has no sign-in and no Docker or Postgres. It reads API keys from the root `.env` and keeps everything in SQLite under `.data/`. There is no CRM or outreach automation.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env      # then fill in your keys
uv sync
uv run python -m app      # → http://127.0.0.1:8000
```

That one process serves the UI and runs the background job worker. Stop it with Ctrl-C. Queued or interrupted jobs resume the next time it starts. To use another port, set `PORT` in `.env`. Restart after changing `.env` or pulling code.

## Sourcing pipeline

The guided questionnaire covers industries (including custom ones), exclusions, geography, optional financial and employee ranges, Yes/No characteristics marked required or preferred, and 100/250/500 targets **per category**. Results are split into two lists:

- **Proprietary companies (Apollo):** company search → drop public companies and subsidiaries → dedupe by domain → enrich up to the target count → owner/decision-maker lookup → screening → export. If no Apollo key is set, Brave proprietary search is used as a fallback. A configured but unusable Apollo key is reported as an error rather than silently bypassed.
- **Brokered deals (Brave):** publicly indexed listings on BizBuySell, BizQuest, BusinessesForSale, DealStream and broker sites. There is no scraping of private marketplaces.
- **Costs:** every paid call is reserved against the per-search and monthly caps before it is made (defaults $10 and $100, editable in Settings). Results are cached per query, jobs checkpoint and can be cancelled, and transient errors are retried within bounds. The pre-run estimate lists Brave queries and Apollo credits separately.
- **Contacts:** the free owner lookup keeps first name, title and whether an email or phone exists. **Reveal contact email** is a separate, budgeted job you start yourself; it never runs automatically. Phone and personal-email reveals are disabled.

### Screening tiers

User-confirmed facts outrank provider reports. Apollo revenue and headcount are **modeled estimates** and are labeled that way in the UI and export. They never confirm a mandatory financial range. Each company is placed in **Strong fit**, **Possible fit**, **Likely out of range**, or **Excluded**, with reasons. Only Strong and Possible count toward the target. Public companies and subsidiaries are excluded; institutional funding is flagged. There is no numeric sourcing score, and investment scoring lives only in the evaluation workflow.

EBITDA criteria can widen Apollo's USD revenue search band using the illustrative margins in `app/benchmarks.json`. Screening still uses your original numbers. CAD ranges are not sent to Apollo as USD.

## Keys and settings (`.env`)

| Variable | Purpose |
| --- | --- |
| `APOLLO_API_KEY` | Apollo API key (paid plan with API access) |
| `APOLLO_CREDIT_COST_USD` | Your actual cost per credit; blank/0 disables Apollo |
| `APOLLO_SEARCH_CREDITS`, `APOLLO_ENRICH_CREDITS`, `APOLLO_REVEAL_CREDITS` | Credits assumed per call (default 1); check against your plan |
| `APOLLO_STORAGE_RIGHTS_CONFIRMED`, `APOLLO_EXPORT_RIGHTS_CONFIRMED` | Set `true` only if your Apollo license allows storing / re-exporting |
| `BRAVE_SEARCH_API_KEY` | Brokered discovery (and proprietary fallback) |
| `BRAVE_STORAGE_RIGHTS_CONFIRMED`, `BRAVE_EXPORT_RIGHTS_CONFIRMED` | Same, for Brave |
| `OPENAI_API_KEY` (or `AI_API_KEY`) | Optional: investment evaluation |
| `AI_MODEL` | Default `gpt-4.1-mini`; any chat-completions model with JSON mode |

Apollo calls are paced at least 6 seconds apart and at most `APOLLO_CALLS_PER_HOUR`. Pausing for pacing never uses extra credits. A 100-company run makes about 200 Apollo calls (1 enrichment and 1 people search per company), so expect around 20 minutes.

Without keys, criteria, imports, profiles, document storage/previews, financial corrections, and exports still work. Discovery and evaluation then show which configuration is missing; they never fabricate results.

## Investment evaluation

Standalone or sourced-company workspaces support:
- encrypted PDF, XLSX, CSV and TXT uploads, with local text preview;
- editable financial inputs;
- explicitly started AI evaluation with source citations;
- deterministic financial calculations;
- customizable category frameworks and saved presets;
- version history, plus Markdown and JSON export.

Uploading alone never triggers extraction or AI. An overall score requires all of the following, otherwise the report says **Insufficient Information**:
- at least 70% weighted evidence coverage;
- a cited financial-performance assessment;
- revenue plus EBITDA or operating income for the same period and currency.

## Local safety

There is no sign-in, so the server binds to `127.0.0.1` only. It rejects requests whose `Host` is not loopback (DNS-rebinding guard) and requires a per-process page token on every write. That stops other websites from triggering paid API calls. Uploaded documents are Fernet-encrypted in `.data/documents`. The key is generated into `.data/document.key` unless you set `DOCUMENT_ENCRYPTION_KEY`. Back up `.data/` as a whole.

## Tests

```bash
uv sync
.venv/bin/pytest -q
node --test tests/test_frontend.cjs
```

Tests use a temp SQLite database and blank out `.env` keys, so they never call paid providers. Apollo fixtures in `tests/fixtures/` are synthetic. See [validation](docs/validation.md), [costs](docs/costs.md), and [provider details](docs/providers.md).
