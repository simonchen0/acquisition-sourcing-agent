# Validation

Local-only build (no sign-in), validated on macOS on 2026-10-16.

| Check | Result |
| --- | --- |
| `.venv/bin/pytest -q` | 46 passed (SQLite, mocked providers; tests blank out `.env` keys) |
| `node --check app/static/app.js` | Passed |
| `python -m app` startup | `/health` ok; pages load with no sign-in; `/login` is 404 |
| Request guard | POST without the page token → 403; non-loopback `Host` header → 403 |
| `.env` loading | Brave and OpenAI keys detected from the root `.env` with nothing exported in the shell |
| Live Brave sourcing (embedded worker) | HVAC × Ohio, brokered, target 100: 13 queries, $0.065 reserved, 100 targets saved, xlsx export 200 |
| Live OpenAI evaluation | **Not verified:** the OpenAI key in `.env` (`OPENAI_API_KEY`) was rejected with HTTP 401 `invalid_api_key` |

Known limitation (unchanged from the previous build): Brave-sourced brokered hits are mostly marketplace category pages with no structured facts, so they all land in **Needs Verification**. The Apollo plan in `docs/plans/ai-sourcing-pipeline.md` addresses this.
