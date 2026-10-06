"""Command line entry point.

gridshift schedule --zone de --zone fr --duration 2h --deadline 2026-10-05T06:00Z
gridshift serve --port 8000
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import UTC, datetime, timedelta

import httpx

from gridshift import __version__
from gridshift.adapters.energy_charts import EnergyChartsClient, ProviderError
from gridshift.config import Settings
from gridshift.domain.models import Recommendation, Window
from gridshift.domain.scheduler import NoFeasibleWindowError, recommend

_DURATION = re.compile(r"^(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m)?$")


def parse_duration(text: str) -> timedelta:
    """Parse '90m', '2h' or '1h30m'."""
    match = _DURATION.match(text.strip().lower())
    if not match or not any(match.groupdict().values()):
        raise argparse.ArgumentTypeError(f"invalid duration {text!r}, use e.g. 90m, 2h, 1h30m")
    value = timedelta(hours=int(match["h"] or 0), minutes=int(match["m"] or 0))
    if value <= timedelta(0):
        raise argparse.ArgumentTypeError("duration must be positive")
    return value


def parse_deadline(text: str) -> datetime:
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO 8601 time {text!r}") from exc
    if value.tzinfo is None:
        raise argparse.ArgumentTypeError("deadline needs a timezone, e.g. 2026-10-05T06:00Z")
    return value


def utc_now() -> datetime:
    return datetime.now(UTC)


def _fmt(w: Window) -> str:
    tag = " (forecast)" if w.uses_forecast else ""
    return (
        f"{w.zone.upper()}  {w.start:%a %H:%M} -> {w.end:%H:%M} UTC  "
        f"{w.avg_gco2_per_kwh:6.1f} gCO2/kWh{tag}"
    )


def render(rec: Recommendation) -> str:
    lines = [f"Recommended : {_fmt(rec.best)}"]
    if rec.baseline is not None:
        lines.append(f"Run now     : {_fmt(rec.baseline)}")
    if rec.savings_pct is not None:
        lines.append(f"Savings     : {rec.savings_pct:.1f}% lower carbon intensity")
    lines.append("Data: Energy-Charts.info, Fraunhofer ISE")
    return "\n".join(lines)


async def _schedule(args: argparse.Namespace, settings: Settings) -> Recommendation:
    async with httpx.AsyncClient(
        base_url=str(settings.energy_charts_url), timeout=settings.http_timeout_s
    ) as http:
        client = EnergyChartsClient(http, max_retries=settings.max_retries)
        series = await asyncio.gather(*(client.fetch_intensity(z) for z in args.zone))
    now = utc_now()
    horizons = [s.horizon_end for s in series if s.horizon_end is not None]
    deadline = args.deadline or (max(horizons) if horizons else now)
    return recommend(series, duration=args.duration, now=now, deadline=deadline)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gridshift", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sch = sub.add_parser("schedule", help="find the lowest-carbon window for a job")
    sch.add_argument(
        "--zone", action="append", required=True, type=str.lower,
        help="country code, repeat for several (first one is the default location)",
    )  # fmt: skip
    sch.add_argument("--duration", type=parse_duration, required=True, help="e.g. 90m, 2h")
    sch.add_argument("--deadline", type=parse_deadline, help="ISO 8601, default: end of forecast")

    srv = sub.add_parser("serve", help="run the HTTP API")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    level = settings.log_level if args.command == "serve" else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "serve":
        import uvicorn

        uvicorn.run("gridshift.main:app", host=args.host, port=args.port)
        return 0

    try:
        rec = asyncio.run(_schedule(args, settings))
    except (ProviderError, NoFeasibleWindowError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
