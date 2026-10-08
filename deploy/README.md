# Deploying CreditCast to dhyyraj.in

CreditCast ships as **one Docker image**: FastAPI serves the API under `/api`
and the pre-built Next.js Risk Cockpit at `/`. The image trains the models at
build time (and fails the build if a CI performance gate fails), so the running
container only serves. [Caddy](https://caddyserver.com/) sits in front and
handles HTTPS automatically.

```
Internet ──443──▶ caddy (TLS, dhyyraj.in) ──▶ app:8000 (FastAPI + cockpit)
```

## 1. Server

Any Linux VM with Docker (Docker Engine 24+ and Compose v2.24+) and at
least **2 GB RAM** (the build trains LightGBM/SHAP models). Open ports **80**
and **443**.

## 2. DNS

At your domain registrar, create:

| Type | Name | Value |
|------|------|-------|
| A    | `@`   | server's public IPv4 |
| A    | `www` | server's public IPv4 |
| AAAA | `@`, `www` | server's IPv6 (optional) |

Wait until `dig +short dhyyraj.in` returns the server IP. Caddy needs this to
get the certificate.

## 3. Secrets (optional)

The Risk Copilot (AI chat) needs a free Groq key; everything else works
without it. On the server, in the repo root:

```bash
echo "GROQ_API_KEY=your_key_here" > .env
chmod 600 .env
```

`.env` is gitignored; never commit it.

## 4. Launch

```bash
git clone https://github.com/Eyeroniq/CreditCast.git
cd CreditCast
docker compose -f deploy/docker-compose.yml up -d --build
```

Open https://dhyyraj.in. Health check: https://dhyyraj.in/api/health

## 5. Update to a new version

```bash
git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

## Settings (`.env`, all optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | unset | Enables the Risk Copilot (AI chat) |
| `CC_ALLOWED_ORIGINS` | unset (same-origin only) | Extra websites allowed to call the API from a browser, comma-separated |
| `CC_API_KEY` | unset | Require header `X-API-Key` on `/api/score` and `/api/agent/chat`. **Leave unset for the public site**: the cockpit can't hold a secret, so setting it disables scoring and the Copilot in the browser. Use it for API-only deployments. |

Rate limits per visitor (in `creditcast/conf/config.yaml` → `api`):
Copilot 10/min + 100/day, scoring 60/min, portfolio 30/min.

## Health and audit trail

- `https://dhyyraj.in/api/health`: the process is up.
- `https://dhyyraj.in/api/ready`: every model file is present and loads, and
  it returns the model version fingerprint. Docker's `HEALTHCHECK` uses it, and
  Caddy only starts once the app is healthy.
- Every scoring decision is appended to `decisions.jsonl` in the
  `decision_logs` volume. Each line holds the request ID, model version and
  fingerprint, a SHA-256 hash of the inputs (never the raw inputs), the PD,
  the decision, the reason features and the latency. Files rotate at 10 MB
  (10 kept).

```bash
docker compose -f deploy/docker-compose.yml exec app tail -n 5 /app/logs/decisions.jsonl
docker compose -f deploy/docker-compose.yml ps        # shows (healthy)
```

## Useful commands

```bash
docker compose -f deploy/docker-compose.yml logs -f app     # app logs
docker compose -f deploy/docker-compose.yml logs -f caddy   # TLS / proxy logs
docker compose -f deploy/docker-compose.yml down            # stop
```

## Local run (no domain)

```bash
docker build -t creditcast .
docker run -p 8000:8000 --env-file .env creditcast    # http://localhost:8000
```
