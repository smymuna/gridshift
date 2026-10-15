"""Last known good grid data that survives restarts.

The API keeps grid data in memory, and a free host wipes memory and disk on every restart
(Render's free plan restarts the service each time it wakes from sleep). So if Energy-Charts
is down right after a restart, stale-on-error has nothing to serve.

A scheduled GitHub Actions job therefore saves every zone's latest Energy-Charts payload
once an hour and publishes it on GitHub Pages. When Energy-Charts fails and the API has
nothing cached, ``SnapshotFallback`` serves that copy instead of an error. A zone that
fails during the hourly run keeps its previous entry, so one outage never erases the copy.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from gridshift.adapters.energy_charts import ProviderError, UpstreamDataError, parse_co2eq
from gridshift.domain.models import IntensitySeries

log = logging.getLogger(__name__)

VERSION = 1
_KEEP = ("unix_seconds", "co2eq", "co2eq_forecast")  # all parse_co2eq needs


class PayloadSource(Protocol):
    async def fetch_payload(self, zone: str) -> dict[str, Any]: ...


async def build_snapshot(
    source: PayloadSource,
    zones: Iterable[str],
    *,
    previous: dict[str, Any] | None,
    now: datetime,
) -> tuple[dict[str, Any], list[str]]:
    """Fetch every zone; keep the previous entry for zones that fail. Returns the
    snapshot and the zones that failed this time."""
    entries: dict[str, Any] = {}
    if previous and previous.get("version") == VERSION:
        entries.update(previous.get("zones", {}))
    failed = []
    for zone in zones:
        try:
            payload = await source.fetch_payload(zone)
            trimmed = {k: payload[k] for k in _KEEP if k in payload}
            parse_co2eq(zone, trimmed, fetched_at=now)  # never publish what we can't read back
        except ProviderError as exc:
            log.warning("snapshot: keeping the previous copy of zone=%s (%s)", zone, exc)
            failed.append(zone)
            continue
        entries[zone] = {"fetched_at": now.isoformat(), "payload": trimmed}
    return {"version": VERSION, "generated_at": now.isoformat(), "zones": entries}, failed


def series_from_snapshot(snapshot: dict[str, Any], zone: str) -> IntensitySeries | None:
    entry = snapshot.get("zones", {}).get(zone) if snapshot.get("version") == VERSION else None
    if entry is None:
        return None
    try:
        fetched_at = datetime.fromisoformat(entry["fetched_at"])
        return parse_co2eq(zone, entry["payload"], fetched_at=fetched_at)
    except (KeyError, TypeError, ValueError, UpstreamDataError):
        log.warning("snapshot entry for zone=%s is unreadable", zone)
        return None


class SnapshotFallback:
    """Reads the published snapshot when Energy-Charts is down.

    The file is downloaded at most once per ``refresh_s`` (it changes hourly), and entries
    older than ``max_age_s`` are not served: past the forecast horizon they are useless.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        url: str,
        *,
        max_age_s: float,
        refresh_s: float = 600.0,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._http = http
        self._url = url
        self._max_age_s = max_age_s
        self._refresh_s = refresh_s
        self._clock = clock
        self._now = now
        self._data: dict[str, Any] | None = None
        self._next_load = 0.0
        self._lock = asyncio.Lock()

    async def get(self, zone: str) -> IntensitySeries | None:
        snapshot = await self._load()
        series = series_from_snapshot(snapshot, zone) if snapshot else None
        if series is None:
            return None
        age_s = (self._now() - series.fetched_at).total_seconds()
        if age_s > self._max_age_s:
            log.warning("snapshot for zone=%s is %.0f h old, not serving it", zone, age_s / 3600)
            return None
        return series

    async def _load(self) -> dict[str, Any] | None:
        async with self._lock:  # one download even if many zones ask at once
            if self._clock() < self._next_load:
                return self._data
            self._next_load = self._clock() + self._refresh_s
            try:
                response = await self._http.get(self._url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("could not load the fallback snapshot: %s", exc)
                return self._data  # keep whatever was loaded before
            if isinstance(data, dict):
                self._data = data
            return self._data
