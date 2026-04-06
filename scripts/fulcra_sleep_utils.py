"""
Shared sleep data utility for all Fulcra scripts.

Uses metric_samples('SleepStage') to get sleep data. Each sample has:
  start_date, end_date, value (2=awake, 3=core, 4=deep, 5=rem)

Sessions are groups of samples with <= 60 min gaps between them.
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

from fulcra_timezone import get_user_tz, now_local, today_local, to_local, format_local_time


# ET is now dynamic — fetched from Fulcra user profile, handles DST automatically
ET = get_user_tz()

# Apple HealthKit sleep stage values:
# 0 = InBed, 1 = Asleep (unspecified), 2 = Awake, 3 = Core, 4 = Deep, 5 = REM
STAGE_NAMES = {2: 'awake', 3: 'core', 4: 'deep', 5: 'rem'}


def get_fulcra_client():
    """Get authenticated Fulcra API client."""
    from fulcra_api.core import FulcraAPI
    api = FulcraAPI()
    token_path = os.path.expanduser('~/.config/fulcra/token.json')
    td = json.loads(open(token_path).read())
    api.fulcra_cached_access_token = td['access_token']
    api.fulcra_cached_access_token_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    return api


def _parse_dt(ts_str):
    ts_str = ts_str.replace('Z', '+00:00')
    ts_str = re.sub(
        r'\.(\d+)([+\-])',
        lambda m: '.' + m.group(1)[:6].ljust(6, '0') + m.group(2),
        ts_str
    )
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_sessions(samples):
    if not samples:
        return []
    sorted_samples = sorted(samples, key=lambda s: s['start_date'])
    sessions = []
    current = []
    for s in sorted_samples:
        if not current:
            current.append(s)
        else:
            try:
                prev_end = _parse_dt(current[-1]['end_date'])
                this_start = _parse_dt(s['start_date'])
                gap_min = (this_start - prev_end).total_seconds() / 60
            except Exception:
                gap_min = 0
            if gap_min > 60:
                sessions.append(current)
                current = [s]
            else:
                current.append(s)
    if current:
        sessions.append(current)
    return sessions


def _compute_session_stats(session):
    stage_mins = defaultdict(float)
    sleep_start = sleep_end = None
    for s in session:
        try:
            sd = _parse_dt(s['start_date'])
            ed = _parse_dt(s['end_date'])
        except Exception:
            continue
        dur = (ed - sd).total_seconds() / 60
        v = int(s.get('value', 0))
        if v in STAGE_NAMES:
            stage_mins[v] += dur
        if sleep_start is None or sd < sleep_start:
            sleep_start = sd
        if sleep_end is None or ed > sleep_end:
            sleep_end = ed
    total_sleep = stage_mins[3] + stage_mins[4] + stage_mins[5]
    awake = stage_mins[2]
    total_bed = total_sleep + awake
    if total_sleep < 30:
        return {"status": "no_data"}
    deep_pct = stage_mins[4] / total_sleep * 100 if total_sleep else 0
    rem_pct = stage_mins[5] / total_sleep * 100 if total_sleep else 0
    core_pct = stage_mins[3] / total_sleep * 100 if total_sleep else 0
    frag_pct = awake / total_bed * 100 if total_bed else 0
    efficiency = total_sleep / total_bed * 100 if total_bed else 0

    # Fragmentation label
    if frag_pct < 10:
        frag_label, frag_emoji = "low", "🟢"
    elif frag_pct < 20:
        frag_label, frag_emoji = "moderate", "🟡"
    elif frag_pct < 30:
        frag_label, frag_emoji = "high", "🟠"
    else:
        frag_label, frag_emoji = "severe", "⚠️"

    # Parse bedtime/wake for display
    bedtime_str = ""
    wake_str = ""
    user_tz = get_user_tz()
    if sleep_start:
        try:
            bedtime_str = format_local_time(sleep_start)
        except Exception:
            pass
    if sleep_end:
        try:
            wake_str = format_local_time(sleep_end)
        except Exception:
            pass

    stages = {STAGE_NAMES[k]: round(v, 1) for k, v in stage_mins.items() if k in STAGE_NAMES}

    return {
        "status": "ok",
        "total_sleep_h": round(total_sleep / 60, 1),
        "total_sleep_min": round(total_sleep),
        "stages": stages,
        "deep_pct": round(deep_pct, 1),
        "rem_pct": round(rem_pct, 1),
        "core_pct": round(core_pct, 1),
        "frag_pct": round(frag_pct, 1),
        "frag_label": frag_label,
        "frag_emoji": frag_emoji,
        "awake_min": round(awake),
        "efficiency": round(efficiency, 1),
        "bedtime_str": bedtime_str,
        "wake_str": wake_str,
        "sleep_start": sleep_start.isoformat() if sleep_start else None,
        "sleep_end": sleep_end.isoformat() if sleep_end else None,
    }


def get_last_night_sleep(client=None, target_date=None):
    """
    Get last night's sleep data using metric_samples('SleepStage').

    Args:
        client: FulcraAPI instance (created if None)
        target_date: date object (local date for the morning after sleep).
                     Defaults to today local.

    Returns:
        dict with keys: status, total_sleep_h, stages (dict of minutes),
        deep_pct, rem_pct, core_pct, frag_pct, frag_label, frag_emoji,
        awake_min, efficiency, bedtime_str, wake_str, sleep_start, sleep_end
    """
    if client is None:
        client = get_fulcra_client()

    user_tz = get_user_tz()

    if target_date is None:
        target_date = today_local()

    # Query ±2 days around target to handle sync delays
    start_dt = datetime(target_date.year, target_date.month, target_date.day,
                        tzinfo=user_tz) - timedelta(days=2)
    end_dt = datetime(target_date.year, target_date.month, target_date.day,
                      tzinfo=user_tz) + timedelta(days=1)

    try:
        raw = client.metric_samples(start_dt.isoformat(), end_dt.isoformat(), 'SleepStage')
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if not raw:
        return {"status": "no_data"}

    sessions = _parse_sessions(raw)

    # Find session ending on target_date (in local timezone)
    for sess in sessions:
        try:
            session_end_local = _parse_dt(sess[-1]['end_date']).astimezone(user_tz)
            if session_end_local.date() == target_date:
                result = _compute_session_stats(sess)
                if result.get("status") == "ok":
                    result["date"] = str(target_date)
                return result
        except Exception:
            continue

    return {"status": "no_data"}


def get_sleep_history(client=None, days=7):
    """
    Get multiple nights of sleep data.

    Returns list of dicts (newest first), one per night.
    Each night uses the local date as the key.
    """
    if client is None:
        client = get_fulcra_client()

    today_dt = today_local()
    results = []

    for d in range(days):
        target = today_dt - timedelta(days=d)
        night = get_last_night_sleep(client, target_date=target)
        if night.get("status") == "ok":
            night["date"] = str(target)
            results.append(night)

    return results


# Quick test when run directly
if __name__ == "__main__":
    print("Testing sleep utility...")
    print(f"Today local: {today_local()}")
    print(f"User timezone: {get_user_tz()}")
    print(f"Current UTC: {datetime.now(timezone.utc).date()}")
    print()

    result = get_last_night_sleep()
    if result["status"] == "ok":
        print(f"Last night: {result['total_sleep_h']}h sleep, {result['efficiency']:.0f}% efficiency")
        print(f"  Deep: {result['stages'].get('deep', 0):.0f}min ({result['deep_pct']:.0f}%)")
        print(f"  Core: {result['stages'].get('core', 0):.0f}min ({result['core_pct']:.0f}%)")
        print(f"  REM: {result['stages'].get('rem', 0):.0f}min ({result['rem_pct']:.0f}%)")
        print(f"  Awake: {result['awake_min']}min ({result['frag_pct']:.0f}%)")
        print(f"  Bedtime: {result['bedtime_str']} → Wake: {result['wake_str']}")
    else:
        print(f"Status: {result}")

    print("\nHistory (last 5 nights):")
    for night in get_sleep_history(days=5):
        print(f"  {night['date']}: {night['total_sleep_h']}h, deep {night['deep_pct']:.0f}%, REM {night['rem_pct']:.0f}%, eff {night['efficiency']:.0f}%")
