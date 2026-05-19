#!/usr/bin/env python3
"""Correlate upcoming calendar events from Fulcra with high-resolution heart rate time series data."""
import json
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from fulcra_data_service import get_service
except ImportError:
    print(json.dumps({"error": "Could not import fulcra_data_service."}))
    sys.exit(1)

def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _sample_rate_for_window(start_dt, end_dt, is_all_day=False):
    if is_all_day or not start_dt or not end_dt:
        return 1800
    duration_seconds = max(0, int((end_dt - start_dt).total_seconds()))
    if duration_seconds > 12 * 3600:
        return 1800
    if duration_seconds > 3 * 3600:
        return 300
    return 60


def main():
    parser = argparse.ArgumentParser(description="Fetch calendar events aligned with health metric time series data.")
    parser.add_argument("--hours", type=int, default=24, help="Time range in hours (default: 24)")
    parser.add_argument("--include-all-day", action="store_true", help="Include all-day events")
    parser.add_argument("--metric", type=str, default="HeartRate", help="Health metric ID from catalog (e.g. HeartRate, HeartRateVariabilitySDNN)")
    args = parser.parse_args()

    service = get_service()

    # We use a past time range for testing, since future events won't have heart rate data.
    # To keep it standard with the previous align.sh (which defaults to "1 day" -> usually past 24h)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)

    try:
        events = service.get_calendar_events(start.isoformat(), end.isoformat())
        if not events:
            print(json.dumps([]))
            return

        calendars = service.get_calendars()
        cal_map = {c.get('calendar_id'): c.get('calendar_name', 'Unknown Calendar') for c in calendars}

        range_start = start
        range_end = end
        aligned_events = []
        for event in events:
            start_date = event.get('start_date')
            end_date = event.get('end_date')
            is_all_day = event.get('is_all_day', False)
            cal_id = event.get('calendar_id')
            calendar_name = cal_map.get(cal_id, 'Unknown Calendar')

            if not args.include_all_day and is_all_day:
                continue

            if not start_date or not end_date:
                continue

            event_start = _parse_dt(start_date)
            event_end = _parse_dt(end_date)
            if not event_start or not event_end:
                continue

            window_start = max(event_start, range_start)
            window_end = min(event_end, range_end)
            if window_end <= window_start:
                continue

            sample_rate = _sample_rate_for_window(window_start, window_end, is_all_day)

            metric_series = service.get_metric_time_series(
                window_start.isoformat(), window_end.isoformat(), args.metric,
                sample_rate=sample_rate, agg_function="mean"
            )

            # Deliberately do not echo full calendar records: they may contain
            # notes, locations, attendee data, video links, and external IDs.
            aligned_events.append({
                "title": event.get("title", "Untitled"),
                "calendar_name": calendar_name,
                "start_date": start_date,
                "end_date": end_date,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "is_all_day": bool(is_all_day),
                "sample_rate": sample_rate,
                "metric": args.metric,
                "metric_series": metric_series,
            })

        print(json.dumps(aligned_events, indent=2, default=str))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
