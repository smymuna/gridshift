from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, field_validator

from gridshift.domain.models import IntensitySeries, Window

Zone = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{2}$", to_lower=True)]

ATTRIBUTION = "Carbon intensity data: Energy-Charts.info, Fraunhofer ISE"


class ScheduleRequest(BaseModel):
    zones: list[Zone] = Field(
        min_length=1,
        max_length=10,
        description="Zones the job may run in, in order of preference. "
        "The first one is used as the run-now baseline.",
        examples=[["de", "fr", "nl"]],
    )
    duration_minutes: int = Field(gt=0, le=2880, examples=[120])
    deadline: AwareDatetime | None = Field(
        default=None,
        description="Latest time the job must finish. Defaults to the end of the forecast.",
    )
    power_kw: float | None = Field(
        default=None,
        gt=0,
        le=100_000,
        description="Average power draw of the job. If set, emissions are returned in grams.",
        examples=[0.4],
    )

    @field_validator("zones")
    @classmethod
    def _unique(cls, zones: list[str]) -> list[str]:
        if len(set(zones)) != len(zones):
            raise ValueError("zones must be unique")
        return zones


class WindowOut(BaseModel):
    zone: str
    start: datetime
    end: datetime
    avg_gco2_per_kwh: float
    uses_forecast: bool
    emissions_g: float | None = None

    @classmethod
    def from_domain(cls, w: Window, power_kw: float | None) -> WindowOut:
        emissions = None
        if power_kw is not None:
            hours = (w.end - w.start).total_seconds() / 3600
            emissions = round(w.avg_gco2_per_kwh * power_kw * hours, 1)
        return cls(
            zone=w.zone,
            start=w.start,
            end=w.end,
            avg_gco2_per_kwh=round(w.avg_gco2_per_kwh, 1),
            uses_forecast=w.uses_forecast,
            emissions_g=emissions,
        )


class ScheduleResponse(BaseModel):
    recommended: WindowOut
    run_now: WindowOut | None = Field(
        description="Starting immediately in the first zone. Null if the data does not cover it."
    )
    savings_pct: float | None
    emissions_saved_g: float | None
    delay_minutes: int
    attribution: str = ATTRIBUTION


class PointOut(BaseModel):
    start: datetime
    gco2_per_kwh: float
    is_forecast: bool


class IntensityResponse(BaseModel):
    zone: str
    resolution_minutes: int
    fetched_at: datetime
    points: list[PointOut]
    attribution: str = ATTRIBUTION

    @classmethod
    def from_domain(cls, s: IntensitySeries, since: datetime | None) -> IntensityResponse:
        return cls(
            zone=s.zone,
            resolution_minutes=int(s.resolution.total_seconds() // 60),
            fetched_at=s.fetched_at,
            points=[
                PointOut(start=p.start, gco2_per_kwh=p.gco2_per_kwh, is_forecast=p.is_forecast)
                for p in s.points
                if since is None or p.start + s.resolution > since
            ],
        )
