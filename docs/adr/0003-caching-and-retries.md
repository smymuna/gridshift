# ADR 0003: Per-zone TTL cache, single-flight and retries

- Status: accepted
- Date: 2026-10-04

## Context

Energy-Charts publishes new values every 15 minutes and returns HTTP 429 quickly when
called repeatedly. A burst of API requests for the same zone must not turn into a burst
of upstream calls.

## Decision

- **TTL cache per zone** (`GRIDSHIFT_CACHE_TTL_S`, default 900 s, matching the data
  update interval). Failures are not cached.
- **Single-flight**: concurrent requests for a zone that is not cached await the same
  `asyncio.Task`. The task is wrapped in `asyncio.shield`, so if one client disconnects
  the shared fetch keeps running for the others.
- **Retries** on 429, 5xx and transport errors with exponential backoff (1 s, 2 s, 4 s,
  capped at 30 s). `Retry-After` is honoured when present. Other 4xx errors are not
  retried.

## Consequences

- The cache is in process memory. With several replicas each one fetches separately;
  that is acceptable at this scale (one request per zone per replica per 15 min). A shared
  cache such as Redis is the next step if the service is scaled out.
- Clocks and `sleep` are injected, so the cache and backoff are tested without real waiting.
