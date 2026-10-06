from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from gridshift.adapters.energy_charts import UpstreamUnavailableError, ZoneNotFoundError
from gridshift.api.app import create_app, utc_now
from gridshift.config import Settings
from gridshift.domain.models import IntensitySeries
from gridshift.services.intensity import IntensityService
from tests.conftest import QUARTER, T0, make_series

SERIES = {
    "de": make_series([700, 650, 600, 600, 650, 700, 720, 710], zone="de", forecast_from=2),
    "fr": make_series([60, 55, 50, 48, 52, 58, 61, 63], zone="fr", forecast_from=2),
}


class StubProvider:
    async def fetch_intensity(self, zone: str) -> IntensitySeries:
        if zone == "zz":
            raise UpstreamUnavailableError("Energy-Charts returned HTTP 503 after 3 retries")
        if zone not in SERIES:
            raise ZoneNotFoundError(f"no carbon intensity data for zone {zone!r}")
        return SERIES[zone]


@pytest.fixture
def client() -> Iterator[TestClient]:
    def factory(_: httpx.AsyncClient, __: Settings) -> IntensityService:
        return IntensityService(StubProvider())

    app = create_app(Settings(), service_factory=factory)
    app.dependency_overrides[utc_now] = lambda: T0
    with TestClient(app) as c:
        yield c


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json()["status"] == "ok"


def test_intensity_hides_past_points_by_default(client: TestClient) -> None:
    body = client.get("/v1/intensity/DE").json()
    assert body["zone"] == "de"
    assert body["resolution_minutes"] == 15
    assert len(body["points"]) == 8
    assert "Fraunhofer" in body["attribution"]


def test_schedule_shifts_to_cleaner_zone(client: TestClient) -> None:
    r = client.post(
        "/v1/schedule",
        json={"zones": ["de", "fr"], "duration_minutes": 30, "power_kw": 2.0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["recommended"]["zone"] == "fr"
    assert body["recommended"]["avg_gco2_per_kwh"] == 49.0
    assert body["recommended"]["uses_forecast"] is True
    assert body["run_now"]["zone"] == "de"
    assert body["run_now"]["avg_gco2_per_kwh"] == 675.0
    # 2 kW for 0.5 h = 1 kWh, so emissions in g equal the average intensity
    assert body["recommended"]["emissions_g"] == 49.0
    assert body["emissions_saved_g"] == 626.0
    assert body["savings_pct"] == 92.7
    assert body["delay_minutes"] == 30


def test_schedule_respects_explicit_deadline(client: TestClient) -> None:
    deadline = (T0 + 2 * QUARTER).isoformat()
    r = client.post(
        "/v1/schedule", json={"zones": ["de"], "duration_minutes": 30, "deadline": deadline}
    )
    assert r.status_code == 200
    assert r.json()["delay_minutes"] == 0


def test_schedule_without_power_omits_grams(client: TestClient) -> None:
    body = client.post("/v1/schedule", json={"zones": ["fr"], "duration_minutes": 15}).json()
    assert body["recommended"]["emissions_g"] is None
    assert body["emissions_saved_g"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"zones": [], "duration_minutes": 30},
        {"zones": ["deu"], "duration_minutes": 30},
        {"zones": ["de", "DE"], "duration_minutes": 30},
        {"zones": ["de"], "duration_minutes": 0},
        {"zones": ["de"], "duration_minutes": 30, "deadline": "2026-10-04T10:00:00"},
    ],
    ids=["no-zones", "bad-code", "duplicate", "zero-duration", "naive-deadline"],
)
def test_schedule_validation(client: TestClient, payload: dict[str, object]) -> None:
    assert client.post("/v1/schedule", json=payload).status_code == 422


def test_job_longer_than_forecast_is_problem_422(client: TestClient) -> None:
    r = client.post("/v1/schedule", json={"zones": ["de"], "duration_minutes": 600})
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["title"] == "No feasible window"


def test_unknown_zone_is_problem_404(client: TestClient) -> None:
    r = client.get("/v1/intensity/xx")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"


def test_upstream_outage_is_problem_503(client: TestClient) -> None:
    r = client.post("/v1/schedule", json={"zones": ["zz"], "duration_minutes": 15})
    assert r.status_code == 503
    assert r.json()["title"] == "Data provider unavailable"


def test_deadline_in_past_is_422(client: TestClient) -> None:
    deadline = (T0 - timedelta(hours=1)).isoformat()
    r = client.post(
        "/v1/schedule", json={"zones": ["de"], "duration_minutes": 15, "deadline": deadline}
    )
    assert r.status_code == 422


def test_zones_are_listed_by_name(client: TestClient) -> None:
    zones = client.get("/v1/zones").json()
    names = [z["name"] for z in zones]
    assert names == sorted(names)
    assert {"code": "de", "name": "Germany"} in zones


def test_cors_allows_the_configured_frontend_only() -> None:
    app = create_app(Settings(cors_origins=["https://ui.example"]))
    with TestClient(app) as c:
        ok = c.get("/healthz", headers={"Origin": "https://ui.example"})
        other = c.get("/healthz", headers={"Origin": "https://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "https://ui.example"
    assert "access-control-allow-origin" not in other.headers


def test_openapi_export_is_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from gridshift.openapi import main

    main()
    spec = json.loads(capsys.readouterr().out)
    assert "/v1/schedule" in spec["paths"]
    assert "/v1/zones" in spec["paths"]
