# ADR 0001: Energy-Charts as the carbon intensity source

- Status: accepted
- Date: 2026-10-04

## Context

The scheduler needs measured and forecast grid carbon intensity (gCO2eq/kWh) for European
countries, at sub-hourly resolution, at least ~24 h ahead.

Options considered:

| Source | Coverage | Forecast | Access |
|---|---|---|---|
| Electricity Maps | Global | Yes | API key, free tier is limited and non-commercial |
| ENTSO-E Transparency Platform | EU | Generation forecasts only, no intensity | Free token; intensity must be derived from the generation mix |
| National sources (e.g. UK Carbon Intensity API) | One country | Yes | Free |
| **Energy-Charts (Fraunhofer ISE)** | Many European countries | Yes, `co2eq_forecast` | Free, no key |

## Decision

Use the Energy-Charts `/co2eq` endpoint. It gives measured and forecast intensity in one
response at 15-minute resolution and needs no API key, so anyone can run the project.

The client sits behind an `IntensityProvider` protocol (`services/intensity.py`), so a
second source such as Electricity Maps can be added without touching the scheduler.

## Consequences

- The API rate limits aggressively (HTTP 429 with `Retry-After`, seen in testing). This
  forces caching and backoff, see ADR 0003.
- Unknown countries return HTTP 400, not 404. The client maps both to `ZoneNotFoundError`.
- Values are **average** (location-based) intensity per country, not marginal emissions
  and not per bidding zone. That is good enough to compare times and countries, but it is
  not a carbon accounting figure. See "Limitations" in the README.
