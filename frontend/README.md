# SkyFleet Ops — Frontend

Next.js (App Router, static export) ops-console UI for the SkyFleet Ops drone fleet command center.

## Setup

```bash
npm install
npm run dev   # http://localhost:3000, expects the backend running on :8000 for /api/* proxying in dev
```

`npm run build` produces a static export in `out/`, which the Docker build copies into the backend image as `static/` (see `../docker/Dockerfile`).

## Layout

```
src/
├── app/            # App Router: layout, page, global styles
├── components/      # Header, ConnectionDot, FleetRosterPanel (implemented)
├── lib/             # useTelemetryStream — SSE client hook
└── types/           # TypeScript mirrors of backend telemetry models
```

## Status

The live telemetry stream (roster grid + connection indicator) is wired up against the real backend SSE endpoint. Chart panels (heatmap, budget chart), the mission dispatch bar, and the AI chat panel are specified in `../planning/PLAN.md` sections 8-10 but not yet built.

## Design tokens

Dark ops-console theme, defined in `tailwind.config.ts`:

- `ops-bg` `#0a0e14` — page background
- `ops-panel` `#12161f` — card/panel background
- `ops-border` `#232a38` — hairline borders
- `ops-amber` `#f2a900` — primary accent
- `ops-teal` `#17a2b8` — secondary accent / live data
- `ops-signal` `#e8622c` — dispatch/launch actions
