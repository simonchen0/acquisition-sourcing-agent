# Validation

Local-only build (no sign-in) merged with the Apollo pipeline from `main`, validated on macOS on 2026-10-16.

| Check | Result |
| --- | --- |
| `.venv/bin/pytest -q` | 75 passed (SQLite, mocked providers, synthetic Apollo fixtures; tests blank out `.env` keys) |
| `node --test tests/test_frontend.cjs` | 4 passed |
| `uv run python -m app` startup | `/health` ok with the embedded worker alive; all 7 pages load with no sign-in |
| Request guard | POST without the page token → 403; non-loopback `Host` → 403 |
| `.env` loading | Apollo, Brave, and OpenAI detected from the root `.env` |
| Search estimate (HVAC × Ohio, both, 100) | 15 Brave queries + 3 Apollo pages + 100 enrichments = 103 credits, about $2.75 |
| Live Brave brokered | Ran: 20 brokered rows stored before the job stopped |
| Live Apollo proprietary | **Failed:** `mixed_companies/search` returned HTTP 403. The key isn't entitled to that endpoint (check plan / API key permissions in Apollo). 1 credit was reserved. |
| OpenAI key | Accepted (`/v1/models` 200); a full evaluation run was not repeated after the key was replaced |

Earlier Brave-only run: HVAC × Ohio brokered, target 100, 13 queries, $0.065, 100 rows, xlsx export 200.
