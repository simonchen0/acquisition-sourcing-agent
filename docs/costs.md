# Operating cost estimates

These are **configurable planning assumptions**, not verified current provider quotes. Confirm rates with your subscriptions before spending.

| Cost category | Default assumption | Controls |
| --- | --- | --- |
| Sourcing | $0.005 per Brave request (up to 20 hits) | `BRAVE_REQUEST_COST_USD`, per-search cap, monthly cap, user-scoped one-hour cache |
| Contact enrichment | $0 paid enrichment | Public snippet extraction only |
| Document processing | Local CPU, no per-document external fee | File/page/row/text limits |
| AI evaluation | $0.40 input / $1.60 output per million tokens | Configurable model/rates, explicit initiation, approved cap, 5,000 output-token ceiling |
| Hosting | Plan for roughly $15–$40/month for a small web/worker/database deployment | Provider pricing, shared volume, database and backup choices vary |

At the default Brave request assumption, 100 uncached requests reserve $0.50; 1,000 reserve $5. These are **requests**, not guaranteed matched companies. Duplicate hits, excluded results, and unavailable facts reduce yield. Both categories share a single approved job cap while counts are tracked independently. Brokered and proprietary queries are interleaved so one category cannot exhaust the cap first.

The UI shows maximum query count and projected uncached cost before starting sourcing. Initial account limits: $1 per search, $0.25 per AI evaluation, and $20 per month. Change these in Settings before approving a higher-cost job. Current jobs retain their originally approved cap.

AI cost reservation uses a conservative UTF-8 byte bound for the actual message payload plus message framing and a 5,000-token output ceiling. It is deliberately greater than typical tokenization. At default rates the full 80,000-character limit can reserve around $0.15 depending on text encoding, schema, notes, and reviewed financial rows. Typical shorter reports cost less, but the application retains the conservative reservation rather than claiming a reconciled invoice amount. Repeated/ambiguous failed requests also consume reservations.

All reservations are checked before outbound paid requests with an atomic monthly-spend update. Monthly counters use UTC calendar months. Cached searches incur no new provider reservation. Retries never bypass the original job or monthly limit. Search cancellation takes effect between requests; an in-flight request may already be billed. Provider billing is authoritative, and inaccurate configured prices invalidate currency-based caps; set provider-side account limits as well.
