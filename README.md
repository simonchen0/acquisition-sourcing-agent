# Acquisition Sourcing Agent

A two-stage acquisition-sourcing application: discover companies/listings, then explicitly evaluate selected opportunities after receiving diligence materials. FastAPI, SQLAlchemy, Pydantic, a durable job worker, PostgreSQL in production, and SQLite for local development. No automated outreach or CRM.

## Run locally — Linux or macOS

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required. From this checkout:

```bash
uv sync --frozen
cp .env.example .env  # only if you don't already have a .env; preserve existing settings
.venv/bin/python -m app.cli setup
scripts/dev-start.sh
```

`setup` initializes the database and prompts for the first account's email/password. Rerunning it preserves existing accounts and passwords. Activate `.venv` first if you prefer `python -m app.cli setup`. There is no default password or public signup. `ADMIN_EMAIL` / `ADMIN_PASSWORD` can be supplied securely for noninteractive provisioning; never commit them.

The application now loads `.env` automatically for both web and standalone worker, without overriding injected environment variables. Local defaults use `.data/app.db`. Set `COOKIE_SECURE=false` for local HTTP; `.env.example` does this. Set it **true** for hosted HTTPS. PostgreSQL and `/data` overrides belong in production configuration; Compose supplies them to its services.

The web process starts a background worker thread by default. **No second command is required for development.** Jobs stay in SQL, survive browser closure, and recover on process restart. The portable start/stop scripts use `ps` and `grep`, not `/proc` or ripgrep, and verify absolute checkout command paths before stopping processes. `scripts/dev-stop.sh` stops the development service. `/health` reports database connection and embedded-worker mode/liveness. Native macOS execution was not available for verification in the Linux build environment.

For production set `EMBEDDED_WORKER=false` on web and run `.venv/bin/python -m app.worker` separately. Compose already does this. See [deployment](docs/deployment.md).

## Sourcing pipeline

The guided questionnaire preserves custom industries, exclusions, geography, optional financial/employee ranges, Yes/No business characteristics, requirement/preference distinctions, and 100/250/500 targets **per selected category**.

- **Proprietary, when Apollo is configured:** company search → exclude known public/subsidiary records → deduplicate domains → enrich up to the requested number of candidates → owner/decision-maker lookup → factual screening → export.
- **Brokered:** Brave public indexed listing searches. The app does not scrape or access private marketplaces.
- **Fallback:** if no Apollo key is configured, the existing Brave proprietary discovery remains available and is identified as the provider in the search estimate. A configured but unusable Apollo key is reported as a setup error rather than silently bypassed.
- **Costs:** reserve before every paid call, user-scoped cache, persistent checkpoints, cancellation, bounded transient retries, and per-operation/monthly caps. New-account defaults are **$10/search and $100/month**, editable in Settings; previously saved limits are preserved. API prices must match your plan.
- **Contacts:** free owner/decision-maker lookup retains first name/title and availability flags only. **Reveal contact email** is a separate explicitly approved, budgeted job. Phone and personal-email reveals are disabled. Reveals are never automatic.

### Evidence and factual tiers

User-confirmed facts outrank supported provider reports. Unattributed snippets/imports stay unverified. Apollo revenue and employee counts are **modeled estimates**, labeled in the UI and spreadsheet; they do not confirm mandatory financial ranges. Unknowns are never invented or treated as satisfying a requirement.

Tiers are **Strong fit**, **Possible fit**, **Likely out of range**, and **Excluded**, with factual reasons. Only Strong/Possible fill the requested target count; estimates outside a range become Likely out of range rather than hard exclusions. Hard exclusions need conflicting confirmed/provider-reported evidence. Known public companies/parents are excluded; institutional funding is flagged, and conflicts with a Required independent-private-ownership criterion.

**There is no numeric sourcing fit score or investment score.** The user's explicit decision was to omit sourcing scores. Tier ordering followed by company name is deterministic. Investment scoring remains exclusively in the separate evaluation workflow.

Financial filters retain their original values. Illustrative margin assumptions in `app/benchmarks.json` can widen Apollo's USD retrieval range when EBITDA criteria are provided, but never supply company EBITDA or prove a financial match. CAD amounts are not sent as USD revenue filters. See [sources](docs/providers.md) for limitations.

## Provider configuration

Add values securely to `.env` locally or your host's server-side secret manager; never paste keys into chat or source control.

| Settings | Purpose |
| --- | --- |
| `APOLLO_API_KEY` | Apollo API credential with appropriate paid-plan endpoint entitlements |
| `APOLLO_CREDIT_COST_USD` | Actual cost of one credit; blank/zero disables Apollo requests |
| `APOLLO_SEARCH_CREDITS`, `APOLLO_ENRICH_CREDITS`, `APOLLO_REVEAL_CREDITS` | Configurable per-call credit assumptions; defaults 1, **not independently verified** |
| `APOLLO_STORAGE_RIGHTS_CONFIRMED=true` | Enable retention only after confirming your license permits it |
| `APOLLO_EXPORT_RIGHTS_CONFIRMED=true` | Enable re-export only when licensed; false by default |
| `BRAVE_SEARCH_API_KEY` | Brokered discovery and optional proprietary fallback |
| `BRAVE_STORAGE_RIGHTS_CONFIRMED=true`, `BRAVE_EXPORT_RIGHTS_CONFIRMED=true` | Separate licensed-retention/export controls |
| `AI_API_KEY` | Optional OpenAI document evaluation; ordinary hosting also accepts `OPENAI_API_KEY` |

Allow `api.apollo.io`, `api.search.brave.com`, and optionally `api.openai.com`. Read Apollo documentation at `docs.apollo.io`. The code enforces at least six seconds between Apollo calls plus at most 600/hour across workers sharing a credential; reduce the hourly limit for a more restrictive plan. Local pacing checkpoints the job and does not consume another credit or retry attempt.

**Integration status:** Apollo adapters and workflow are tested with explicitly synthetic fixtures. No Apollo key was supplied, and the proxy blocked documentation pages (403). Endpoint compatibility, response shapes, current credit prices, actual sourcing quality, and re-export licensing remain **unverified live**. The handoff document's claimed credit rates are configurable assumptions, not verified facts. No paid API calls were made during this upgrade. [Validation](docs/validation.md) distinguishes actual execution from mocks.

## Investment evaluation

Dedicated standalone or sourced-company workspaces support encrypted PDF/XLSX/CSV/TXT uploads, local text preview, editable financial inputs, explicit AI evaluation, source locations/citations, deterministic financial calculations, customizable category frameworks, saved presets, versions, and Markdown/JSON exports. Upload alone never triggers extraction or AI. Scanned PDFs need prior OCR; legacy XLS is not supported.

An overall score requires at least 70% weighted evidence coverage, a financial-performance assessment with exact document citations, and supported revenue plus EBITDA/operating income for the same period/currency. Otherwise reports return **Insufficient Information**. Missing evidence receives neither credit nor penalty. Claimed add-backs/third-party estimates stay separate, contradictions are flagged, and incompatible financial figures are excluded from calculations. Reports remain preliminary diligence support.

## Exports, imports, and security

CSV/Excel exports include factual tiers/reasons, estimate labels, ownership/funding information, contact availability, and source URLs. Re-export is gated per provider; formula protection is retained. No sourcing scores are exported. Authorized CSV/XLSX imports supplement automatic discovery; imported facts remain unverified. PitchBook access does not imply API or re-export entitlement.

Accounts are administrator-provisioned with PBKDF2 password hashes, hashed session tokens, CSRF checks, rate-limited sign-in, and account-scoped records. Uploaded file bytes use Fernet encryption. SQL notes, reports, and extracted figures rely on access controls and infrastructure encryption. Use HTTPS, encrypted managed storage/backups, private volumes, and consistent backups of database/documents/key. Deleting confidential workspaces removes their reports/materials; document deletion removes reports that could quote it. Provider request bodies/keys are not logged.

## Tests and packaging

```bash
uv sync --frozen
.venv/bin/pytest -q
node --check app/static/app.js
node --test tests/test_frontend.cjs
.venv/bin/python scripts/package.py
```

Tests ignore the application's database and paid credentials, using disposable SQLite by default. PostgreSQL tests require `TEST_DATABASE_URL` naming an isolated `_test` or `_tests` database and recreate its tables. Fixtures under `tests/fixtures/apollo_*.json` are synthetic, not recorded provider responses.

`dist/` is ignored and no longer tracked. The packaging command creates a source-only ZIP locally, excluding credentials, uploads, environments, and Git metadata. See [costs](docs/costs.md), [provider setup](docs/providers.md), and [deployment](docs/deployment.md). Public hosting and live provider validation require external credentials; they are not claimed complete.

## Restarting after an update

Stop/start the service after pulling code or changing `.env`. The launcher now verifies the exact server instance and frontend API version; an older healthy process on the same port is not accepted as a successful restart. macOS process checks use untruncated `ps -ww` output and can verify older relative launches via `lsof` working-directory evidence.

If a port is occupied by a process that cannot be safely identified, stop it from its original terminal or use `DEV_PORT=8001 scripts/dev-start.sh` and open the app on port 8001. Alternate ports have separate PID/instance records; stop that instance with `DEV_PORT=8001 scripts/dev-stop.sh`. The UI displays a restart message when current JavaScript receives an old server response, rather than crashing or enabling an outdated paid-search action. No API keys are displayed during these checks.
