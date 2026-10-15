# ADR 0005: An hourly snapshot as the fallback that survives restarts

- Status: accepted
- Date: 2026-10-15

## Context

On launch day (14–15 October 2026) Energy-Charts answered every request with
"503 No server is available to handle this request". Stale-on-error
([ADR 0003](0003-caching-and-retries.md)) could not help: the API keeps data in memory,
and the freshly deployed service had nothing cached yet.

This is not a one-off. Render's free plan restarts the service whenever it wakes from
sleep (after 15 idle minutes), and its disk is ephemeral, so memory *and* local files are
empty after every restart. Saving the cache to a local file would be lost at exactly the
moment it is needed.

## Decision

- A scheduled GitHub Actions workflow (`snapshot.yml`, hourly) runs
  `gridshift snapshot`. It fetches every zone through the normal client (throttling,
  retries), checks that each payload parses, and publishes the raw payloads as
  `intensity.json` on GitHub Pages.
- A zone that fails keeps its entry from the previously published file. If no zone can be
  fetched at all, the command exits non-zero and nothing is deployed, so the last good
  copy stays online during an outage.
- In the API, `IntensityService` asks a `SnapshotFallback` only when the provider fails
  *and* there is no usable cached entry. The snapshot is downloaded at most every
  10 minutes, entries older than 24 hours are not served, and a served snapshot is cached
  for 60 seconds so the provider is retried soon but not on every request.
- The response's `fetched_at` is the snapshot's time, and the web app says "Using saved
  grid data from 14:23 (2 h ago)" when data is older than 45 minutes. Old forecasts are
  never presented as live.

## Alternatives

- **A persistent disk on Render:** not on the free plan.
- **Redis / a managed key-value store:** another account and another moving part for a
  single-instance service. Worth it with several replicas (see Limitations).
- **Committing the snapshot to the repository:** would trigger a redeploy every hour
  (auto-deploy) and fill the history with data commits.

## Consequences

- The fallback depends on GitHub Pages and Actions, which are independent of both
  Energy-Charts and Render.
- After a long outage the snapshot's forecast runs out (most countries forecast 1–2 days
  ahead); the 24-hour limit then turns the fallback off and the API reports the outage.
- GitHub disables scheduled workflows in repositories without activity for 60 days, so
  the workflow needs a push (or a manual run) at least that often.
