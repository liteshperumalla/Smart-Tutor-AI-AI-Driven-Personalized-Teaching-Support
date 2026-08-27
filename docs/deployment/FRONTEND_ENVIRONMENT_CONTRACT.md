# Frontend environment contract

The browser always calls the same-origin `/api/backend` route. The Next.js
route handler then calls `BACKEND_API_BASE_URL`, which must be an HTTPS public
backend origin on Vercel. It must never be `http://backend:8000` or localhost
outside Docker.

## Production

Configure these in both Vercel Production and GitHub Actions before deploying:

| Setting | Purpose |
| --- | --- |
| `BACKEND_API_BASE_URL` | Public HTTPS API origin used only by the Next.js proxy. |
| `NEXT_PUBLIC_API_BASE_URL=/api/backend` | Keeps browser requests same-origin. |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth web-client ID (public client configuration). |
| `NEXT_PUBLIC_GOOGLE_REDIRECT_URI` | Exact registered callback: `https://your-app-domain/auth/google/callback`. |
| `NEXT_PUBLIC_APP_BASE_URL` | Public HTTPS app origin. |

The production workflow reads the corresponding GitHub secrets:
`PRODUCTION_API_URL`, `PRODUCTION_APP_URL`, `GOOGLE_OAUTH_CLIENT_ID`, and
`GOOGLE_OAUTH_REDIRECT_URI`. It intentionally fails rather than deploying
placeholder or localhost OAuth configuration.

## Vercel previews

Preview functions cannot resolve the Docker-only `backend` hostname. Add the
GitHub `STAGING_API_URL` secret with a reachable HTTPS staging API origin. The
staging deployment synchronizes it into Vercel Preview as
`BACKEND_API_BASE_URL` before deployment. Google OAuth is intentionally not
enabled for arbitrary preview aliases; register a stable staging callback if
preview OAuth is required.
