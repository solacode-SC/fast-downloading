# Egress IP Strategy (Anti-Block L5)

Datacenter IP ranges (DigitalOcean, AWS, Hetzner, GCP) are the #1 trigger for YouTube `BOT_CHECK` and Instagram/Facebook `LOGIN_REQUIRED`. Locally, FastDL defaults to a **direct connection** because residential/home IPs rarely face blocks. For VPS production deployments, choose one of the three strategies below.

---

## Option A — Rotating Residential / ISP Proxy Pool (Recommended for Production)

ISP/static-residential proxies provide clean ASN reputation with fast download speeds.

1. Set one or more proxy URLs in `.env.prod` (credentials are automatically redacted from all logs and Prometheus labels):
   ```dotenv
   # Global pool for all platforms
   PROXY_URLS=http://user:pass@isp1.provider.net:8000,http://user:pass@isp2.provider.net:8000

   # Or assign per platform (e.g. direct for X, residential for YouTube & Instagram)
   PROXY_URLS_YOUTUBE=socks5h://user:pass@res-yt.provider.net:1080
   PROXY_URLS_INSTAGRAM=http://user:pass@res-ig.provider.net:8000
   PROXY_URLS_FACEBOOK=http://user:pass@res-fb.provider.net:8000
   PROXY_STRATEGY=sticky
   PROXY_MAX_FAILURES=3
   PROXY_COOLDOWN_SECONDS=300
   ```
2. Optional local proxy relay container (`--profile proxy`) is included in `docker-compose.prod.yml` if you need an internal forwarder.
3. Restart:
   ```bash
   make prod-restart
   ```

---

## Option B — Cloudflare WARP Sidecar (Free / Low-Cost VPS Upgrade)

Cloudflare WARP routes egress traffic out of Cloudflare consumer egress IPs instead of your VPS datacenter subnet. A ready-to-use `warp` profile is built into `docker-compose.prod.yml`.

1. Update `.env.prod`:
   ```dotenv
   PROXY_URLS=socks5h://warp:1080
   # Or route only YouTube & Instagram through WARP:
   # PROXY_URLS_YOUTUBE=socks5h://warp:1080
   # PROXY_URLS_INSTAGRAM=socks5h://warp:1080
   ```
2. Start the production stack with the `warp` profile enabled:
   ```bash
   docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod --profile warp up -d
   ```
3. Verify WARP connectivity from the API container:
   ```bash
   docker compose -p vdl-prod -f docker-compose.prod.yml --env-file .env.prod exec api \
     curl -s --proxy socks5h://warp:1080 https://www.cloudflare.com/cdn-cgi/trace | grep warp
   ```
   Expected output: `warp=on`.

---

## Option C — Home / ISP Worker Over WireGuard or Tailscale

Keep the lightweight public web/API/Nginx stack on your DigitalOcean VPS, and run an additional `worker` container (or a lightweight SOCKS5 proxy) on a home Raspberry Pi / mini-PC connected over **Tailscale** or **WireGuard**:

1. **Simple SOCKS5 exit node via Tailscale:**
   - Install Tailscale on both your VPS and home device (`tailscale up --advertise-exit-node` or run a local `dante`/`gost` SOCKS5 server bound strictly to the Tailscale IP `100.x.y.z:1080`).
   - In the VPS `.env.prod`, set:
     ```dotenv
     PROXY_URLS=socks5h://100.x.y.z:1080
     ```
2. **Direct remote worker mode:**
   - Expose Redis ONLY over the WireGuard/Tailscale interface (never on public internet) with a strong Redis password.
   - Run the `vdl-backend` worker container on your home machine pointing `REDIS_URL` to the VPS Tailscale IP, or sync artifacts over WireGuard. (Option 1 — SOCKS5 over Tailscale — is simpler because files stay on the VPS disk directly.)
