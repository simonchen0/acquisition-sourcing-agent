# Matthew branch preference and browser E2E — October 16, 2026

Fetched all origin branches. Matthew's latest branch is `plan/apollo-brave-sourcing` at `0454052`; its history was already merged at `dad0860`, but that merge retained our overlapping launcher changes. At the user's request, `scripts/dev-start.sh` and `scripts/dev-stop.sh` now exactly match Matthew's branch. Other application changes remain present. The results below supersede historical launcher claims farther down this document.

Launched the real FastAPI server and external worker using Matthew's script on an isolated SQLite test database in the Linux cloud workspace. A Chromium/Playwright browser run passed these checks against the actual application, without HTTP response interception:

1. Sign in and load bootstrap.
2. Complete all six questionnaire steps, review the estimate, verify the $10 default and unavailable-provider guard, and save criteria.
3. Import a synthetic, explicitly exportable company CSV through the UI.
4. Open its results list and company profile.
5. Create its evaluation workspace, upload a synthetic document, and preview locally extracted text.
6. Save notes and reviewed financial figures; verify persistence after reload and disabled AI evaluation without credentials.
7. Download a CSV containing the imported company.
8. Save account settings and verify persistence after reload.
9. Verify uploads did not start an evaluation and provider usage remains empty.
10. Log out.
11. Observe zero uncaught JavaScript errors, including no `.join()` crash.

Automated results: **77 Python tests passed, 2 failed; 4 Node frontend tests passed**. The Python failures remain visible, with no assertions removed:

- `test_process_helper_is_portable_and_rejects_unrelated_pid`: a source-level assertion rejects `/proc`/`readlink` usage. Matthew's implementation intentionally uses `/proc` on Linux and an `lsof`/`ps` fallback on macOS, so this particular assertion conflicts with his implementation; it does not prove the macOS fallback fails.
- `test_start_script_does_not_claim_success_for_an_old_listener`: a behavioral regression. The launcher returned success when an old server occupied the port. The real stop/restart exercise also left the old listener running in this sandbox, followed by a failed bind despite the success message. Identified test processes were terminated explicitly before the final successful browser run. His stop/start scripts have not been changed to conceal this result.

Live Apollo/Brave/OpenAI requests, full automated sourcing, AI-generated evaluation reports, and native macOS startup were **not validated** in this run. No paid provider credentials or user `.env` contents were used. Passing local browser checks must not be interpreted as passing those integrations or the failing launcher regression.

---

# Frontend / stale-server repair validation (historical, before Matthew script restoration)

The subsequent repair passed **79 Python tests on SQLite**, **4 Node frontend regression tests**, and real Chromium regression checks. PostgreSQL's 76-case pipeline run below predates this repair; it was not repeated for the frontend/process-lifecycle changes.

Reproduced an original legacy estimate without `setup_errors` and verified that the current frontend rejects its outdated shape instead of throwing on `.join()`. Missing diagnostic lists receive a readable fallback with paid sourcing disabled. Partial saved criteria receive defaults, and mixed frontend/backend versions show a restart message before the search form loads. The review dialog preserves the $10 default.

The restart helper now verifies a per-launch instance identifier/API version, rejects an already occupied port before spawning another server, uses untruncated portable process checks, and keeps separate PID records for alternate ports. Tests confirmed it cannot treat an old `/health` response or another instance's identifier as successful startup. Actual start/repeated-start and browser behavior were exercised on Linux; native macOS remains unverified. No paid provider calls or user credentials were involved.

---

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
