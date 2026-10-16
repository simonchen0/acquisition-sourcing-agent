# Validation results

Validated in the Codex cloud workspace on October 13, 2026. This report distinguishes real application execution from mocked provider responses.

| Check | Result | Scope |
| --- | --- | --- |
| Frozen installation | Passed | `uv sync --frozen`, Python 3.12, repository lockfile |
| Automated suite, SQLite | **45 passed** | Questionnaire/binary logic, mandatory vs preferred rules, currency/financial/geographic/industry filters, missing facts, deduplication, contacts, exports, uploads, extraction, deterministic financials, citation/scoring rules, confidential access controls, persistence, budgets, cancellation, recovery, versions |
| Same suite, PostgreSQL 16 | **45 passed** | Dedicated disposable `acquisition_tests` database; actual psycopg/SQLAlchemy transactions |
| Brave HTTP adapter | Passed with mocks | Checks documented host/endpoint, subscription header, response normalization; no live request or dataset |
| OpenAI HTTP adapter | Passed with mocks | Checks explicit workflow, request format, validated report, citation handling; no live AI request |
| Chromium browser smoke | Passed | Real HTTP sign-in, custom industry/geography selection, binary franchise answer, full questionnaire, saved criteria, standalone evaluation, confidential CSV upload, explicit preview, edited financial persistence, and settings |
| Desktop/mobile inspection | Passed | 1440px and 390px layouts inspected; no browser JavaScript errors |
| Docker image build | Passed | Frozen dependencies installed with verification intact; non-root Python 3.12 image |
| Docker + PostgreSQL + worker | Passed | Real containerized HTTP login, saved criteria/import/results/Excel, encrypted upload/preview, separate worker processing and persistence of an expected missing-provider failure |
| Development startup helper | Passed | Started web/worker and reran startup without duplicate processes; database health request succeeded |
| JavaScript syntax | Passed | `node --check app/static/app.js` |
| Git whitespace check | Passed | `git diff --check` |

The SQLite and PostgreSQL suite counts describe the **same 45 tests executed against two database backends**, not 90 independent test cases. One upstream Starlette warning announces deprecation of the current httpx TestClient backend; assertions executed and passed.

Tests use a temporary SQLite database by default and deliberately ignore application `DATABASE_URL`. To test PostgreSQL, provide `TEST_DATABASE_URL` naming an isolated database ending `_test` or `_tests`; the suite recreates its tables. Never point it at production.

## Issues found and fixed

- An unauthenticated favicon request could redirect to sign-in and replace its anti-CSRF nonce. Favicon is now public and the sign-in nonce is reused across concurrent sign-in pages. Browser sign-in and a regression test pass.
- The restricted environment's Docker build did not inherit the running machine's proxy/DNS and custom CA trust. Builds were corrected with the provided proxy route and an optional BuildKit CA secret, preserving TLS and artifact verification.
- Conflicting financial disclosures no longer select an arbitrary last value for deterministic ratios; the conflicting metric is excluded pending reconciliation. A conflicting critical financial period cannot justify an overall score.
- Startup helpers verify process ownership and reuse existing processes. Tests isolate their database rather than using a possibly production-configured application URL.

## Not verified / outstanding

- Live Brave search authorization, current subscription storage/export rights, real sourcing yield, and requested 100–500 candidates per category: missing credentials/license configuration.
- Live OpenAI model access, output quality on an actual CIM, and provider invoice pricing: missing credentials and confidential diligence materials.
- Apollo/PitchBook/private-marketplace APIs: not integrated; authorized imports and public indexed searches are the supported alternatives.
- Public online deployment and remote restore: no hosting destination or deployment credentials supplied. Docker/local cloud validation does not establish a published website.
- Broad public directory/company website extraction, deliverability verification, OCR, object storage, and schema migrations are not included in this release.

No paid API calls were made. No financial documents were sent to an AI provider. All test business names and provider responses were fixtures clearly separated from live sourcing results.
