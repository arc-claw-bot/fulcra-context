#!/usr/bin/env python3
"""Fulcra Data Watchdog — P0 alert if biometric data goes stale >12h.
Run from cron every 2-4 hours. Writes state to data/fulcra-watchdog-state.json.
Exits 0 = data OK or alert already sent. Exits 1 = STALE, needs escalation."""

import json, datetime, sys, os

STATE_FILE = os.path.expanduser("~/.openclaw/data/fulcra-watchdog-state.json")
TOKEN_FILE = os.path.expanduser("~/.config/fulcra/token.json")
STALE_THRESHOLD_HOURS = 12

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"last_data_seen": None, "alert_sent": False, "last_check": None}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def main():
    from fulcra_api.core import FulcraAPI

    token_data = json.load(open(TOKEN_FILE))
    api = FulcraAPI()
    api.fulcra_cached_access_token = token_data["access_token"]
    api.fulcra_cached_access_token_expiration = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    state = load_state()

    # Check last 24h of HeartRate as the canary metric
    start = (now - datetime.timedelta(hours=24)).isoformat()
    try:
        hr_samples = api.metric_samples(start, now.isoformat(), "HeartRate")
    except Exception as e:
        print(f"API ERROR: {e}")
        # API error is also worth escalating if persistent
        state["last_check"] = now.isoformat()
        state["last_error"] = str(e)
        save_state(state)
        print("STALE — API error, escalate")
        sys.exit(1)

    if hr_samples and len(hr_samples) > 0:
        # Find most recent sample
        latest = max(hr_samples, key=lambda s: s.get("start_date", ""))
        latest_time = latest.get("start_date", "")[:19]
        print(f"OK — {len(hr_samples)} HR samples, latest: {latest_time}")
        state["last_data_seen"] = latest_time
        state["alert_sent"] = False
        state["last_check"] = now.isoformat()
        state.pop("last_error", None)
        save_state(state)
        sys.exit(0)
    else:
        # No data in last 24h — check how long it's been
        hours_since = None
        if state.get("last_data_seen"):
            try:
                last_dt = datetime.datetime.fromisoformat(state["last_data_seen"])
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=datetime.timezone.utc)
                hours_since = (now - last_dt).total_seconds() / 3600
            except:
                pass

        state["last_check"] = now.isoformat()

        if hours_since and hours_since > STALE_THRESHOLD_HOURS:
            if not state.get("alert_sent"):
                print(f"STALE — No data for {hours_since:.0f}h (threshold: {STALE_THRESHOLD_HOURS}h). ESCALATE.")
                state["alert_sent"] = True
                save_state(state)
                sys.exit(1)
            else:
                print(f"STALE — {hours_since:.0f}h, alert already sent")
                save_state(state)
                sys.exit(0)
        elif hours_since:
            print(f"WARNING — No recent data, {hours_since:.0f}h since last sample (under threshold)")
            save_state(state)
            sys.exit(0)
        else:
            print("STALE — No data and no prior state. ESCALATE.")
            state["alert_sent"] = True
            save_state(state)
            sys.exit(1)

if __name__ == "__main__":
    main()