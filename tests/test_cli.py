from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import respx

from gridshift import cli
from gridshift.cli import main, parse_deadline, parse_duration


@pytest.mark.parametrize(
    ("text", "expected"),
    [("90m", timedelta(minutes=90)), ("2h", timedelta(hours=2)), ("1H30m", timedelta(minutes=90))],
)
def test_parse_duration(text: str, expected: timedelta) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "0m", "1.5h", "30s"])
def test_parse_duration_rejects(text: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_duration(text)


def test_parse_deadline_requires_timezone() -> None:
    assert parse_deadline("2026-10-05T06:00Z").utcoffset() == timedelta(0)
    with pytest.raises(argparse.ArgumentTypeError, match="timezone"):
        parse_deadline("2026-10-05T06:00")


@respx.mock
def test_schedule_command_end_to_end(
    fr_payload: dict[str, Any], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get("https://api.energy-charts.info/co2eq").respond(json=fr_payload)
    # Pretend "now" is inside the captured fixture: 5 minutes into its second hour.
    first = datetime.fromtimestamp(fr_payload["unix_seconds"][0], tz=UTC)
    monkeypatch.setattr(cli, "utc_now", lambda: first + timedelta(hours=1, minutes=5))

    assert main(["schedule", "--zone", "FR", "--duration", "1h"]) == 0
    out = capsys.readouterr().out
    assert "Recommended : FR" in out
    assert "(forecast)" in out  # the cleanest French hours are in the forecast part
    assert "Run now     : FR" in out
    assert "Savings" in out


@respx.mock
def test_schedule_command_reports_upstream_errors(capsys: pytest.CaptureFixture[str]) -> None:
    respx.get("https://api.energy-charts.info/co2eq").respond(404)
    assert main(["schedule", "--zone", "xx", "--duration", "1h"]) == 1
    assert "no carbon intensity data" in capsys.readouterr().err
