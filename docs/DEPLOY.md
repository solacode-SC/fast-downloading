# Production VPS Deployment Guide (`fastdownloading.solaymanbuilds.com`)

This guide covers deploying and updating FastDL on an Ubuntu VPS (e.g. DigitalOcean Droplet, 2 vCPU / 2–4 GB RAM) in both supported networking modes:
- **Mode A (Default):** Bundled Nginx container inside this stack exposing ports `80`/`443` with automated Let's Encrypt HTTPS.
- **Mode B (Shared Host Nginx):** Joins an existing external Docker network (`proxy_net`) and publishes **zero host ports**.

Default production coordinates baked into the automation scripts:
- **Domain:** `fastdownloading.solaymanbuilds.com`
- **Let's Encrypt Email:** `elmouden00den@gmail.com`

---

## Prerequisites

1. Ubuntu 24.04 / 22.04 VPS (root or `sudo` user).
2. DNS `A` record pointing `fastdownloading.solaymanbuilds.com` to your VPS IPv4 address.
3. Open ports `22/tcp`, `80/tcp`, and `443/tcp`.

---

## ⚡ One-Command Turnkey VPS Setup (Mode A — Bundled Nginx + HTTPS)

Clone the repository onto your VPS and run `make vps-setup`:

```bash
git clone <your-repo-url> /opt/fastdl
cd /opt/fastdl
make vps-setup
```

### What `make vps-setup` (`scripts/vps_setup.sh`) Automates:
1. **Host Preparation:** Verifies/installs Docker Engine, Docker Compose v2, `git`, `curl`, `jq`, `openssl`, configures a 2 GiB `/swapfile` on low-RAM droplets so builds never OOM, and opens `22/80/443` in `ufw` if active.
2. **Environment & Secrets (`.env.prod`):** Generates `.env.prod` with:
   - `DOMAIN=fastdownloading.solaymanbuilds.com`
   - `LETSENCRYPT_EMAIL=elmouden00den@gmail.com`
   - `CORS_ORIGINS=https://fastdownloading.solaymanbuilds.com`
   - Cryptographic 32-byte `HMAC_SECRET` (`openssl rand -hex 32`)
   - Random `GRAFANA_ADMIN_PASSWORD`
3. **Production Build & Launch:** Builds `vdl-backend:latest` and `vdl-frontend:latest` and starts `redis`, `pot-provider`, `api`, `worker`, `frontend`, and `nginx` with healthcheck waits.
4. **Let's Encrypt SSL & Zero-Conflict Nginx HTTPS (`scripts/ssl_setup.sh`):**
   - Issues the TLS certificate for `fastdownloading.solaymanbuilds.com` (`elmouden00den@gmail.com`) via webroot HTTP-01 challenge.
   - Renders `nginx/conf.d/tls.local.conf` (git-ignored so future `git pull` updates never conflict) from `nginx/templates/tls.conf.template` and reloads Nginx.
   - Installs a twice-daily auto-renewal cron job (`/etc/cron.d/fastdl-certbot` or user crontab).
5. **Health Verification:** Verifies `/healthz` over local HTTP and `https://fastdownloading.solaymanbuilds.com/healthz`.

> **Tip:** If you ran `make vps-setup` before your DNS `A` record finished propagating, the stack will start on HTTP and you can activate HTTPS at any time once DNS resolves by running:
> ```bash
> make ssl-setup
> ```

---

## 🔄 Pulling Updates & Upgrading the App (`make update`)

Whenever new code is pushed to your repository, SSH into the VPS and run:

```bash
cd /opt/fastdl
make update
```

### What `make update` (`scripts/update.sh`) Automates:
1. **Safety Snapshot:** Tags current `vdl-backend:latest` and `vdl-frontend:latest` as `:previous`.
2. **Git Pull:** Fetches and fast-forwards (`git pull --ff-only`) to the latest commit and prints the commit changelog.
3. **Config Sync:** Preserves all your existing secrets in `.env.prod` while automatically appending any new configuration keys introduced in `.env.prod.example`.
4. **Rolling Rebuild & Restart:** Rebuilds images, performs a rolling update (`up -d --remove-orphans --wait`), and reloads Nginx.
5. **Health Verification & Auto-Rollback:** Checks `/healthz`; if the new build fails health verification, it **automatically rolls back** to `:previous` images.
6. **Cleanup:** Prunes dangling Docker images to keep VPS disk space clean.

Additional update & rollback commands:
```bash
# Update and run the 4-platform download + ffprobe smoke suite
make deploy

# Update yt-dlp runtime overlay inside running containers without rebuilding images
make update-ytdlp

# Instant manual rollback to the previous production build
make rollback
```

---

## Mode B: Existing Host Nginx via Shared External Docker Network (`proxy_net`)

If your VPS already runs a central Nginx reverse proxy container on a Docker network (e.g. `proxy_net`):

```bash
# One-command setup in external-network mode (disables bundled Nginx, publishes zero host ports)
make vps-setup-external
```

Then copy `nginx/conf.d/external-proxy-snippet.conf` (pre-configured for `fastdownloading.solaymanbuilds.com`) into your existing Nginx container's `conf.d/` and reload Nginx. Future updates with `make update` automatically detect `external` mode and preserve it.
