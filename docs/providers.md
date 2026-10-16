# Data sources and API setup

## Brave Search — implemented adapter, credentials required

Official documentation: https://api-dashboard.search.brave.com/documentation

The application calls `GET https://api.search.brave.com/res/v1/web/search` with `X-Subscription-Token`, query text, `count=20`, and offsets 0–9. A bounded set of industry/location/query variants covers each selected category. Custom industry and region answers are preserved verbatim. Fewer-than-requested results remain incomplete; mandatory criteria are never relaxed.

Brokered discovery uses publicly indexed acquisition searches, including site-scoped queries for BizBuySell, BizQuest, BusinessesForSale, and DealStream, plus broader brokerage queries. The app does **not** fetch those sites or access their private APIs. A hit must contain listing-related language before becoming a candidate. Listing aggregations, stale listings, and ambiguous identities still require human verification. Anonymous listings retain their disclosed title and never receive an invented company identity.

Proprietary discovery uses industry/location company queries. Deduplication uses a normalized company domain; separately listed brokered deals use their full listing URL. This conservative implementation can merge independent companies sharing a domain or miss companies with several domains; profiles retain evidence for human review. Search-index visibility is not guaranteed company coverage. Search snippets are not complete company dossiers.

Storage is disabled until `BRAVE_STORAGE_RIGHTS_CONFIRMED=true`. Check your exact subscription/license for retention rights. Search responses have a one-hour user-scoped cache; sourced candidate records persist until database retention policies remove them. Re-export is disabled unless `BRAVE_EXPORT_RIGHTS_CONFIRMED=true`. Do not enable either setting based only on having an API key.

API errors report status codes, not confidential headers/bodies. 429 and 5xx responses are retried at most three times; every request has a new conservative cost reservation. TLS verification and provider protections are maintained.

## OpenAI — implemented adapter, credentials required

Official documentation: https://platform.openai.com/docs/api-reference/chat

The evaluation worker calls `POST https://api.openai.com/v1/chat/completions` only for manually selected opportunities after the user presses Evaluate Investment. Set `AI_API_KEY` (`OPENAI_API_KEY` is accepted outside the Codex binding restriction) and `AI_MODEL`. JSON-mode responses are validated with Pydantic, exact document citations are checked, unsupported extracted amounts are rejected, and financial calculations run in Python. Model output is treated as untrusted input; it cannot fetch arbitrary URLs, send outreach, or execute tools. Uploaded document instructions are explicitly treated as evidence, not system commands.

Maximum 10 files, 10 MB each, 300 PDF pages, 10,000 spreadsheet rows, and an 80,000-character combined AI material limit. Inputs are rejected when too large; no silent document truncation. Text-only PDFs are supported; scanned documents require prior OCR. Prompt/output usage is recorded in the report. Network failures remain charged conservatively because the application cannot prove whether the provider billed them.

Document content is sent to your configured AI provider only when evaluation is explicitly requested. Choose an appropriate provider account and data-retention arrangement for confidential materials.

## Authorized CSV / Excel imports — implemented supplement

The application accepts user-permitted data exports, including PitchBook exports your license permits. PitchBook access is not an API entitlement, and no PitchBook scraping or API access is claimed.

Required headers: `name,url`. Optional: `description,industry,country,location,currency,revenue,ebitda,sde,asking_price,employees,export_allowed`. Numbers are raw amounts, not expressions like `5M`; currencies are USD or CAD. Duplicate company domains/listing URLs are removed within a job. Blank name/unsafe URL rows are skipped and counted. Import facts remain reported/unverified. `export_allowed` defaults to false and must be explicitly true when re-export is licensed.

## Public contact extraction — implemented, limited

Only names/titles, emails, phone numbers, or LinkedIn URLs visibly supported in source text may be presented. This release extracts explicitly labeled owner/founder/CEO/president/broker names, LinkedIn profile URLs, emails, and North American phone numbers from snippets, preserving their source and unverified status. It does not guess identities, infer emails, or claim deliverability verification. Contact enrichment beyond source-disclosed details and Apollo lookup remain future licensed extensions. No automated outreach, contact histories, or CRM is implemented.

## Additional providers — not connected

Apollo needs a suitable licensed API account; Axial and DealMatch require separately authorized access. BizBuySell, BizQuest, BusinessesForSale, DealStream, and brokerages may be visible through public search indexing; direct feeds require documented permission. No login, CAPTCHA, paywall, or robots restriction is bypassed. Add future provider adapters through the discovery module, preserving field provenance, authorization, category separation, budgets, and export permissions. This release deliberately has one real automatic-discovery provider rather than placeholder marketplace adapters.
