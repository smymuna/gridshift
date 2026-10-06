from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gridshift import __version__
from gridshift.adapters.energy_charts import (
    EnergyChartsClient,
    UpstreamDataError,
    UpstreamUnavailableError,
    ZoneNotFoundError,
)
from gridshift.api.schemas import (
    IntensityResponse,
    ScheduleRequest,
    ScheduleResponse,
    WindowOut,
    Zone,
    ZoneOut,
)
from gridshift.config import Settings
from gridshift.domain.scheduler import NoFeasibleWindowError, recommend
from gridshift.services.intensity import IntensityService
from gridshift.zones import ZONES

log = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_service(request: Request) -> IntensityService:
    service: IntensityService = request.app.state.intensity_service
    return service


Service = Annotated[IntensityService, Depends(get_service)]
Now = Annotated[datetime, Depends(utc_now)]


def _problem(status: int, title: str, detail: str) -> JSONResponse:
    """RFC 9457 problem details."""
    return JSONResponse(
        status_code=status,
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
        media_type="application/problem+json",
    )


def create_app(
    settings: Settings | None = None,
    service_factory: Callable[[httpx.AsyncClient, Settings], IntensityService] | None = None,
) -> FastAPI:
    settings = settings or Settings()

    def default_factory(http: httpx.AsyncClient, s: Settings) -> IntensityService:
        client = EnergyChartsClient(
            http, max_retries=s.max_retries, min_interval_s=s.upstream_min_interval_s
        )
        return IntensityService(client, ttl_s=s.cache_ttl_s, max_stale_s=s.cache_max_stale_s)

    factory = service_factory or default_factory

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(
            base_url=str(settings.energy_charts_url),
            timeout=settings.http_timeout_s,
            headers={"User-Agent": f"gridshift/{__version__}"},
        ) as http:
            app.state.intensity_service = factory(http, settings)
            yield

    app = FastAPI(
        title="GridShift",
        version=__version__,
        summary="Carbon-aware scheduling for compute jobs on European power grids.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        max_age=3600,
    )

    @app.exception_handler(ZoneNotFoundError)
    async def _zone_not_found(_: Request, exc: ZoneNotFoundError) -> JSONResponse:
        return _problem(404, "Zone not found", str(exc))

    @app.exception_handler(NoFeasibleWindowError)
    async def _no_window(_: Request, exc: NoFeasibleWindowError) -> JSONResponse:
        return _problem(422, "No feasible window", str(exc))

    @app.exception_handler(UpstreamUnavailableError)
    async def _upstream_down(_: Request, exc: UpstreamUnavailableError) -> JSONResponse:
        log.error("upstream unavailable: %s", exc)
        return _problem(503, "Data provider unavailable", str(exc))

    @app.exception_handler(UpstreamDataError)
    async def _upstream_bad(_: Request, exc: UpstreamDataError) -> JSONResponse:
        log.error("upstream data error: %s", exc)
        return _problem(502, "Bad data from provider", str(exc))

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/zones", tags=["intensity"])
    async def zones() -> list[ZoneOut]:
        """Countries with carbon intensity data, sorted by name."""
        return [ZoneOut(code=c, name=n) for c, n in sorted(ZONES.items(), key=lambda kv: kv[1])]

    @app.get("/v1/intensity/{zone}", tags=["intensity"])
    async def get_intensity(
        zone: Annotated[Zone, Path(description="ISO 3166-1 alpha-2 country code, e.g. de")],
        service: Service,
        now: Now,
        include_past: bool = False,
    ) -> IntensityResponse:
        """Measured and forecast carbon intensity (gCO2eq/kWh) for a zone."""
        series = await service.get(zone)
        return IntensityResponse.from_domain(series, since=None if include_past else now)

    @app.post("/v1/schedule", tags=["schedule"])
    async def schedule(body: ScheduleRequest, service: Service, now: Now) -> ScheduleResponse:
        """Find the lowest-carbon start time and zone that still meets the deadline."""
        series = await service.get_many(body.zones)
        duration = timedelta(minutes=body.duration_minutes)
        horizons = [s.horizon_end for s in series if s.horizon_end is not None]
        deadline = body.deadline or (max(horizons) if horizons else now)

        rec = recommend(series, duration=duration, now=now, deadline=deadline)
        best = WindowOut.from_domain(rec.best, body.power_kw)
        baseline = WindowOut.from_domain(rec.baseline, body.power_kw) if rec.baseline else None
        saved = None
        if best.emissions_g is not None and baseline and baseline.emissions_g is not None:
            saved = round(baseline.emissions_g - best.emissions_g, 1)
        return ScheduleResponse(
            recommended=best,
            run_now=baseline,
            savings_pct=rec.savings_pct,
            emissions_saved_g=saved,
            delay_minutes=int((rec.best.start - now).total_seconds() // 60),
        )

    return app
