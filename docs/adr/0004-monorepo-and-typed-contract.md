# ADR 0004: Turborepo monorepo with a generated, typed API contract

- Status: accepted
- Date: 2026-10-06

## Context

GridShift gained a web app. The API is Python (FastAPI); the web app is TypeScript
(Next.js). Two things go wrong easily in that setup: the frontend's idea of the API
drifts from the real API, and running "the whole thing" locally needs several
commands in several folders.

## Decision

- **One repository, Turborepo, npm workspaces.** `apps/api`, `apps/web` and
  `packages/api-client` are workspaces. Turborepo runs `dev`, `lint`, `typecheck`,
  `test` and `build` across all of them, in parallel, with caching. npm instead of
  pnpm, so a clone only needs Node and Python.
- **Python joins the task graph through a thin `package.json`.** Its scripts call
  `scripts/py.sh`, which creates or refreshes `apps/api/.venv` when `pyproject.toml`
  changes, so `npm run dev` works right after cloning.
- **The API defines the contract.** Pydantic models → `openapi.json` →
  `openapi-typescript` → `schema.d.ts`, wrapped by a small `openapi-fetch` client.
  The web app is type-checked against the real request and response shapes.
- **Generated files are committed** and CI regenerates them and fails on any diff.
  Vercel can then build the web app without Python, and a contract change shows up
  in code review.

## Consequences

- Changing a response model without regenerating the client fails CI, not production.
- Two toolchains stay in one repo: Python lint/type/test (ruff, mypy, pytest) and
  TypeScript (Biome, tsc, Vitest), both behind the same `npm run check`.
- The API still ships alone (Docker image built from `apps/api`), so the frontend and
  backend can be deployed separately (Vercel and Render).
