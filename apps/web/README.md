# GridShift web app

Next.js 16 (App Router, React 19, React Compiler), Tailwind CSS 4, TanStack Query.
See the [repository README](../../README.md) for the full picture.

Run it from the repository root with `npm run dev` (starts the API too), or on its own:

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, defaults to http://localhost:8000
npm run dev                  # http://localhost:3000
npm test                     # Vitest + Testing Library
npm run build
```

- `src/hooks/usePlanner.ts`: plan state (mirrored to the URL), queries, debounced scheduling.
- `src/components/IntensityChart.tsx`: the SVG chart, hover and slider exploration, table view.
- `src/lib/series.ts`: the same time-weighted job average the API uses, for the what-if tooltip.
- API types come from `@gridshift/api-client`, generated from the API's OpenAPI schema.
