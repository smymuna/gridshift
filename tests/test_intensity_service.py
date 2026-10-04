from __future__ import annotations

import asyncio

import pytest

from gridshift.adapters.energy_charts import UpstreamUnavailableError
from gridshift.domain.models import IntensitySeries
from gridshift.services.intensity import IntensityService
from tests.conftest import make_series


class FakeProvider:
    def __init__(self, *, delay: float = 0.0, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.delay = delay
        self.fail = fail

    async def fetch_intensity(self, zone: str) -> IntensitySeries:
        self.calls.append(zone)
        await asyncio.sleep(self.delay)
        if self.fail:
            raise UpstreamUnavailableError("down")
        return make_series([100, 200], zone=zone)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_caches_within_ttl_and_refetches_after() -> None:
    provider, clock = FakeProvider(), FakeClock()
    service = IntensityService(provider, ttl_s=60, clock=clock)

    await service.get("de")
    clock.now += 59
    await service.get("de")
    assert provider.calls == ["de"]

    clock.now += 2
    await service.get("de")
    assert provider.calls == ["de", "de"]


async def test_concurrent_requests_share_one_fetch() -> None:
    provider = FakeProvider(delay=0.05)
    service = IntensityService(provider)
    results = await asyncio.gather(*(service.get("fr") for _ in range(20)))
    assert provider.calls == ["fr"]
    assert all(r is results[0] for r in results)


async def test_failures_are_not_cached() -> None:
    provider = FakeProvider(fail=True)
    service = IntensityService(provider)
    for _ in range(2):
        with pytest.raises(UpstreamUnavailableError):
            await service.get("de")
    assert provider.calls == ["de", "de"]


async def test_get_many_keeps_order() -> None:
    service = IntensityService(FakeProvider())
    result = await service.get_many(["nl", "de", "fr"])
    assert [s.zone for s in result] == ["nl", "de", "fr"]


async def test_cancelled_caller_does_not_cancel_shared_fetch() -> None:
    provider = FakeProvider(delay=0.05)
    service = IntensityService(provider)
    first = asyncio.create_task(service.get("de"))
    second = asyncio.create_task(service.get("de"))
    await asyncio.sleep(0.01)
    first.cancel()
    assert (await second).zone == "de"
    assert provider.calls == ["de"]
