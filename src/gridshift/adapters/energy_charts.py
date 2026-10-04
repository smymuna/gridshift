"""Client for the public Energy-Charts API (Fraunhofer ISE).

Endpoint used: ``GET /co2eq?country=<code>``. It returns parallel arrays of unix
timestamps, measured intensity (``co2eq``) and forecast intensity (``co2eq_forecast``) in
gCO2eq/kWh at 15-minute resolution. For each timestamp at most one of the two values is
set; the rest are null.
"""

from __future__ import annotations

import asyncio
import email.utils
import itertools
import logging
import time
from collections import Counter
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from gridshift.domain.models import IntensityPoint, IntensitySeries

log = logging.getLogger(__name__)

Sleep = Callable[[float], Coroutine[Any, Any, None]]


class ProviderError(Exception):
    """Base class for upstream data problems."""


class ZoneNotFoundError(ProviderError):
    """The provider has no data for this zone."""


class UpstreamUnavailableError(ProviderError):
    """The provider failed or kept rate limiting us after all retries."""


class UpstreamDataError(ProviderError):
    """The provider answered, but the payload is not in the expected shape."""


def parse_co2eq(zone: str, payload: dict[str, Any], *, fetched_at: datetime) -> IntensitySeries:
    """Merge measured and forecast values into one series. Measured values win."""
    try:
        ts: list[int] = payload["unix_seconds"]
        actual: list[float | None] = payload.get("co2eq") or [None] * len(ts)
        forecast: list[float | None] = payload.get("co2eq_forecast") or [None] * len(ts)
    except (KeyError, TypeError) as exc:
        raise UpstreamDataError(f"unexpected co2eq payload for {zone!r}") from exc
    if not (len(ts) == len(actual) == len(forecast)):
        raise UpstreamDataError(
            f"co2eq arrays differ in length for {zone!r}: {len(ts)}/{len(actual)}/{len(forecast)}"
        )
    if len(ts) < 2:
        raise UpstreamDataError(f"too few points for {zone!r} to infer resolution")

    # Most common step, so one missing timestamp does not change the resolution.
    step_s, _ = Counter(b - a for a, b in itertools.pairwise(ts)).most_common(1)[0]
    if step_s <= 0:
        raise UpstreamDataError(f"timestamps for {zone!r} are not increasing")

    points = []
    for t, a, f in zip(ts, actual, forecast, strict=True):
        value, is_forecast = (a, False) if a is not None else (f, True)
        if value is None:
            continue
        points.append(
            IntensityPoint(
                start=datetime.fromtimestamp(t, tz=UTC),
                gco2_per_kwh=float(value),
                is_forecast=is_forecast,
            )
        )
    return IntensitySeries(
        zone=zone,
        resolution=timedelta(seconds=step_s),
        points=tuple(points),
        fetched_at=fetched_at,
    )


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


class EnergyChartsClient:
    """Fetches carbon intensity series. Retries 429 and 5xx with exponential backoff."""

    RETRYABLE = frozenset({429, 500, 502, 503, 504})
    # The API answers 400 "'xx' is not the code for an available country" for unknown
    # countries. Country is the only parameter we send, so 400/404 mean "unknown zone".
    ZONE_NOT_FOUND = frozenset({400, 404})

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        max_retries: int = 3,
        backoff_base_s: float = 1.0,
        max_backoff_s: float = 30.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._http = http
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._max_backoff_s = max_backoff_s
        self._sleep = sleep

    async def fetch_intensity(self, zone: str) -> IntensitySeries:
        response = await self._get("/co2eq", params={"country": zone})
        if response.status_code in self.ZONE_NOT_FOUND:
            raise ZoneNotFoundError(f"no carbon intensity data for zone {zone!r}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamDataError(f"invalid JSON for zone {zone!r}") from exc
        if not isinstance(payload, dict):
            raise UpstreamDataError(f"unexpected co2eq payload for {zone!r}")
        return parse_co2eq(zone, payload, fetched_at=datetime.now(UTC))

    async def _get(self, path: str, *, params: dict[str, str]) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            started = time.perf_counter()
            try:
                response = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise UpstreamUnavailableError(f"Energy-Charts unreachable: {exc}") from exc
                delay = self._backoff(attempt, None)
                log.warning(
                    "energy-charts %s transport error (%s), retry in %.1fs", path, exc, delay
                )
                await self._sleep(delay)
                continue

            elapsed_ms = (time.perf_counter() - started) * 1000
            log.info(
                "energy-charts GET %s %s -> %d in %.0fms",
                path, params, response.status_code, elapsed_ms,
            )  # fmt: skip
            if response.status_code not in self.RETRYABLE:
                if response.status_code >= 400 and response.status_code not in self.ZONE_NOT_FOUND:
                    raise UpstreamUnavailableError(
                        f"Energy-Charts returned HTTP {response.status_code}"
                    )
                return response
            if attempt == self._max_retries:
                raise UpstreamUnavailableError(
                    f"Energy-Charts returned HTTP {response.status_code} "
                    f"after {self._max_retries} retries"
                )
            delay = self._backoff(attempt, _retry_after_seconds(response))
            log.warning(
                "energy-charts %s HTTP %d, retry %d/%d in %.1fs",
                path, response.status_code, attempt + 1, self._max_retries, delay,
            )  # fmt: skip
            await self._sleep(delay)
        raise AssertionError("unreachable")

    def _backoff(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, self._max_backoff_s)
        return min(self._backoff_base_s * float(2**attempt), self._max_backoff_s)
