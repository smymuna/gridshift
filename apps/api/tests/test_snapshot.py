from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from gridshift.adapters.energy_charts import UpstreamUnavailableError, parse_co2eq
from gridshift.cli import main
from gridshift.domain.models import IntensitySeries
from gridshift.services.intensity import IntensityService
from gridshift.snapshot import SnapshotFallback, build_snapshot, series_from_snapshot
from gridshift.zones import ZONES

NOW = datetime(2026, 10, 15, 1, 0, tzinfo=UTC)
URL = "https://example.test/intensity.json"


class FakeSource:
    def __init__(self, payloads: dict[str, Any], failing: set[str] = frozenset()) -> None:  # type: ignore[assignment]
        self.payloads = payloads
        self.failing = failing

    async def fetch_payload(self, zone: str) -> dict[str, Any]:
        if zone in self.failing:
            raise UpstreamUnavailableError("down")
        payload: dict[str, Any] = self.payloads[zone]
        return payload


async def test_failed_zones_keep_their_previous_copy(fr_payload: dict[str, Any]) -> None:
    previous, _ = await build_snapshot(
        FakeSource({"fr": fr_payload, "de": fr_payload}), ["fr", "de"], previous=None, now=NOW
    )
    later = NOW + timedelta(hours=1)
    snap, failed = await build_snapshot(
        FakeSource({"fr": fr_payload}, failing={"de"}), ["fr", "de"], previous=previous, now=later
    )
    assert failed == ["de"]
    assert snap["zones"]["fr"]["fetched_at"] == later.isoformat()
    assert snap["zones"]["de"]["fetched_at"] == NOW.isoformat()  # not erased by the outage


async def test_unreadable_payloads_are_not_published(fr_payload: dict[str, Any]) -> None:
    snap, failed = await build_snapshot(
        FakeSource({"fr": fr_payload, "de": {"unexpected": True}}), ["fr", "de"],
        previous=None, now=NOW,
    )  # fmt: skip
    assert failed == ["de"]
    assert set(snap["zones"]) == {"fr"}
    # only what the parser needs is stored
    assert set(snap["zones"]["fr"]["payload"]) <= {"unix_seconds", "co2eq", "co2eq_forecast"}


async def test_snapshot_round_trip(fr_payload: dict[str, Any]) -> None:
    snap, _ = await build_snapshot(FakeSource({"fr": fr_payload}), ["fr"], previous=None, now=NOW)
    series = series_from_snapshot(json.loads(json.dumps(snap)), "fr")
    assert series is not None
    assert series.fetched_at == NOW
    original = parse_co2eq("fr", fr_payload, fetched_at=NOW)
    assert series.points == original.points  # nothing lost by trimming and JSON
    assert series_from_snapshot(snap, "de") is None
    assert series_from_snapshot({**snap, "version": 99}, "fr") is None
    broken = {**snap, "zones": {"fr": {"fetched_at": "yesterday", "payload": {}}}}
    assert series_from_snapshot(broken, "fr") is None


@pytest.fixture
async def published(fr_payload: dict[str, Any]) -> dict[str, Any]:
    snap, _ = await build_snapshot(FakeSource({"fr": fr_payload}), ["fr"], previous=None, now=NOW)
    return snap


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@respx.mock
async def test_fallback_downloads_at_most_once_per_refresh(published: dict[str, Any]) -> None:
    route = respx.get(URL).respond(json=published)
    clock = Clock()
    async with httpx.AsyncClient() as http:
        fb = SnapshotFallback(
            http, URL, max_age_s=24 * 3600, refresh_s=600, clock=clock,
            now=lambda: NOW + timedelta(hours=3),
        )  # fmt: skip
        assert (await fb.get("fr")) is not None
        assert (await fb.get("de")) is None  # not in the snapshot
        assert route.call_count == 1
        clock.t += 601
        await fb.get("fr")
        assert route.call_count == 2


@respx.mock
async def test_fallback_refuses_entries_that_are_too_old(published: dict[str, Any]) -> None:
    respx.get(URL).respond(json=published)
    async with httpx.AsyncClient() as http:
        fb = SnapshotFallback(http, URL, max_age_s=3600, now=lambda: NOW + timedelta(hours=2))
        assert await fb.get("fr") is None


@respx.mock
async def test_fallback_keeps_the_last_copy_when_the_download_fails(
    published: dict[str, Any],
) -> None:
    route = respx.get(URL)
    route.side_effect = [httpx.Response(200, json=published), httpx.Response(404)]
    clock = Clock()
    async with httpx.AsyncClient() as http:
        fb = SnapshotFallback(http, URL, max_age_s=24 * 3600, clock=clock, now=lambda: NOW)
        assert await fb.get("fr") is not None
        clock.t += 601
        assert await fb.get("fr") is not None  # 404 now, but the earlier copy is kept


@respx.mock
async def test_fallback_without_any_copy_returns_none() -> None:
    respx.get(URL).respond(503)
    async with httpx.AsyncClient() as http:
        assert await SnapshotFallback(http, URL, max_age_s=3600).get("fr") is None


class DownProvider:
    async def fetch_intensity(self, zone: str) -> IntensitySeries:
        raise UpstreamUnavailableError("Energy-Charts returned HTTP 503 after 3 retries")


class StaticFallback:
    def __init__(self, series: IntensitySeries | None) -> None:
        self.series = series
        self.calls = 0

    async def get(self, zone: str) -> IntensitySeries | None:
        self.calls += 1
        return self.series


async def test_service_serves_the_snapshot_after_a_restart(published: dict[str, Any]) -> None:
    saved = series_from_snapshot(published, "fr")
    fallback = StaticFallback(saved)
    service = IntensityService(DownProvider(), fallback=fallback, fallback_ttl_s=60)
    assert await service.get("fr") is saved
    assert await service.get("fr") is saved  # cached briefly: no second lookup
    assert fallback.calls == 1


async def test_service_still_fails_without_a_snapshot() -> None:
    service = IntensityService(DownProvider(), fallback=StaticFallback(None))
    with pytest.raises(UpstreamUnavailableError):
        await service.get("fr")


@pytest.fixture
def fast_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRIDSHIFT_UPSTREAM_MIN_INTERVAL_S", "0")
    monkeypatch.setenv("GRIDSHIFT_MAX_RETRIES", "0")


@respx.mock
@pytest.mark.usefixtures("fast_upstream")
def test_snapshot_command_writes_every_zone(fr_payload: dict[str, Any], tmp_path: Path) -> None:
    respx.get("https://api.energy-charts.info/co2eq").respond(json=fr_payload)
    out = tmp_path / "site" / "intensity.json"
    assert main(["snapshot", "--out", str(out), "--previous", str(tmp_path / "missing.json")]) == 0
    assert set(json.loads(out.read_text())["zones"]) == set(ZONES)


@respx.mock
@pytest.mark.usefixtures("fast_upstream")
def test_snapshot_command_writes_nothing_when_every_zone_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    respx.get("https://api.energy-charts.info/co2eq").respond(503)
    previous = tmp_path / "previous.json"
    previous.write_text("not json")
    out = tmp_path / "intensity.json"
    assert main(["snapshot", "--out", str(out), "--previous", str(previous)]) == 1
    assert not out.exists()
    assert "unreadable" in capsys.readouterr().err
