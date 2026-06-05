# Curriculum Frontend

Next.js frontend for AI Curriculum Creator.

The frontend supports:

- guest intent classification, retrieval preview, and curriculum generation
- browser-local guest plans
- Supabase Google OAuth when a learner opens a module
- persisted module design and checkpoint flows
- learner plan history
- admin dashboards for learners, content, checkpoints, and hotspots

## Local Development

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
```

Run:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The backend must allow `http://localhost:3000` through `CORS_ALLOW_ORIGINS`.
Supabase Auth must allow:

```text
http://localhost:3000/auth/callback
```

## Cloudflare Workers Deployment

The application uses OpenNext for Cloudflare Workers:

```bash
npm run deploy
```

Public runtime variables must be configured for the deployed Worker. The
deployed worker origin must also be allowed by the backend CORS configuration
and Supabase Auth redirect settings.

## Build Verification

```bash
npm run build
```

For complete runtime architecture, backend setup, deployment, and operations, see
the repository root `README.md`.
