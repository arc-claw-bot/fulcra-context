#!/usr/bin/env python3
"""Fetch upcoming calendar events from Fulcra API."""
import json, os, sys, argparse
from datetime import datetime, timezone, timedelta

parser = argparse.ArgumentParser()
parser.add_argument("--hours", type=int, default=2)
args = parser.parse_args()

TOKEN_PATH = os.path.expanduser("~/.config/fulcra/token.json")
try:
    with open(TOKEN_PATH) as f:
        token_data = json.load(f)
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)

try:
    from fulcra_api.core import FulcraAPI
    api = FulcraAPI()
    api.fulcra_cached_access_token = token_data["access_token"]
    api.fulcra_cached_access_token_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=args.hours)
    events = api.calendar_events(now.isoformat(), end.isoformat())
    print(json.dumps(events or [], indent=2, default=str))
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
