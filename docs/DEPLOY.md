# Production VPS Deployment Guide (DigitalOcean + Docker + Nginx + TLS)

This guide covers deploying FastDL to a single Ubuntu VPS (e.g. DigitalOcean Droplet, 2 vCPU / 2–4 GB RAM) in both supported networking modes:
- **Mode A (Default):** Bundled Nginx container inside this stack exposing ports 80/443.
- **Mode B (Shared Host Nginx):** Joins an existing external Docker network (`proxy_net`) and publishes **zero host ports**.

---

## Prerequisites

1. Ubuntu 24.04 / 22.04 VPS with Docker Engine & Docker Compose plugin installed.
2. DNS `A` record pointing `dl.yourdomain.com` to your VPS IPv4 address.
3. Firewall (`ufw`) allowing only `22/tcp`, `80/tcp`, and `443/tcp`.

---

## Step 1: Clone & Configure

```bash
git clone <your-repo-url> /opt/fastdl
cd /opt/fastdl
make setup
```

Edit `.env.prod`:
- Set `CORS_ORIGINS=https://dl.yourdomain.com`
- Verify `HMAC_SECRET` was replaced with a random 64-char hex string (`openssl rand -hex 32`)
- Configure `PROXY_URLS` (or WARP) if deploying on a datacenter IP (see [EGRESS.md](EGRESS.md))
- Optionally enable `TURNSTILE_ENABLED=true` with your Cloudflare Turnstile keys.

---

## Mode A: Bundled Nginx + Let's Encrypt TLS (Default)

### 1. Build & Start Over HTTP First

```bash
make prod-build
make prod-up
make prod-ps
```

Confirm every container (`redis`, `pot-provider`, `api`, `worker`, `frontend`, `nginx`) reports `healthy`.
Verify:
```bash
curl -fsS http://dl.yourdomain.com/healthz
curl -fsS http://dl.yourdomain.com/readyz | jq
```

### 2. Issue a Let's Encrypt TLS Certificate

Use Certbot sharing the `vdl_prod_certbot_www` and `vdl_prod_letsencrypt` volumes:

```bash
docker run --rm \
  -v vdl-prod_vdl_prod_certbot_www:/var/www/certbot \
  -v vdl-prod_vdl_prod_letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
  -d dl.yourdomain.com \
  --email admin@yourdomain.com \
  --agree-tos --no-eff-email
```

### 3. Enable HTTPS in `nginx/conf.d/app.conf`

1. Uncomment the `listen 443 ssl; http2 on;` server block at the bottom of `nginx/conf.d/app.conf` and replace `dl.yourdomain.com` with your domain.
2. Add `return 301 https://$host$request_uri;` to the port 80 `server` block (keeping `location /.well-known/acme-challenge/` above it for renewals).
3. Validate Nginx config & reload:
   ```bash
   docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod exec nginx nginx -t
   docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod exec nginx nginx -s reload
   ```
4. Add a host cron job for automatic renewals twice daily:
   ```cron
   15 3,15 * * * docker run --rm -v vdl-prod_vdl_prod_certbot_www:/var/www/certbot -v vdl-prod_vdl_prod_letsencrypt:/etc/letsencrypt certbot/certbot renew --quiet && docker compose -p vdl-prod -f /opt/fastdl/docker-compose.prod.yml --env-file /opt/fastdl/.env.prod exec -T nginx nginx -s reload
   ```

---

## Mode B: Existing Host Nginx via Shared External Docker Network

If your VPS already runs a central Nginx reverse proxy container on a Docker network (e.g. `proxy_net`):

1. Ensure the shared network exists:
   ```bash
   EXTERNAL_NET=proxy_net make network
   ```
2. Build and launch using the external-network override (disables bundled Nginx, publishes **no** host ports):
   ```bash
   docker compose -p vdl-prod \
     -f docker-compose.prod.yml \
     -f docker-compose.prod.external-net.yml \
     --env-file .env.prod up -d --build
   ```
3. Copy `nginx/conf.d/external-proxy-snippet.conf` into your existing Nginx container's `conf.d/`, update `server_name` and certificate paths, and reload Nginx. It routes directly to `fastdl-frontend:3000` and `fastdl-api:8000` over `proxy_net`.

---

## Deploying Updates & Rollback

```bash
# Zero-guesswork deploy: tags current images as :previous, pulls, rebuilds, waits for health, runs smoke
make deploy

# Instant rollback to previous image tag if anything regresses
make rollback
```
