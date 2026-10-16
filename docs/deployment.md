# Online deployment

No hosting account, deployment API credentials, or public destination was provided. This guide prepares the tested application for your chosen host; it does not claim a public deployment.

## Docker Compose on an affordable HTTPS host

1. Provision a small Linux VM or managed Docker host. Clone/upload this repository or unpack the source ZIP.
2. Copy `.env.example` to `.env`, set a strong `POSTGRES_PASSWORD`, and use a URL-safe password; Compose constructs the matching database URL for web and worker. Keep PostgreSQL private, not publicly exposed.
3. Set a persistent `DOCUMENT_ENCRYPTION_KEY`. Set `COOKIE_SECURE=true` for hosted HTTPS (the local example defaults to false). Generate a Fernet key in a private terminal with Python/cryptography, then enter it securely in the host's secret manager. Do not paste it in chat. If omitted, a 0600 key is generated atomically in the private data volume; retain and back it up with the documents.
4. Configure Brave/OpenAI keys if desired, confirm your provider's storage/export permissions, and set accurate current prices. Both application services need the same provider variables. Confirm Apollo retention/export rights and actual credit pricing before enabling it.
5. Run `docker compose up -d --build`. The web process initializes tables after PostgreSQL is healthy. The worker waits for web health before starting to avoid concurrent first-run schema creation.
6. Provision the initial account using `docker compose exec web /app/.venv/bin/python -m app.cli create-user --email you@example.com`. The command prompts for a password; there is no signup or baked-in account. Add other users with the same administrator-controlled command. `app.cli setup` creates only the first account and is repeatable without overwriting credentials.
7. Configure your HTTPS reverse proxy to forward to host port 8000. Keep `COOKIE_SECURE=true`. Limit request bodies to 11 MB at ingress and timeouts appropriately; uploads themselves are limited to 10 MB each. Do not expose host loopback URLs as onboarding previews.
8. Verify `/health` returns a connected database, sign in, save/reopen criteria, inspect worker logs, upload/preview a nonconfidential test document, and run an authorized low-budget sourcing job. Test one explicitly initiated AI evaluation after confirming billing and confidentiality arrangements. These live tests were not run without provider credentials.

For local Compose HTTP only, set `COOKIE_SECURE=false`; restore true before online hosting. Secure cookies will intentionally prevent an HTTP production login.

## Railway, Render, or another managed host

Use the Dockerfile for a web service and the same image for a worker. Web start command:

```text
/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Configure your platform to route to port 8000 (or replace the port with its provided port). Set `EMBEDDED_WORKER=false` on the web service to use a separate production worker. Worker command:

```text
/app/.venv/bin/python -m app.worker
```

Attach a private managed PostgreSQL database. Set `DATABASE_URL` with the `postgresql+psycopg://` SQLAlchemy scheme. Configure TLS using your database provider's supported `sslmode` and CA requirements. Initialize the database once through the CLI/web service before starting the first worker.

**Shared document storage is required:** both services must mount the same persistent private path at `DATA_DIR=/data` and use the same Fernet key. Some inexpensive managed hosts do not support sharing one volume across separate services. For those hosts, deploy Compose on one host, or add an authorized shared/object-storage backend in a separate coding task. Do not deploy separate ephemeral volumes and assume the worker can read web uploads. SQLite is for a single development machine; PostgreSQL is the recommended hosted database.

Provision accounts through a secure host shell or one-time job. `ADMIN_EMAIL` and `ADMIN_PASSWORD` are accepted only by `app.cli create-user`; they do not silently provision or change an account on startup. Remove a one-time password binding after provisioning.

## Restricted proxy builds

The standard Docker build needs access to Docker Hub, PyPI, and Python package artifact hosts. Codex's build-container network does not automatically inherit the running machine's proxy or custom certificate trust. The Dockerfile supports an **optional BuildKit secret** named `build_ca` containing the authorized CA bundle. It is mounted only while installing dependencies, not retained in the final image.

For this cloud instance, the image was built with the supplied egress proxy, an explicit proxy DNS mapping, and `/etc/ssl/certs/ca-certificates.crt` as the trusted bundle. Use your own environment's documented proxy address, without embedding credentials in build arguments:

```bash
docker build \
  --add-host proxy:YOUR_PROXY_IP \
  --build-arg HTTP_PROXY=http://proxy:8080 \
  --build-arg HTTPS_PROXY=http://proxy:8080 \
  --secret id=build_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t acquisition-sourcing-agent .
```

Never disable certificate verification, replace package hashes, or embed a proxy's private key in the image. Runtime trust must also be configured through the host's supported CA settings if the deployed services use a TLS-inspecting proxy; the build secret alone does not configure runtime networking.

## Operations

- Run at least one persistent worker, with a restart policy. Development embeds a worker in the FastAPI lifespan; production Compose explicitly disables this and starts a separate worker. Queued jobs remain queued when all workers are offline. Browser polling is only a display of persisted database progress, not the job executor.
- Stale running jobs are reclaimable after the 300-second lease. Each successful sourcing query advances a persisted checkpoint. Retries keep successful candidates and obey remaining approved budgets. An AI request interrupted after the provider accepted it may be repeated on recovery; the original ambiguous reservation remains charged.
- Back up PostgreSQL, documents, and the encryption key consistently. Test restore. Infrastructure backup retention must respect confidential-material deletion policies.
- Use HTTPS, encrypted database storage, private volumes, restricted operator access, and provider-side spending limits. Application encryption covers uploaded document bytes; SQL report/notes fields rely on access controls and infrastructure encryption.
- The initial schema is created using `create_all`. It is not a migration framework. Introduce reviewed schema migrations before updating database models on a live deployment.
- Monitor health, persistent failed/incomplete jobs, worker restart logs, disk usage, and provider invoices. This initial release does not include a hosted scheduler, full observability platform, or distributed object-storage service.

The local `.env.example` defaults `COOKIE_SECURE=false` for loopback HTTP; production must set it to `true` behind HTTPS. Native local execution loads `.env` automatically. Compose supplies its own PostgreSQL URL from the URL-safe `POSTGRES_PASSWORD` and overrides `DATA_DIR=/data` for both services.
