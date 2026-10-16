# Validation — Apollo pipeline upgrade

Run in the Linux Codex cloud environment on October 16, 2026. All 45 original tests remain intact and passing, with 31 additional test cases for the upgrade. No paid provider request was made.

| Check | Actual outcome |
| --- | --- |
| Frozen dependency installation | Passed: `uv sync --frozen`; python-dotenv is now a declared direct dependency |
| Automated suite, SQLite | **76 passed**, including the original 45 |
| Automated suite, PostgreSQL 16 | **76 passed** against an isolated disposable `acquisition_tests` database |
| Apollo adapters | Passed with **synthetic fixtures / mocked HTTP**, not recorded live responses |
| Apollo request mapping | Geography, employee/revenue filters, custom industries, complete questionnaire map, shared NAICS exclusions, CAD handling, and illustrative EBITDA search expansion checked |
| Durable pipeline | Search/enrich/people checkpoints, deduplication, public/subsidiary prefilters, wrong-domain rejection, budgets, cache credit avoidance, rate-limit pacing, and legacy-provider preservation checked |
| Contacts | Automatic lookup does not reveal details; explicit reveal reserves credits; contact ownership/user isolation checked |
| Screening/exports | No numeric sourcing score; factual tiers/reasons, estimated-financial treatment, funding ambiguity, source licensing gates, tier filters, and spreadsheet columns checked |
| Setup/environment | First-account setup is repeatable without password overwrite; .env loads without overriding injected settings; tests isolate DBs and paid credentials |
| Embedded worker | Real lifespan thread processed a mocked discovery job without a second worker process; health reported worker liveness |
| Development scripts | Real start, repeated start without duplicate service, stop, and restart passed on Linux; scripts use portable `ps`/`grep` and absolute checkout paths |
| Chromium browser | Real login, questionnaire, provider-specific estimate, saved criteria, factual tier/filter, modeled-estimate labels, explicit reveal-approval dialog, and $10/$100 defaults passed; desktop/mobile inspected; no JS errors |
| Docker | Non-root image built with certificate verification preserved; container health confirmed database and embedded worker startup |
| Compose configuration | Validated using a copy of `.env.example`; web/worker receive PostgreSQL and shared data-directory settings; embedded web worker disabled for Compose |
| JavaScript / shell / Git | Syntax checks and whitespace checks passed |

SQLite/PostgreSQL results are the same 76 cases executed on two backends, not 152 independent cases. One upstream Starlette deprecation warning concerns its httpx TestClient backend; tests executed and passed.

## What remains unverified

- **Apollo official documentation:** proxy returned 403 during CONNECT to `docs.apollo.io`. The supplied plan's claimed parameters, credit rates, and plan requirements could not be independently checked against current endpoint pages.
- **Real Apollo responses/credits:** no key/binding was configured. The `apollo_*.json` fixtures are explicitly synthetic. No real response was recorded, and no live credit use was reconciled.
- **Live sourcing quality:** the requested 100-target run, hand-check of 25 candidates / 70% genuine-fit goal, and recall against approximately 10 known companies could not run without provider credentials, network access, and a supplied known-company reference list.
- **Native macOS:** portability was implemented and Linux process lifecycle was exercised; a native macOS machine was unavailable.
- **Public deployment:** not performed. Local/container execution does not establish a published website.
- **Optional phase 2:** website/AI signal extraction and Apollo lookalikes remain deferred until live coverage can justify them. No extra AI spend was introduced.

Enter keys securely in environment settings, configure the actual Apollo credit prices and licensed storage/export permissions, and apply the saved Apollo API/docs network destinations. After that, retry documentation access and perform an explicitly budgeted small live search before relying on company yield or cost projections. Never submit keys in chat or commit them.

## Additional safeguards found during implementation

- Existing queued Brave jobs retain their provider contract when an Apollo key is later enabled.
- USD provider estimates do not exclude a CAD-denominated range without supported currency conversion.
- Funding amount alone does not prove institutional ownership; unclear investor type remains a verification flag.
- Returned enrichment domains and reveal-person IDs must match the saved company/contact.
- Local request pacing does not consume retry attempts or reserve another credit.
- `dist/` remains ignored and its previously tracked ZIP is removed in this branch. The packaging script can regenerate a local source-only archive without keys or confidential data.
