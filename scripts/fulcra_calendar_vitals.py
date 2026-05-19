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

def main():
    parser = argparse.ArgumentParser(description="Fetch calendar events aligned with heart rate time series data.")
    parser.add_argument("--hours", type=int, default=24, help="Time range in hours (default: 24)")
    parser.add_argument("--include-all-day", action="store_true", help="Include all-day events")
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

        aligned_events = []
        for event in events:
            start_date = event.get('start_date')
            end_date = event.get('end_date')
            is_all_day = event.get('is_all_day', False)
            cal_id = event.get('calendar_id')
            
            event['calendar_name'] = cal_map.get(cal_id, 'Unknown Calendar')

            if not args.include_all_day and is_all_day:
                continue

            if not start_date or not end_date:
                aligned_events.append(event)
                continue

            # Sample rate is 1s for normal, 30m (1800s) for all-day events to prevent overload
            sample_rate = 1800 if is_all_day else 1

            hr_series = service.get_metric_time_series(
                start_date, end_date, "HeartRate", 
                sample_rate=sample_rate, agg_function="mean"
            )

            # Assign directly as it matches align.sh output `. + {heart_rate_series: hr}`
            event['heart_rate_series'] = hr_series
            aligned_events.append(event)

        print(json.dumps(aligned_events, indent=2, default=str))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
