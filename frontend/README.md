# Candor frontend

The editorial research interface for [Candor](../README.md), built with React 19, TypeScript, Vite, Tailwind CSS and React Router. The application fetches report content from the FastAPI backend.

## Run locally

Start the API from the repository root in one terminal:

```bash
source .venv/bin/activate
READ_ONLY_MODE=true python -m uvicorn api.main:app --host 127.0.0.1 --port 8321 --reload
```

For a fresh checkout, follow the [root README's dependency setup](../README.md#quick-start) first.

In a second terminal, starting from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open the URL Vite prints, normally `http://localhost:5173`. The development server proxies `/api` to `http://127.0.0.1:8321` and removes the `/api` prefix before forwarding requests.

## Pages

| Route | Content |
|---|---|
| `/` | Landing page, live research preview and methodology overview |
| `/app` | Research library with company filters and search |
| `/app/calls/:ticker/:quarter` | Earnings brief, claims and transcript |
| `/app/calls/:ticker/:quarter/claims/:index` | Source quote, citation verdict, waveform and transcript context |
| `/app/evaluation` | Recorded citation and claim-coverage results |

The report route accepts `?t=830`, for example, to position the source player at 830 seconds once audio metadata loads. Claim and transcript timestamp controls seek the report's existing player. The evidence view preserves its WaveSurfer instance while navigating between claims in the same call.

## Design and code

- `src/index.css`: shared ink, parchment and brass visual system, responsive layouts, focus states and reduced-motion rules.
- `src/components/`: navigation, verdicts, sentiment bars, report tabs, evidence audio and loading/error/empty states.
- `src/pages/`: landing, dashboard, report, evidence and evaluation views.
- `src/hooks/useCallData.ts`: loads the report, claims and transcript; retains separate errors for unavailable supporting data.
- `src/lib/api.ts`: typed API client and audio URLs.
- `src/lib/format.ts`: date, timestamp and percentage formatting.

Manrope and DM Serif Display are loaded through Google Fonts, with system and serif fallbacks. Speaker labels are not supplied by the backend and are not invented in the interface. A **Citation matched** badge describes text matching near a timestamp, not independent validation of a claim's meaning.

## Build and check

```bash
npm run build
npm run lint
```

The build type-checks TypeScript and writes the production bundle to `dist/`. Lint uses Oxlint. A persistent automated frontend test suite is not currently configured in this package.

## Deployment

Use `frontend` as the Vercel root directory, `npm run build` as the build command, and `dist` as the output directory.

Set `VITE_API_BASE_URL` to the backend origin at build time, without a trailing slash or `/api` suffix. Rebuild after changing it. Configure the backend's `ALLOWED_ORIGINS` to include the frontend origin. `vercel.json` rewrites requests to `index.html` for direct React Router links.

The public API serves saved reports in read-only mode. Audio controls require source recordings on that API server; without them, the interface explains that playback is unavailable while retaining text evidence.
