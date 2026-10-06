from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx

from gridshift.adapters.energy_charts import (
    EnergyChartsClient,
    UpstreamDataError,
    UpstreamUnavailableError,
    ZoneNotFoundError,
    parse_co2eq,
)

BASE = "https://api.energy-charts.info"
NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)


class RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture
def sleep() -> RecordingSleep:
    return RecordingSleep()


async def make_client(sleep: RecordingSleep, **kw: Any) -> EnergyChartsClient:
    return EnergyChartsClient(httpx.AsyncClient(base_url=BASE), sleep=sleep, **kw)


# --- parsing -------------------------------------------------------------------------


def test_parse_real_payload_merges_measured_and_forecast(fr_payload: dict[str, Any]) -> None:
    s = parse_co2eq("fr", fr_payload, fetched_at=NOW)
    assert s.resolution == timedelta(minutes=15)
    assert len(s.points) == 24 + 75  # measured + forecast, trailing nulls dropped
    assert not s.points[0].is_forecast
    assert s.points[0].gco2_per_kwh == pytest.approx(64.8)
    assert s.points[24].is_forecast
    assert s.points[0].start == datetime.fromtimestamp(1791064800, tz=UTC)
    # contiguous: measured data ends exactly where the forecast starts
    assert s.points[24].start - s.points[23].start == s.resolution


def test_measured_value_wins_over_forecast() -> None:
    payload = {"unix_seconds": [0, 900], "co2eq": [100.0, None], "co2eq_forecast": [999.0, 50.0]}
    s = parse_co2eq("de", payload, fetched_at=NOW)
    assert [(p.gco2_per_kwh, p.is_forecast) for p in s.points] == [(100.0, False), (50.0, True)]


def test_resolution_ignores_a_single_missing_timestamp() -> None:
    ts = [0, 900, 1800, 3600, 4500]
    payload = {"unix_seconds": ts, "co2eq": [1.0] * 5, "co2eq_forecast": [None] * 5}
    assert parse_co2eq("de", payload, fetched_at=NOW).resolution == timedelta(minutes=15)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"unix_seconds": [0, 900], "co2eq": [1.0], "co2eq_forecast": [None, None]},
        {"unix_seconds": [0], "co2eq": [1.0], "co2eq_forecast": [None]},
        {"unix_seconds": [900, 0], "co2eq": [1.0, 1.0], "co2eq_forecast": [None, None]},
    ],
    ids=["missing-keys", "length-mismatch", "too-short", "not-increasing"],
)
def test_parse_rejects_malformed_payloads(payload: dict[str, Any]) -> None:
    with pytest.raises(UpstreamDataError):
        parse_co2eq("de", payload, fetched_at=NOW)


# --- HTTP behaviour --------------------------------------------------------------------


@respx.mock
async def test_fetch_ok(fr_payload: dict[str, Any], sleep: RecordingSleep) -> None:
    route = respx.get(f"{BASE}/co2eq", params={"country": "fr"}).respond(json=fr_payload)
    client = await make_client(sleep)
    s = await client.fetch_intensity("fr")
    assert s.zone == "fr"
    assert route.call_count == 1
    assert sleep.calls == []


@respx.mock
async def test_retries_on_429_honouring_retry_after(
    fr_payload: dict[str, Any], sleep: RecordingSleep
) -> None:
    respx.get(f"{BASE}/co2eq").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(503),
            httpx.Response(200, json=fr_payload),
        ]
    )
    client = await make_client(sleep, backoff_base_s=1.0)
    await client.fetch_intensity("fr")
    assert sleep.calls == [7.0, 2.0]  # Retry-After, then exponential 1 * 2**1


@respx.mock
async def test_gives_up_after_max_retries(sleep: RecordingSleep) -> None:
    route = respx.get(f"{BASE}/co2eq").respond(429)
    client = await make_client(sleep, max_retries=2)
    with pytest.raises(UpstreamUnavailableError, match="429"):
        await client.fetch_intensity("de")
    assert route.call_count == 3


@respx.mock
async def test_backoff_is_capped(sleep: RecordingSleep) -> None:
    respx.get(f"{BASE}/co2eq").respond(500)
    client = await make_client(sleep, max_retries=4, backoff_base_s=10, max_backoff_s=25)
    with pytest.raises(UpstreamUnavailableError):
        await client.fetch_intensity("de")
    assert sleep.calls == [10, 20, 25, 25]


@respx.mock
async def test_transport_errors_are_retried(
    fr_payload: dict[str, Any], sleep: RecordingSleep
) -> None:
    respx.get(f"{BASE}/co2eq").mock(
        side_effect=[httpx.ConnectTimeout("boom"), httpx.Response(200, json=fr_payload)]
    )
    client = await make_client(sleep)
    assert (await client.fetch_intensity("fr")).zone == "fr"
    assert len(sleep.calls) == 1


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        # what the live API actually returns for an unknown country (seen 2026-10-04)
        httpx.Response(
            400,
            text="'xx' is not the code for an available country. "
            "Please refer to the API doc for information about available countries",
        ),
        httpx.Response(404, json={"detail": "Not Found"}),
    ],
    ids=["400-unknown-country", "404"],
)
async def test_unknown_zone_maps_to_zone_not_found(
    response: httpx.Response, sleep: RecordingSleep
) -> None:
    route = respx.get(f"{BASE}/co2eq").mock(return_value=response)
    client = await make_client(sleep)
    with pytest.raises(ZoneNotFoundError):
        await client.fetch_intensity("xx")
    assert route.call_count == 1


@respx.mock
async def test_other_4xx_is_not_retried(sleep: RecordingSleep) -> None:
    route = respx.get(f"{BASE}/co2eq").respond(403)
    client = await make_client(sleep)
    with pytest.raises(UpstreamUnavailableError, match="403"):
        await client.fetch_intensity("de")
    assert route.call_count == 1


@respx.mock
async def test_invalid_json_is_a_data_error(sleep: RecordingSleep) -> None:
    respx.get(f"{BASE}/co2eq").respond(200, text="<html>maintenance</html>")
    client = await make_client(sleep)
    with pytest.raises(UpstreamDataError):
        await client.fetch_intensity("de")


@respx.mock
async def test_requests_are_spaced_by_min_interval(fr_payload: dict[str, Any]) -> None:
    respx.get(f"{BASE}/co2eq").respond(json=fr_payload)
    now = [100.0]
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)
        now[0] += s

    client = EnergyChartsClient(
        httpx.AsyncClient(base_url=BASE), min_interval_s=1.5, sleep=fake_sleep, clock=lambda: now[0]
    )
    await client.fetch_intensity("fr")  # first call: no wait
    now[0] += 0.5
    await client.fetch_intensity("de")  # 0.5 s later: waits the remaining 1.0 s
    now[0] += 5
    await client.fetch_intensity("nl")  # long after: no wait
    assert sleeps == [pytest.approx(1.0)]
