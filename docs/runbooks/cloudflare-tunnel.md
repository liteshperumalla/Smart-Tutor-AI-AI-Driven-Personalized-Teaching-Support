# Cloudflare Tunnel for the backend

The Vercel frontend proxies API calls, including the user's session cookie
and `Authorization` header, to `BACKEND_API_BASE_URL`. Pointed at
`http://52.2.3.101`, those headers cross the internet unencrypted. A
Cloudflare Tunnel serves the backend over HTTPS instead:

```
Browser ──HTTPS──▶ Vercel ──HTTPS──▶ Cloudflare ──tunnel (outbound from EC2)──▶ cloudflared ──▶ smart-tutor-backend:8000
```

`cloudflared` runs as the `smart-tutor-tunnel` container on the instance's
Docker network and dials out to Cloudflare, so the instance needs no inbound
web port once the cutover is done.

## What the repo does

`deploy-production.yml`, when the `CLOUDFLARE_TUNNEL_TOKEN` secret is set:

- writes the token to `~/smart-tutor-tunnel.env` (mode 600) and runs
  `cloudflare/cloudflared` (pinned) as `smart-tutor-tunnel`, restart
  `unless-stopped`, logs to CloudWatch stream `tunnel`;
- recreates it only when the image or token changes, so ordinary deploys
  don't drop the tunnel;
- waits for `cloudflared`'s `/ready` (connected to Cloudflare) and fails the
  deploy if it doesn't connect within a minute.

When `BACKEND_PUBLIC_HOSTNAME` is set:

- it is added to `TRUSTED_HOSTS`; the backend rejects requests whose `Host`
  isn't listed;
- `FORWARDED_ALLOW_IPS` is set to the backend Docker network's subnet, so
  Uvicorn trusts the `X-Forwarded-Proto: https` that `cloudflared` sends.
  Without it, turning on `ENFORCE_HTTPS` would redirect every tunnelled
  request.

The Vercel proxy treats Cloudflare's own "origin unreachable" responses
(520–527, 530, or an HTML 502/504) like a connection failure, so a stopped
instance still shows the maintenance notice. It also drops `content-encoding`
and `content-length` from proxied responses, since `fetch()` has already
decompressed the body Cloudflare compressed.

Without the secret nothing changes.

## One-time setup

You need a domain whose DNS is on Cloudflare (any plan, including Free).

1. **Create the tunnel.** Cloudflare dashboard → Zero Trust → Networks →
   Tunnels → *Create a tunnel* → *Cloudflared*. Name it `smart-tutor`. On
   the install step choose *Docker* and copy the token (the long string after
   `--token`). Don't run the command shown; the deploy does that.
2. **Add the public hostname** (same wizard, *Public Hostname* tab):
   - Subdomain `api`, your domain (e.g. `api.example.com`)
   - Service type `HTTP`, URL `smart-tutor-backend:8000`

   Cloudflare creates the DNS record.
3. **GitHub** → Settings → Secrets and variables → Actions:
   - Secret `CLOUDFLARE_TUNNEL_TOKEN` = the token from step 1
   - Variable `BACKEND_PUBLIC_HOSTNAME` = `api.example.com`
4. **Deploy:** run **Production Deploy** (or merge to `main`). The run log
   shows `Cloudflare Tunnel connected after Ns`. Check:
   ```bash
   curl https://api.example.com/health
   ```
5. **Switch Vercel to HTTPS:** Vercel project → Settings → Environment
   Variables → `BACKEND_API_BASE_URL` = `https://api.example.com` (Production),
   then redeploy the frontend (variable changes only reach new
   deployments). Set the GitHub variable `PRODUCTION_API_URL` to the same
   URL so the synthetic monitor and post-deploy smoke test use it.
6. **Close the public HTTP path** once the site works through the tunnel:
   EC2 → the instance's security group → delete the inbound rules for ports
   80 and 8010 (keep 22; deploys open and revoke it themselves). The backend
   is then reachable only through the tunnel.

## Rolling back

In this order, so the site keeps working throughout:

1. Re-add the security group rules for ports 80 and 8010.
2. Set Vercel's `BACKEND_API_BASE_URL` back to the previous URL and
   **redeploy the frontend**: Vercel applies variable changes only to new
   deployments. Check the site works.
3. Set the GitHub variable `PRODUCTION_API_URL` back to the previous URL
   (synthetic monitor, post-deploy smoke test).
4. To remove the tunnel, delete the `CLOUDFLARE_TUNNEL_TOKEN` secret and the
   `BACKEND_PUBLIC_HOSTNAME` variable, then run on the instance:

```bash
docker rm -f smart-tutor-tunnel && rm -f ~/smart-tutor-tunnel.env
```

## Troubleshooting

| Symptom | Check |
|---|---|
| Deploy: "Cloudflare Tunnel did not connect" | Token copied whole? `docker logs smart-tutor-tunnel` |
| `https://api…/health` returns 502 | Public hostname service must be `smart-tutor-backend:8000`; is the backend container healthy? |
| `400 Invalid host header` | `BACKEND_PUBLIC_HOSTNAME` unset or different from the tunnel hostname; redeploy after fixing |
| Tunnel down after the instance restarts | `docker ps -a --filter name=smart-tutor-tunnel`; it restarts automatically unless it was stopped by hand |
