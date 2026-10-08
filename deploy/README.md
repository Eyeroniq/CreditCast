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
