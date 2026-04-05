"""
Shared sleep data utility for all Fulcra scripts.

PERMANENT FIX for the UTC date selection problem:

Fulcra's sleep_agg API returns data bucketed by UTC calendar day.
Each bucket contains the COMPLETE night (not a partial). The bucket
for a given UTC date contains the sleep session that ENDED on that
UTC calendar day.

Example: Sleep 11 PM ET Mar 5 → 6 AM ET Mar 6
  = Sleep 4 AM UTC Mar 6 → 11 AM UTC Mar 6
  → All data is in the Mar 6 UTC bucket (complete, not split)

THE BUG: Using `datetime.now(utc).date()` as the target. This works
at 7:30 AM ET (= 12:30 PM UTC Mar 6 → Mar 6 ✓) but BREAKS at
8 PM ET (= 1 AM UTC Mar 7 → Mar 7 ✗, no sleep data yet).

THE FIX: Always use today's date in ET, then use that as the UTC
period date. "Last night's sleep" = today's ET date = the UTC bucket
where that sleep session lives.

Every script that needs sleep data should use get_last_night_sleep() from here.
DO NOT call sleep_agg directly in other scripts.
"""

import json
import pandas as pd
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

from fulcra_timezone import get_user_tz, now_local, today_local, to_local, format_local_time


# ET is now dynamic — fetched from Fulcra user profile, handles DST automatically
# Kept as a property for backward compatibility with scripts that reference ET directly
@property
def _et():
    return get_user_tz()

# For backward compat: scripts that do `from fulcra_sleep_utils import ET`
# This will be set on first use
ET = get_user_tz()

# Apple HealthKit sleep stage values:
# 0 = InBed, 1 = Asleep (unspecified), 2 = Awake, 3 = Core, 4 = Deep, 5 = REM
STAGE_NAMES = {2: 'awake', 3: 'core', 4: 'deep', 5: 'rem'}


def get_fulcra_client():
    """Get authenticated Fulcra API client."""
    from fulcra_api.core import FulcraAPI
    api = FulcraAPI()
    td = json.load(open('~/.config/fulcra/token.json'))
    api.set_cached_access_token(td['access_token'])
    api.set_cached_refresh_token(td['refresh_token'])
    return api


def _get_target_utc_date(for_date=None):
    """
    Get the correct UTC period date for "last night's sleep."
    
    The key insight: today's date in ET IS the UTC period date where
    last night's sleep data lives. This works because:
    - Sleep 11 PM ET Mar 5 → 6 AM ET Mar 6 lands in UTC Mar 6 bucket
    - On Mar 6 in ET (any time of day), we want that Mar 6 bucket
    - Using today's ET date (not current UTC date) avoids the PM bug
    
    Args:
        for_date: Optional date object (ET date). Defaults to today ET.
    """
    if for_date is not None:
        return for_date
    return today_local()


def get_last_night_sleep(client=None, target_date=None):
    """
    Get last night's sleep data using sleep_cycles (primary) for accurate
    total duration, with sleep_agg for stage breakdown details.
    
    IMPORTANT: sleep_cycles.total_time_asleep_ms is the authoritative
    sleep duration — it matches what Apple Health reports. Manually
    summing stage durations from sleep_agg undercounts by ~20% because
    it misses transitional periods between stages.
    
    Args:
        client: FulcraAPI instance (created if None)
        target_date: date object (ET date for the morning after sleep).
                     Defaults to today ET. This maps directly to the
                     UTC period bucket containing that night's data.
    
    Returns:
        dict with keys: status, total_sleep_h, stages (dict of minutes),
        deep_pct, rem_pct, frag_pct, frag_label, awake_min, bedtime_str,
        wake_str, efficiency, sleep_start, sleep_end
    """
    if client is None:
        client = get_fulcra_client()
    
    target = _get_target_utc_date(target_date)
    
    # Query window: target date ± 2 days to handle sync delays
    start = datetime(target.year, target.month, target.day,
                     tzinfo=timezone.utc) - timedelta(days=2)
    end = datetime(target.year, target.month, target.day,
                   tzinfo=timezone.utc) + timedelta(days=2)
    
    start_iso = start.isoformat()
    end_iso = end.isoformat()
    
    # --- Primary: sleep_cycles for authoritative duration ---
    cycles_data = None
    try:
        cycles_df = client.sleep_cycles(start_iso, end_iso)
        if hasattr(cycles_df, 'iterrows') and len(cycles_df) > 0:
            # Find the cycle whose start_time falls on the target night
            # Target night = evening before target date (ET) through morning of target date
            target_evening_utc = datetime(target.year, target.month, target.day,
                                          tzinfo=timezone.utc) - timedelta(hours=8)
            target_morning_utc = datetime(target.year, target.month, target.day,
                                          tzinfo=timezone.utc) + timedelta(hours=14)
            
            for _, row in cycles_df.iterrows():
                st = pd.to_datetime(row.get('start_time'))
                if st and target_evening_utc <= st.to_pydatetime().replace(tzinfo=timezone.utc) <= target_morning_utc:
                    cycles_data = row
                    break
            
            # NO FALLBACK: if no cycle matches the target window, cycles_data stays None.
            # Previously this fell back to the most recent cycle, which caused stale
            # data to be reported as current when the watch hadn't synced yet.
    except Exception:
        pass  # Fall through to sleep_agg
    
    # --- Secondary: sleep_agg for stage breakdown ---
    try:
        df = client.sleep_agg(start_iso, end_iso)
    except Exception as e:
        if cycles_data is None:
            return {"status": "error", "error": str(e)}
        df = pd.DataFrame()  # Empty — we'll use cycles_data only
    
    # Parse stage details from sleep_agg
    stages = {}
    stage_sleep_ms = 0  # Sum of stage durations (deep+core+rem)
    awake_ms = 0
    sleep_start = None
    sleep_end = None
    
    if hasattr(df, 'iterrows') and len(df) > 0:
        df['period_date'] = pd.to_datetime(df['period_start_time']).dt.date
        night = df[df['period_date'] == target]
        
        # NO FALLBACK to older dates. If today's data isn't here, it means
        # the watch hasn't synced yet. Return no_data instead of stale data.
        # Previously this fell back to the latest available date, which caused
        # the same night's data to be reported on multiple mornings.
        
        for _, row in night.iterrows():
            stage = int(row['value'])
            ms = float(row.get('sum_ms', 0) or 0)
            name = STAGE_NAMES.get(stage, f'stage_{stage}')
            stages[name] = stages.get(name, 0) + round(ms / 60000, 1)
            
            if stage in (3, 4, 5):  # core, deep, rem = actual sleep stages
                stage_sleep_ms += ms
                min_start = str(row.get('min_start_time', ''))
                max_end = str(row.get('max_end_time', ''))
                if min_start and min_start != 'nan' and (not sleep_start or min_start < sleep_start):
                    sleep_start = min_start
                if max_end and max_end != 'nan' and (not sleep_end or max_end > sleep_end):
                    sleep_end = max_end
            elif stage == 2:  # awake
                awake_ms += ms
    
    # --- Determine authoritative total sleep duration ---
    # Prefer sleep_cycles.total_time_asleep_ms (matches Apple Health)
    # Fall back to summing stages if cycles unavailable
    if cycles_data is not None:
        total_sleep_ms = float(cycles_data.get('total_time_asleep_ms', 0) or 0)
        total_session_ms = float(cycles_data.get('total_time_ms', 0) or 0)
        
        # Use cycles for start/end times if we don't have them from agg
        if not sleep_start:
            st = cycles_data.get('start_time')
            if st is not None:
                sleep_start = str(st)
        if not sleep_end:
            et = cycles_data.get('end_time')
            if et is not None:
                sleep_end = str(et)
        
        # For awake/fragmentation, prefer sleep_agg stage 5 data (more granular).
        # Only fall back to cycles math if sleep_agg had no awake data.
        if awake_ms == 0 and total_session_ms > 0 and total_sleep_ms > 0:
            awake_ms = total_session_ms - total_sleep_ms
    else:
        total_sleep_ms = stage_sleep_ms
    
    if total_sleep_ms == 0 and stage_sleep_ms == 0:
        return {"status": "no_data"}
    
    total_bed_ms = total_sleep_ms + awake_ms
    total_sleep_h = total_sleep_ms / 3600000
    awake_min = awake_ms / 60000
    frag_pct = (awake_ms / total_bed_ms * 100) if total_bed_ms > 0 else 0
    
    # Stage percentages (based on stage durations, not total sleep)
    # Use stage_sleep_ms for percentage base so they add to ~100%
    pct_base = stage_sleep_ms if stage_sleep_ms > 0 else total_sleep_ms
    deep_ms = stages.get('deep', 0) * 60000
    deep_pct = (deep_ms / pct_base * 100) if pct_base > 0 else 0
    rem_ms = stages.get('rem', 0) * 60000
    rem_pct = (rem_ms / pct_base * 100) if pct_base > 0 else 0
    core_ms = stages.get('core', 0) * 60000
    core_pct = (core_ms / pct_base * 100) if pct_base > 0 else 0
    
    # Efficiency
    efficiency = (total_sleep_ms / total_bed_ms * 100) if total_bed_ms > 0 else 0
    
    # Fragmentation label
    if frag_pct < 10:
        frag_label, emoji = "low", "🟢"
    elif frag_pct < 20:
        frag_label, emoji = "moderate", "🟡"
    elif frag_pct < 30:
        frag_label, emoji = "high", "🟠"
    else:
        frag_label, emoji = "severe", "⚠️"
    
    # Parse bedtime/wake for display
    bedtime_str = ""
    wake_str = ""
    if sleep_start:
        try:
            dt = datetime.fromisoformat(str(sleep_start).replace('Z', '+00:00'))
            bedtime_str = format_local_time(dt)
        except:
            pass
    if sleep_end:
        try:
            dt = datetime.fromisoformat(str(sleep_end).replace('Z', '+00:00'))
            wake_str = format_local_time(dt)
        except:
            pass
    
    return {
        "status": "ok",
        "total_sleep_h": round(total_sleep_h, 1),
        "total_sleep_min": round(total_sleep_ms / 60000),
        "stages": stages,
        "deep_pct": round(deep_pct, 1),
        "rem_pct": round(rem_pct, 1),
        "core_pct": round(core_pct, 1),
        "frag_pct": round(frag_pct, 1),
        "frag_label": frag_label,
        "frag_emoji": emoji,
        "awake_min": round(awake_min),
        "efficiency": round(efficiency, 1),
        "bedtime_str": bedtime_str,
        "wake_str": wake_str,
        "sleep_start": sleep_start,
        "sleep_end": sleep_end,
    }


def get_sleep_history(client=None, days=7):
    """
    Get multiple nights of sleep data.
    
    Returns list of dicts (newest first), one per night.
    Each night uses the ET date (not UTC) as the key.
    """
    if client is None:
        client = get_fulcra_client()
    
    today_et = today_local()
    results = []
    
    for d in range(days):
        target = today_et - timedelta(days=d)
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