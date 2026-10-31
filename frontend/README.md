# Smart AI Tutor frontend

Next.js (App Router) client for Smart AI Tutor. Production runs on Vercel at
https://smart-ai-tutor.vercel.app; the FastAPI backend runs on EC2 (see the
root [README](../README.md)).

> This is Next.js 16. APIs and conventions differ from older versions; the
> bundled docs are in `node_modules/next/dist/docs/` (see `AGENTS.md`).

## Layout

| Path | What it is |
|---|---|
| `src/app/` | Routes (`chat`, `quiz`, `research`, `code`, `admin`, `instructor`, auth pages, …) and the root `layout.tsx` |
| `src/app/api/backend/[...path]/route.ts` | Server-side proxy to the backend. The browser only talks to `/api/backend/*` on this origin; the proxy forwards to `BACKEND_API_BASE_URL` and turns an unreachable backend into a 503 (`scheduled_maintenance` inside the stop window, `backend_unavailable` otherwise) |
| `src/lib/api.ts` | Typed API client used by the pages |
| `src/lib/maintenance.ts` | The Mon–Fri 9 AM–5 PM CT schedule. The site banner (`components/maintenance-banner.tsx`) only shows when `/api/backend/health` fails; the schedule picks its wording |
| `src/components/` | Shared UI (site chrome, chat pieces, toasts, …) |
| `public/fonts/` | Self-hosted fonts: brand fonts plus the bundled Google fonts in `public/fonts/google` (no Google Fonts download at build) |
| `e2e/` | Playwright checks of the public routes |

## Running locally

Start the backend first. From the repository root, `docker compose up -d`
publishes it on `127.0.0.1:8010`, which is where the proxy points in
development. Then:

```bash
npm ci
npm run dev            # http://localhost:4000
```

### Environment

All optional for local development.

| Variable | Used by | Default |
|---|---|---|
| `BACKEND_API_BASE_URL` | Proxy (server only) | `http://localhost:8010` in development; must be set in production |
| `NEXT_PUBLIC_API_BASE_URL` | Browser API client | `/api/backend` (the proxy) |
| `NEXT_PUBLIC_APP_BASE_URL` | Server-side requests to this app | `http://localhost:4000` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, `NEXT_PUBLIC_GOOGLE_REDIRECT_URI` | Google sign-in | unset (Google sign-in hidden) |

Put local values in `frontend/.env.local` (git-ignored).

## Checks

These are the commands CI runs (`.github/workflows/ci-cd.yml`):

```bash
npm run type-check
npm run lint
npm test -- --coverage --watchAll=false   # Jest; fails below the floors in jest.config.js
npm run build

# Public-route browser checks (needs `npm run build` and a running `npm run start -- -p 4000`)
npx playwright test --config=playwright.public.config.ts --project=chromium
```

## Deployment

Vercel builds `main` for production and every pull request for a preview.
`BACKEND_API_BASE_URL` and the other variables above are set in the Vercel
project settings. The backend deploys separately through
`.github/workflows/deploy-production.yml`.
