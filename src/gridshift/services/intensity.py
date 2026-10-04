"""Intensity lookups with a per-zone TTL cache.

Energy-Charts rate limits aggressively (HTTP 429) and only publishes new values every
15 minutes, so each zone is fetched at most once per TTL. Concurrent requests for the
same zone share one in-flight fetch ("single flight") instead of all calling upstream.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from gridshift.domain.models import IntensitySeries

log = logging.getLogger(__name__)


class IntensityProvider(Protocol):
    async def fetch_intensity(self, zone: str) -> IntensitySeries: ...


@dataclass(slots=True)
class _Entry:
    series: IntensitySeries
    expires_at: float


class IntensityService:
    def __init__(
        self,
        provider: IntensityProvider,
        *,
        ttl_s: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._ttl_s = ttl_s
        self._clock = clock
        self._cache: dict[str, _Entry] = {}
        self._inflight: dict[str, asyncio.Task[IntensitySeries]] = {}

    async def get(self, zone: str) -> IntensitySeries:
        entry = self._cache.get(zone)
        if entry is not None and entry.expires_at > self._clock():
            log.debug("cache hit zone=%s", zone)
            return entry.series

        task = self._inflight.get(zone)
        if task is None:
            task = asyncio.create_task(self._fetch(zone))
            self._inflight[zone] = task
            task.add_done_callback(lambda _: self._inflight.pop(zone, None))
        # shield: one cancelled caller must not cancel the fetch other callers wait on
        return await asyncio.shield(task)

    async def get_many(self, zones: Iterable[str]) -> list[IntensitySeries]:
        """Fetch several zones concurrently, keeping input order. Errors propagate."""
        return list(await asyncio.gather(*(self.get(z) for z in zones)))

    async def _fetch(self, zone: str) -> IntensitySeries:
        series = await self._provider.fetch_intensity(zone)
        self._cache[zone] = _Entry(series, self._clock() + self._ttl_s)
        return series
