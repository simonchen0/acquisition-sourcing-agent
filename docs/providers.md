# Provider integration contracts

## Apollo: implemented, fixture-tested; live compatibility unverified

Reference pages requested on October 16, 2026:

- https://docs.apollo.io/reference/organization-search
- https://docs.apollo.io/reference/organization-enrichment
- https://docs.apollo.io/reference/people-api-search
- https://docs.apollo.io/reference/people-enrichment
- https://docs.apollo.io/reference/rate-limits
- https://docs.apollo.io/reference/api-pricing

The environment's HTTPS proxy returned 403 during the CONNECT request. No API credential was configured. Consequently the handoff's endpoint/price claims could not be independently rechecked, and no real response was recorded. `tests/fixtures/apollo_*.json` explicitly identify themselves as synthetic fixtures; they must not be presented as live validation. A real licensed smoke run is still required before relying on data/credit estimates.

The adapter uses only fixed `https://api.apollo.io/api/v1/` endpoints, `x-api-key`, TLS verification, no redirects, and no arbitrary company-page requests:

| Operation | Configured endpoint | Default credit assumption |
| --- | --- | --- |
| Company search | POST `mixed_companies/search` | 1 per page, max 100 records |
| Organization enrichment | GET `organizations/enrich?domain=...` | 1/company |
| Owner/decision-maker lookup | POST `mixed_people/api_search` | 0; first name/title and availability flags only |
| Explicit email reveal | POST `people/match` | 1; phone/personal-email reveal disabled |

These defaults came from the supplied plan, **not independently verified pricing**. Set actual `APOLLO_CREDIT_COST_USD` and per-call credit settings for your plan. 403 reports paid-plan/permission issues; 429/5xx and network failures trigger bounded retries. Reservations precede paid calls, including reveals. Ambiguous failures retain their reservation because billing is uncertain.

The database coordinates a credential-scoped request slot across workers: minimum six-second spacing and configurable hourly cap up to 600. Pacing suspends a durable job without incrementing failed-provider attempts. Successful user-scoped API results are cached for an hour, only after retention rights are confirmed.

### Filter mapping and firmographics

`app/industry_map.json` covers every questionnaire industry using NAICS prefixes/keyword tags. Custom descriptions stay as original keyword tags. Shared NAICS exclusions are suppressed when they would remove an explicitly selected industry; keyword exclusions remain. Combining custom and predefined terms avoids requiring unrelated NAICS for custom matches. These are retrieval hints, not guarantees of coverage.

Geography, employee ranges, and USD revenue bounds map to the handoff's bracketed filter parameters. Broad illustrative margins in `app/benchmarks.json` can widen retrieval when EBITDA filters are present. They are **search-planning assumptions with no supplied licensed benchmark source**, never company EBITDA evidence. CAD revenue bounds are omitted from Apollo's USD filters rather than converted without an exchange rate.

Search results reporting public trading or a parent are skipped before paid enrichment. Domains deduplicate companies; returned enrichment domains must match. Organization IDs, reported industry/keywords/location/founding/ownership/funding, website/LinkedIn/switchboard, and modeled revenue/headcount retain provenance. Unclear classification remains Possible rather than being fabricated. Missing revenue/headcount, common in SMB datasets, cannot prove a required filter.

### Contacts and licensing

People search does not reveal emails/phones automatically. Each company profile can queue an approved business-email reveal. The requested person must already belong to that user's saved company record. Provider verification status is displayed without claiming independent verification. No outreach, phone reveal, personal-email reveal, contact-history tracking, or CRM.

Apollo retention requires `APOLLO_STORAGE_RIGHTS_CONFIRMED=true`; exports additionally require `APOLLO_EXPORT_RIGHTS_CONFIRMED=true`, default false. Having a key alone does not establish retention/re-export rights. Honor your actual agreement and delete retained data as required.

## Brave: documented search adapter; live credentials still required

Official documentation: https://api-dashboard.search.brave.com/documentation

`GET https://api.search.brave.com/res/v1/web/search` with subscription header, 20 results, offsets 0–9. Used for publicly indexed brokered listings, including site-scoped marketplace searches and independent brokerages. When Apollo is absent, existing proprietary company searches remain an explicit fallback. The app does not fetch marketplace pages, log into private systems, bypass CAPTCHAs/paywalls, or imply active listings/seller interest from a search hit.

Snippet facts remain unverified unless sufficient supported provider evidence is available; contacts are only those explicitly disclosed in the source. Public names/titles, LinkedIn URLs, emails, and North American phone numbers can be extracted without guessing. Retention and re-export are independently gated by the existing Brave settings. URL validation, user-scoped cache, deterministic deduplication, formula protection, and budget limits remain intact.

## OpenAI: optional explicit evaluation

Official documentation: https://platform.openai.com/docs/api-reference/chat

OpenAI is used only after **Evaluate Investment** is explicitly clicked. It is not used for Apollo classification, sourcing tiers, contact lookup, or automatic website research. Uploaded documents are untrusted evidence rather than executable instructions. JSON responses, literal citations, extracted amounts, document limits, and deterministic calculations are validated. Set `AI_API_KEY` (ordinary hosting also accepts `OPENAI_API_KEY`). Live model behavior remains unverified without credentials.

## Imports and optional extensions

Authorized CSV/XLSX exports, including PitchBook data your agreement permits, supplement automatic sourcing. Required columns `name,url`; optional `industry,country,location,currency,revenue,ebitda,sde,asking_price,employees,description,export_allowed`. Imported values remain unverified; re-export defaults false. Private marketplace/PitchBook APIs are not connected.

Phase 2 website analysis and Apollo lookalikes were explicitly optional in the handoff and conditional on thin live coverage. They are not activated or implemented in this upgrade because live coverage could not be measured. No additional AI spend is introduced.
