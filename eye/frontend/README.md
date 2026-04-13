# ComadEye Frontend

Next.js 16 (App Router) UI for ComadEye. Talks to the FastAPI backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Getting Started

```bash
npm install
npm run dev    # http://localhost:3000
```

Environment variables (optional):

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=https://your-public-host        # used for metadataBase / OG URLs
```

## Routes

| Path | Purpose |
|---|---|
| `/` | Dashboard — recent jobs, system status |
| `/new` | Start a new analysis |
| `/analysis?job=<id>` | Multi-space analysis result + entity graph |
| `/report?job=<id>` | Full narrative report (markdown) |
| `/qa?job=<id>` | Interactive Q&A session |

## AI / Crawler Readability

`/analysis` and `/report` are server components that fetch data from the backend and inline it into the initial HTML (inside a visually-hidden `sr-only` section). This means:

- AI tools (ChatGPT, Claude, Perplexity) can read a shared report URL without executing JavaScript.
- Per-page `generateMetadata` produces unique `<title>` and `description` derived from the actual analysis — the description of `/analysis?job=abc` surfaces the top key findings, `/report?job=abc` surfaces the first 280 characters of the report.
- OpenGraph, Twitter Card, and JSON-LD (`SoftwareApplication`) tags are emitted from `app/layout.tsx`.
- `public/robots.txt` explicitly allows `GPTBot`, `ChatGPT-User`, `ClaudeBot`, `Claude-Web`, `PerplexityBot`, `Google-Extended`.

Server-side data fetches live in `lib/server-api.ts` (`server-only` guard, 30-second `revalidate`, silent `null` fallback when the API is down — the page still renders the interactive client without the SSR preview).

## Directory Layout

```
app/
  layout.tsx                 # Root layout, global metadata + JSON-LD
  page.tsx                   # Dashboard
  new/
    layout.tsx               # Per-route static metadata
    page.tsx
  analysis/
    page.tsx                 # Server component: generateMetadata + SSR preview
    AnalysisClient.tsx       # Client component: interactive dashboard
  report/
    page.tsx                 # Server component: generateMetadata + SSR markdown
    ReportClient.tsx         # Client component: live re-fetch + ReactMarkdown
  qa/
    layout.tsx
    page.tsx
components/                  # Shared UI (Sidebar, EntityGraph, Loading, …)
lib/
  api.ts                     # Client-side API (fetchWithRetry)
  server-api.ts              # Server-only fetch helpers used by generateMetadata/SSR
public/
  robots.txt                 # AI crawler allow list
```

## Quality Gates

```bash
npm run lint
npx tsc --noEmit
```
