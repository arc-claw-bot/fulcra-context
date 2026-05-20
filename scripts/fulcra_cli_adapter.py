#!/usr/bin/env python3
"""Lightweight Fulcra CLI probe used by the data service.

The adapter is intentionally conservative:
- Prefer an explicit CLI command from `FULCRA_CLI_COMMAND` when present.
- Otherwise probe a few common command names on PATH.
- Try a small set of JSON-oriented argument shapes.
- Return `None` when the CLI is absent or does not speak the expected shape.

The data service keeps the existing API-backed fallback, so a missing or
misconfigured CLI does not change current behavior.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Optional


CLI_ENV = "FULCRA_CLI_COMMAND"
CLI_CANDIDATES = ("fulcra-api", "fulcra", "fulcra-cli", "fulcracli")


def _command_parts() -> list[list[str]]:
    explicit = os.environ.get(CLI_ENV, "").strip()
    if explicit:
        return [shlex.split(explicit)]

    # Temporary fallback for POC
    return [shlex.split("uv tool run 'git+https://github.com/fulcradynamics/fulcra-api-python.git@add-cli'")]


def _parse_json_payload(stdout: str) -> Optional[Any]:
    text = stdout.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                json_lines.append(json.loads(stripped))
            except json.JSONDecodeError:
                json_lines = []
                break
        if json_lines:
            return json_lines

        # Some CLIs print banners before JSON. Try the first JSON-looking blob.
        for start, end in (("{", "}"), ("[", "]")):
            begin = text.find(start)
            finish = text.rfind(end)
            if begin != -1 and finish != -1 and finish > begin:
                try:
                    return json.loads(text[begin : finish + 1])
                except json.JSONDecodeError:
                    continue
    return None


def _run_cli(args: list[str]) -> Optional[Any]:
    env = os.environ.copy()

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if proc.returncode != 0:
        return None

    return _parse_json_payload(proc.stdout)


def _extract_list(payload: Any, keys: Iterable[str]) -> Optional[list]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return None


def fetch_metric_samples(start_date: str, end_date: str, metric_name: str) -> Optional[list]:
    """Fetch raw metric samples from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.extend(
            [
                [*base, "get-records", metric_name, start_date, end_date],
            ]
        )

    for args in attempts:
        payload = _run_cli(args)
        samples = _extract_list(payload, ("samples", "data", "items", "results"))
        if samples is not None:
            return samples
    return None


def fetch_metric_time_series(start_date: str, end_date: str, metric_name: str, sample_rate: int = 1, agg_function: str = "mean") -> Optional[list]:
    """Fetch resampled/aggregated metric time series from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.extend(
            [
                [*base, "metric-time-series", "--sample-rate", str(sample_rate), "--agg-function", agg_function, metric_name, start_date, end_date],
            ]
        )

    for args in attempts:
        payload = _run_cli(args)
        series = _extract_list(payload, ("series", "data", "items", "results"))
        if series is not None:
            return series
    return None


def fetch_workouts(start_date: str, end_date: str) -> Optional[list]:
    """Fetch workouts from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.extend(
            [
                [*base, "apple-workouts", start_date, end_date],
            ]
        )

    for args in attempts:
        payload = _run_cli(args)
        workouts = _extract_list(payload, ("workouts", "data", "items", "results"))
        if workouts is not None:
            return workouts
    return None


def fetch_calendar_events(start_date: str, end_date: str) -> Optional[list]:
    """Fetch calendar events from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.extend(
            [
                [*base, "calendar-events", start_date, end_date],
            ]
        )

    for args in attempts:
        payload = _run_cli(args)
        events = _extract_list(payload, ("events", "calendar_events", "data", "items", "results"))
        if events is not None:
            return events
    return None


def fetch_location_updates(start_date: str, end_date: str) -> Optional[list]:
    """Fetch Apple location update records from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.append([*base, "apple-location-updates", start_date, end_date])

    for args in attempts:
        payload = _run_cli(args)
        updates = _extract_list(payload, ("updates", "location_updates", "data", "items", "results"))
        if updates is not None:
            return updates
    return None


def fetch_location_visits(start_date: str, end_date: str) -> Optional[list]:
    """Fetch Apple location visit records from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.append([*base, "apple-location-visits", start_date, end_date])

    for args in attempts:
        payload = _run_cli(args)
        visits = _extract_list(payload, ("visits", "location_visits", "data", "items", "results"))
        if visits is not None:
            return visits
    return None


def fetch_location_time_series(start_date: str, end_date: str, sample_rate: int = 900, reverse_geocode: bool = False) -> Optional[list]:
    """Fetch location time series from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        cmd = [*base, "location-time-series", "--sample-rate", str(sample_rate)]
        if reverse_geocode:
            cmd.append("--reverse-geocode")
        cmd.extend([start_date, end_date])
        attempts.append(cmd)

    for args in attempts:
        payload = _run_cli(args)
        series = _extract_list(payload, ("series", "data", "items", "results"))
        if series is not None:
            return series
    return None


def fetch_calendars() -> Optional[list]:
    """Fetch all calendars from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.extend(
            [
                [*base, "calendars"],
            ]
        )

    for args in attempts:
        payload = _run_cli(args)
        cals = _extract_list(payload, ("calendars", "data", "items", "results"))
        if cals is not None:
            return cals
    return None

def fetch_catalog() -> Optional[list]:
    """Fetch the data catalog from a Fulcra CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.extend(
            [
                [*base, "catalog"],
            ]
        )

    for args in attempts:
        payload = _run_cli(args)
        cat = _extract_list(payload, ("catalog", "data", "items", "results"))
        if cat is not None:
            return cat
    return None

def fetch_library_files(path: str) -> Optional[list]:
    """List files in the Fulcra Library via the CLI file-commands branch."""
    attempts = []
    for base in _command_parts():
        attempts.extend([
            [*base, "file", "list", path],
        ])

    for args in attempts:
        env = os.environ.copy()
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=60,
            )
            if proc.returncode == 0:
                lines = [line.strip() for line in proc.stdout.split('\n') if line.strip()]
                return lines
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def download_library_file(path: str) -> Optional[str]:
    """Download a file from the Fulcra Library via the CLI and return its content as a string."""
    attempts = []
    for base in _command_parts():
        attempts.extend([
            [*base, "file", "download", path, "-"],
        ])

    for args in attempts:
        env = os.environ.copy()
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=60,
            )
            if proc.returncode == 0:
                return proc.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None

def fetch_user_info() -> Optional[dict]:
    """Fetch Fulcra user profile/preferences from a CLI if one is available."""
    attempts = []
    for base in _command_parts():
        attempts.append([*base, "user-info"])

    for args in attempts:
        payload = _run_cli(args)
        if isinstance(payload, dict):
            return payload
    return None
