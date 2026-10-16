# Build plan: Apollo + Brave sourcing pipeline

> **Handoff doc for the coding agent working in this repo.** It is self-contained: read it fully before starting.
> - Work on a branch.
> - Keep the existing 45 tests passing.
> - Add tests for each new module.
>
> Apollo API facts below were taken from docs.apollo.io on 2026-10-16. Re-check the endpoint pages before coding, and record a real response as a test fixture.

## Why
Today's discovery (`app/discovery.py`) runs templated Brave queries and regex-parses ~200-char search snippets. It never extracts industry, location, or size. `screen()` (`app/criteria.py`) only trusts facts with `status == 'verified'`, and nothing discovery produces is verified, so **every sourced company lands in "Needs Verification"**. The result is an unranked pile.

**Decisions already made:**
- Upgrade the existing FastAPI app. Keep the criteria form, job/worker/budget system, exports, and tests.
- Brokered and proprietary deals are weighted equally.
- Output is a spreadsheet export.
- **Providers:**
  - **Apollo** is the main source for proprietary companies, company firmographics, and owner contacts.
  - **Brave** covers brokered listings, which Apollo doesn't have.
  - OpenAI stays **optional**: only the existing document-evaluation feature and phase 2 below use it.

## Pipeline
**Criteria → Apollo company search → Apollo enrichment (top candidates) → Apollo owner lookup → Screen & rank → Export**, plus **Brave** for brokered listings in parallel (existing code).

### 0. Make it runnable first (small; do before anything else)
- **Fix the macOS dev scripts.** `scripts/dev-start.sh` and `dev-stop.sh` use `/proc/<pid>` and `rg`, which are Linux-only. They falsely report "Web startup failed" and never start the worker. Replace them with `ps -p <pid> -o command=` + `grep`.
- **Run as one process.** Start the worker as a background thread in a FastAPI lifespan handler in `app/main.py`. Keep `python -m app.worker` working for production/Compose.
- **Load `.env` automatically** in `app/config.py` (add `python-dotenv`). Add `APOLLO_API_KEY` and `APOLLO_CREDIT_COST_USD` to `.env.example`.
- **One setup command.** `python -m app.cli setup` runs init DB and creates the first user.
- **Budget defaults.** Per-search cap $10, monthly cap $100, both editable in Settings.
- **Repo hygiene.** Remove `dist/` from git and add it to `.gitignore`.

### 1. Map criteria → Apollo filters (new `app/apollo.py: build_org_filters(criteria)`)

| Criteria field (`app/criteria.py`) | Apollo param (`POST /api/v1/mixed_companies/search`) |
|---|---|
| `countries`, `regions` | `organization_locations[]` (e.g. `"ohio, united states"`, `"ontario, canada"`) |
| `employees` range | `organization_num_employees_ranges[]` as `"min,max"` |
| `revenue` range | `revenue_range[min]`, `revenue_range[max]` (integers) |
| `industries` | `organization_naics_codes[]` (prefix match) **and/or** `q_organization_keyword_tags[]` |
| `exclusions` | `not_organization_naics_codes[]`, `q_not_organization_keyword_tags[]` |
| EBITDA range (no Apollo filter) | derive a revenue band from EBITDA ÷ industry margin band (`app/benchmarks.json`), then use the wider of the user's revenue range and the derived one |

**Industry mapping.**
- Create `app/industry_map.json` mapping every option in the questionnaire's `INDUSTRIES` list (`app/static/app.js`) to NAICS prefixes + keyword tags. Example: HVAC → NAICS `238220` + tags `hvac`, `heating`, `air conditioning`.
- For custom industries the user types in, pass the text as keyword tags.
- Apollo's `organization_industries[]` needs exact lowercase Apollo names, so prefer NAICS + keywords.

**Request details.**
- **Auth:** `x-api-key` header.
- **Paging:** `per_page=100`, `page=1..N`.
- **Cost:** **1 credit per page.**
- **Rate limit:** 600 calls/hour. Throttle, and treat 429 as `TransientProviderError`.
- **Plan:** requires a **paid** plan (otherwise 403). Surface that as a clear setup error.

### 2. Harvest proprietary candidates (`app/jobs.py: run_sourcing`)
- **Add `ApolloProvider`** alongside `BraveProvider` in `app/discovery.py`.
  - Proprietary category = Apollo org search.
  - Brokered category = existing Brave queries; keep the existing `normalize()` brokered path.
- **Reuse the existing job machinery:** `reserve()` before every paid call (credits × `APOLLO_CREDIT_COST_USD`), job cursor/checkpoints, cache, cancellation, retries.
- **Dedupe.** `canonical_url()` dedupes by domain; use Apollo `primary_domain`. Store Apollo `id` on the target.
- **Pre-filters (no extra credits), applied from search-result fields:**
  - drop if `publicly_traded_symbol` is set
  - drop if `owned_by_organization_id` is set: a subsidiary, not an independent owner-run business
  - store `founded_year`, `website_url`, `linkedin_url`, and `primary_phone` as facts
- **Fact format.** Apollo facts get `status: 'reported'` and `source: 'Apollo'`, plus the Apollo org URL. Treat Apollo revenue/headcount as *modeled estimates*. Label them that way in the UI and export, because Apollo SMB revenue is often modeled and sparse under ~50 employees.

### 3. Enrich top candidates (`GET /api/v1/organizations/enrich?domain=…`, 1 credit each)
- Enrich only candidates that pass the pre-filters, up to the target count. That keeps credit use ≈ target count, not harvest size.
- **Store as facts:**
  - `estimated_num_employees`, `annual_revenue`
  - `industry` / `industries`, `keywords`
  - `city` / `state` / `country`
  - `founded_year`
  - `owned_by_organization`, `ultimate_parent_organization`
  - `total_funding`, `latest_funding_stage`
- **Flags:**
  - Any parent organization → Excluded (not independent).
  - VC funding present → flag as "Institutionally funded" (a preference, not a hard exclude unless the user marks `private_ownership` Required).

### 4. Owner/decision-maker lookup (`POST /api/v1/mixed_people/api_search`, **0 credits**)
- Per enriched company: `organization_ids[]=<apollo id>`, `person_seniorities[]=owner,founder,c_suite`, `per_page=5`.
- Store first name, title, `has_email`, and `has_direct_phone` as contacts with status "Apollo; contact details not revealed".
- **Email/phone reveal** (people enrichment / `people/match`) **costs credits.** Add a per-company **"Reveal contact"** button that runs it on demand through `reserve()`, never automatically.
- No outreach automation; that's out of scope, per the README.

### 5. Screen & rank (modify `app/criteria.py: screen()`)
- **Trust ladder:** `verified` (user-confirmed) > `reported` (Apollo, listing text) > `estimated` (derived from benchmarks). Today only `verified` counts, which is the core bug.
- **Excluded** only on a conflicting verified/reported fact. Examples: HQ outside selected regions, excluded industry, parent org, public company, franchise when excluded.
- **Tiers:**
  - **Strong fit:** location + industry + size all supported and in range.
  - **Possible fit:** no conflicts, some unknowns.
  - **Likely out of range:** only estimates, and they fall outside the range.
  - **Excluded.**
- **`fit_score` (0–100)** comes from preference coverage + data completeness, with one-line `fit_reasons`. It is criteria fit only. No investment score in sourcing, which preserves the app's two-stage rule.
- **Wiring:** update `jobs.counts()` to fill the target with Strong + Possible. Add tier/score columns and filters to the dashboards in `app/static/app.js`.

### 6. Export (`app/exports.py`)
- **Add columns:** Fit tier, Fit score, Fit reasons, Industry, HQ city/state, Founded, Employees (Apollo est.), Revenue (Apollo est.), Ownership/parent, Funding, Owner name/title, Contact revealed (Y/N), Apollo URL, LinkedIn, Website.
- Sort by tier, then score.
- Keep `safe_cell` formula protection and the export-rights gate. Check Apollo's terms for re-export of its data, and default `export_allowed` accordingly.

### 7. Phase 2 (optional, only if Apollo coverage is thin)
- **Website check via Brave + OpenAI.** Brave `site:` search or a fetch of the company homepage, then OpenAI JSON extraction of signals Apollo lacks: family-owned, founder tenure/succession, recurring service contracts, B2B vs B2C.
- **Quote validation.** Keep a fact only if its quote appears verbatim in the page text, the same idea as `evaluation.cite_valid`.
- **Lookalikes.** Use Apollo `lookalike_organization_ids[]` (up to 5 seeds) to expand from the best Strong-fit companies.

## Files
- **New:**
  - `app/apollo.py` (client + filter builder)
  - `app/industry_map.json`
  - `app/benchmarks.json`
  - tests: `tests/test_apollo.py` and fixtures under `tests/fixtures/apollo_*.json`
- **Modified:**
  - `app/discovery.py`, `app/jobs.py`, `app/criteria.py`, `app/exports.py`
  - `app/config.py`, `app/main.py` (lifespan worker, reveal-contact endpoint, estimate endpoint includes Apollo credits), `app/cli.py`
  - `app/static/app.js`
  - `scripts/dev-start.sh`, `scripts/dev-stop.sh`
  - `.env.example`, `README.md`, `docs/providers.md`, `docs/costs.md`
  - `pyproject.toml` / `uv.lock`

## Cost model (verify against the actual Apollo plan)
- **Apollo:**
  - search = 1 credit / 100 companies
  - enrichment = 1 credit / company
  - people search = free
  - contact reveal = credits, on demand only
  - A 250-company run costs ≈ a few search pages + ~250 enrichment credits + reveals.
- **Brave:** ≈ $0.005/query for brokered.
- **Budget display.** The pre-run estimate (`/api/search/estimate`) must show Apollo credits and Brave queries separately.

## Verification
1. **Unit tests** (mocked HTTP with recorded fixtures):
   - criteria → Apollo params mapping
   - pre-filters (public/subsidiary dropped)
   - enrichment → facts
   - `screen()` tiers
   - reveal goes through `reserve()`
   - export columns
   - All existing tests still pass: `uv sync && .venv/bin/pytest -q`.
2. **Local run on macOS:** `scripts/dev-start.sh` → `python -m app.cli setup` → log in → save criteria → start search → the worker processes it.
3. **Live smoke run:** one industry × one state, target 100, small budget.
   - Hand-check 25 Strong/Possible rows. Target: ≥70% genuine fits (right industry and geography, independent, plausible size).
   - Confirm credit use matches the estimate.
4. **Recall check:** list ~10 companies already known to fit. Check how many the run surfaces, then tune `industry_map.json` and filters from the misses.
