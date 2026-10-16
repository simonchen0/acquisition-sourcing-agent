# Acquisition Sourcing Agent

A functional two-stage web application for search fund acquisition discovery and **explicitly initiated** investment evaluation. FastAPI, SQLAlchemy, Pydantic, a durable SQL-backed worker, PostgreSQL in production, and SQLite for single-machine development. No CRM or outreach automation.

## What is implemented

- Six-section guided questionnaire: searchable industry and location choices, preserved custom options, exclusions, optional financial ranges, currencies, customer/revenue models, Yes/No characteristics with requirement strength, brokered/proprietary/both, and 100/250/500 targets **per category**. Review and save criteria before sourcing.
- Documented Brave Search API integration for both proprietary candidates and publicly indexed business-for-sale listings. No marketplace scraping, private-platform access, or invented companies. Original URLs and snippets remain linked to candidates.
- Separate dashboards, factual sorting, job-specific lists, company profiles, public contact extraction, supported manual fact verification, and cross-result deduplication. Search snippets and authorized imports are unverified until evidence is reviewed. Unknowns become **Needs Verification**, known conflicts become **Excluded**, and preferences never exclude.
- Persistent jobs with checkpoints, a renewable lease, bounded transient retries, cancellation, duplicate-active-job prevention, and collection preserved after failures. Browser closure does not stop the worker. Target shortfalls and exhausted budgets are explicit.
- Authorized CSV/XLSX import; CSV/Excel sourcing exports with spreadsheet formula protection and licensing gates. No investment scores in sourcing tables or exports.
- Separate standalone or sourced-company evaluation workspaces, encrypted uploads, PDF/CSV/XLSX/TXT extraction with source locations, explicit text previews, editable financial inputs, on-demand OpenAI analysis, deterministic financial ratios, validated literal citations, customizable category frameworks/presets, version history, readable Markdown and JSON reports.
- Per-account access controls, PBKDF2 password hashing, hashed session tokens, secure cookies, CSRF protection, sign-in rate limits, restricted URL schemes, confidential-material deletion, per-operation budgets, monthly cost reservations, and provider usage records.

**Live data/AI status:** no Brave or OpenAI credentials were provided during this build. Adapter calls were verified with mocked HTTP responses, not live providers. No 100–500-company live search, live AI evaluation, or public deployment has been claimed. Marketplace hits are possible listing candidates, not verified active listings; proprietary candidates are not confirmed sellers. Detailed contact enrichment is not implemented; only explicit names/titles, LinkedIn URLs, emails, and phone numbers actually displayed in source material are extracted. Scanned PDF OCR and legacy XLS are not supported.

## Run for development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). From this repository:

```bash
export UV_CACHE_DIR=/workspace/.uv-cache  # or another writable cache path
uv sync --frozen
.venv/bin/python -m app.cli init-db
.venv/bin/python -m app.cli create-user --email you@example.com
COOKIE_SECURE=false .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The account command prompts securely for a password of at least 12 characters. There is no public signup or default password. In another terminal, with the **same DATABASE_URL and DATA_DIR**:

```bash
.venv/bin/python -m app.worker
```

Alternatively, `scripts/dev-start.sh` starts both development processes with private logs/PID files; it is repeatable. `scripts/dev-stop.sh` stops only processes belonging to this checkout. Use your local browser on port 8000. `COOKIE_SECURE=false` is for loopback HTTP development only; leave it true behind HTTPS in production. `.env` is read automatically by Docker Compose, **not** by the Python application: export settings into the process environment or use your hosting provider's configuration. Optional local uvicorn `--env-file .env` loads variables only for the web process; the worker needs the same configuration.

Without provider keys, criteria, imports, profiles, authentication, document storage/previews, financial corrections, and exports work. Automatic discovery and AI evaluation visibly require configuration. They never silently use fabricated results.

## Connect real providers

Set these server-side environment variables on **both** web and worker; do not paste keys into chat or commit them:

| Variable | Purpose |
| --- | --- |
| `BRAVE_SEARCH_API_KEY` | Brave Search API subscription token |
| `BRAVE_STORAGE_RIGHTS_CONFIRMED=true` | Enable retained discovery only after confirming your subscription permits storage |
| `BRAVE_EXPORT_RIGHTS_CONFIRMED=true` | Optional: enable re-export only if your license permits it; false by default |
| `AI_API_KEY` | OpenAI credential; `OPENAI_API_KEY` is also accepted in ordinary hosting |
| `AI_MODEL` | Default `gpt-4.1-mini`; choose a chat-completions model supporting JSON mode |

Allow HTTPS egress to `api.search.brave.com` and `api.openai.com`. The Codex cloud secret binding uses `AI_API_KEY` because the platform reserves `OPENAI_` variable names. Connection indicators distinguish configured credentials from verified live access. The first real job tests authorization and reports failures without logging API keys or provider response bodies.

See [data sources and API setup](docs/providers.md) and [cost estimates](docs/costs.md).

## Screening and scoring

Source facts have `value`, `status`, `source`, and a supporting quote. Snippet financials are **reported**, not independently verified. Unknown currency prevents mandatory financial criteria from being satisfied. Facts manually confirmed by the account holder can satisfy screening; this is clearly identified as user-reviewed evidence, not independent platform verification. Location and industry filters require explicit supported facts, rather than inferring them from a search query. SDE is never substituted for EBITDA.

Evaluation scores exist only in versioned evaluation records. Upload does not extract or analyze; **Preview text** performs local extraction, and **Evaluate Investment** alone queues paid AI analysis. A criterion contributes to scoring only when it has reported/calculated support with exact uploaded-document quotes. Missing criteria are unscored and weights are normalized over supported evidence. Overall scores additionally require at least 70% weighted evidence coverage, financial-performance evidence, and supported revenue plus EBITDA or operating income for the same period/currency. Otherwise the report returns **Insufficient Information**. Valid quotes do not prove the AI's interpretation is correct: reports remain preliminary, and narrative findings require diligence.

Financial calculations use Decimal arithmetic and separate currencies/periods. Claimed adjustments and third-party estimates are displayed separately and excluded from deterministic calculations. User-reviewed figures replace extracted values for the same metric/year/currency. Contradictions and rejected citations/amounts are flagged. Reruns create new versions. Correct latest extracted financial figures through **Use latest extracted figures for correction**, save, and explicitly rerun.

## Deployment

See [deployment instructions](docs/deployment.md). Included: non-root Docker image, PostgreSQL + web + worker Compose configuration, persistent document/database volumes, `.env.example`, health check, and frozen dependency lockfile. HTTPS and hosting accounts are required for an online deployment; none were provided here.

```bash
cp .env.example .env
# Edit .env securely: set POSTGRES_PASSWORD, matching DATABASE_URL, encryption key, and provider keys.
docker compose up -d --build
docker compose exec web /app/.venv/bin/python -m app.cli create-user --email you@example.com
```

Keep `COOKIE_SECURE=true` and use an HTTPS reverse proxy. Compose exposes the web service on host loopback only. Set `COOKIE_SECURE=false` only for local HTTP testing. Back up the database, document volume, and encryption key together; the app cannot decrypt files after losing the key.

## Validation and source archive

```bash
uv sync --frozen
.venv/bin/pytest -q
node --check app/static/app.js
.venv/bin/python scripts/package.py
```

The archive is `dist/acquisition-sourcing-agent.zip`; it excludes credentials, uploaded files, virtual environments, caches, and Git metadata. [Validation report](docs/validation.md) records actual runs and their limitations.

## Security and operational boundaries

Accounts are administrator-provisioned. Confidential uploads use Fernet encryption; notes, extracted reports, session metadata, and structured financials are access-controlled SQL records, **not additionally encrypted by this application**. Production requires encrypted managed database storage, HTTPS, restricted operator access, encrypted backups, and a shared private document volume. Deleting a document also removes previous reports for its opportunity that may quote it; deleting the workspace removes its notes, financial inputs, files, reports, and evaluation-job snapshots. Infrastructure backup retention is controlled by your host.

For this first release, schema initialization uses SQLAlchemy `create_all`; it does not upgrade existing schemas. Back up and add explicit migrations before future schema changes. Keep the worker running; web health validates database connectivity, not worker health. Reservations are conservative estimates, including ambiguous failed requests; they are not a reconciliation of provider invoices. Provider prices and model capabilities must be checked against your current subscriptions. No paid provider is activated automatically.
