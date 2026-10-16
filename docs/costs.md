# Planning costs and spend controls

Provider prices below are configurable assumptions, not verified current quotes. Check your account's plan, endpoint entitlements, credit rules, and invoice before enabling paid calls.

| Category | Default planning assumption | Configuration |
| --- | --- | --- |
| Apollo company search | 1 credit per page, up to 100 results | `APOLLO_SEARCH_CREDITS` |
| Apollo organization enrichment | 1 credit/company, at most requested candidate count per job | `APOLLO_ENRICH_CREDITS` |
| Apollo owner lookup | 0 credits; no details revealed | fixed search-only call |
| Apollo email reveal | 1 credit, explicit per contact | `APOLLO_REVEAL_CREDITS` |
| Apollo credit price | **Unset; paid Apollo calls disabled until provided** | `APOLLO_CREDIT_COST_USD` |
| Brave search | $0.005/query | `BRAVE_REQUEST_COST_USD` |
| Local document processing | CPU only | file/page/row limits |
| Optional OpenAI evaluation | $0.40/$1.60 input/output per million tokens | configurable model/prices |

For a 250-target Apollo search, the retrieval ceiling is nine search pages, up to 250 enrichments, and at most 250 free owner lookups. The estimate shows 259 assumed credits plus Brave queries separately. It is a **projection**, not guaranteed candidate yield or provider billing. Failed/retried requests and explicit reveals can cost more; the originally approved job cap and monthly cap always apply. Early completion/cache hits can cost less. Enrichments rejected on ownership/data conflicts can leave the search short of target; no invented candidates fill the gap.

A key does not authorize unbounded spend. New accounts default to **$10 per search and $100/month**, editable in Settings; saved user limits are preserved. Evaluation's default remains $0.25/operation. Reveal jobs need their own explicit approved amount, bounded by the configured search/enrichment operation limit. No phone or personal-email reveal is requested.

Reservations precede network requests and update the monthly budget atomically. A successful cached response has no new reservation. Rate pacing has no charge and does not consume failed-provider attempts. Actual provider errors/retries retain conservative reservations where billing is uncertain. Provider invoices are authoritative; changing configured prices inaccurately undermines currency-based caps, so use provider-side limits too.

Apollo requests are paced at least six seconds apart and at most the configured 600/hour ceiling across workers sharing a credential. A 100-company enrichment plus owner-lookup run can take approximately 20 minutes at that ceiling. Progress is durable, so closing the browser does not stop it. In Both mode, Apollo and Brave work units alternate while either category has pending steps.

Allow a separate hosting budget (a small web/worker/database deployment can be roughly $15–$40/month, depending on host, storage, and backups). No paid provider was called and no subscription or public deployment was activated during this upgrade.
