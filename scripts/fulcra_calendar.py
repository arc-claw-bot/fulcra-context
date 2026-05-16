#!/usr/bin/env python3
"""Fetch upcoming calendar events from Fulcra through the CLI-first service."""
import json, sys, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

parser = argparse.ArgumentParser()
parser.add_argument("--hours", type=int, default=2)
args = parser.parse_args()

try:
    from fulcra_data_service import get_service
    
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=args.hours)
    events = get_service().get_calendar_events(now.isoformat(), end.isoformat())
    print(json.dumps(events or [], indent=2, default=str))
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
