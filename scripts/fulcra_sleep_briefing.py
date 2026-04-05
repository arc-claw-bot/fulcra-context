#!/usr/bin/env python3
"""
Pre-computed Fulcra Sleep Briefing — Always Ready

Runs every 2 hours via cron. Pulls last night's sleep + 7-day trends + 
biometric context and generates a comprehensive, demo-quality analysis 
using LLM. Saves to a file that can be instantly read when asked
"how did I sleep?"

This is a reference implementation for comprehensive sleep analysis
using Fulcra data streams.
"""

import json
import logging
import os
import sys
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Add scripts dir to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from fulcra_sleep_utils import get_fulcra_client, get_last_night_sleep, get_sleep_history
from fulcra_timezone import now_local, today_local, get_user_tz

logger = logging.getLogger(__name__)

def _user_tz():
    """Get user timezone object for constructing date boundaries. NEVER use timezone.utc for local dates."""
    try:
        tz_name = get_user_tz()
        if tz_name:
            return ZoneInfo(tz_name)
    except Exception:
        pass
    return ZoneInfo("America/New_York")  # Fallback

ET = get_user_tz()

# Output directory - configurable via environment
OUTPUT_DIR = Path(os.environ.get('FULCRA_OUTPUT_DIR', Path.home() / '.openclaw/data/fulcra-analysis'))
OUTPUT_FILE = OUTPUT_DIR / "sleep-briefing-latest.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LLM endpoint - configurable via environment
LLM_ENDPOINT = os.environ.get('LLM_ENDPOINT', 'http://localhost:18789/v1/chat/completions')
LLM_MODEL = os.environ.get('LLM_MODEL', 'openclaw')  # Default to OpenClaw gateway

# Context files - configurable via environment
CONTEXT_DIR = Path(os.environ.get('CONTEXT_DIR', Path.home() / '.openclaw/memory/topics'))
CONTEXT_FILE = CONTEXT_DIR / "biometric-context.md"
SUPPLEMENTS_FILE = CONTEXT_DIR / "supplements.md"


def get_llm_token():
    """Get LLM API token from OpenClaw config or environment."""
    token = os.environ.get('LLM_API_TOKEN')
    if token:
        return token
    
    try:
        with open(os.path.expanduser("~/.openclaw/openclaw.json")) as f:
            config = json.load(f)
        return config.get("gateway", {}).get("auth", {}).get("token", "")
    except:
        return ""


def fetch_hrv_rhr(client, days=7):
    """Fetch HRV and RHR data."""
    results = {"hrv": [], "rhr": []}
    today = today_local()
    
    for metric_name, metric_key in [
        ("HeartRateVariabilitySDNN", "hrv"),
        ("RestingHeartRate", "rhr")
    ]:
        try:
            start = datetime(today.year, today.month, today.day, tzinfo=_user_tz()) - timedelta(days=days)
            end = datetime(today.year, today.month, today.day, tzinfo=_user_tz()) + timedelta(days=1)
            df = client.metric_samples(start.isoformat(), end.isoformat(), metric_name)
            if hasattr(df, 'iterrows') and len(df) > 0:
                for _, row in df.iterrows():
                    val = row.get('value', row.get('avg', None))
                    date_str = str(row.get('start_date', row.get('start_time', '')))[:10]
                    if val is not None:
                        results[metric_key].append({
                            "date": date_str,
                            "value": round(float(val), 1)
                        })
        except Exception as e:
            logger.debug(f"Failed to fetch {metric_name}: {e}")
    
    return results


def fetch_hr_overnight(client):
    """Fetch overnight heart rate curve."""
    try:
        today = today_local()
        # Last night: 8 PM yesterday to 8 AM today
        start = datetime(today.year, today.month, today.day, tzinfo=_user_tz()) - timedelta(hours=12)
        end = datetime(today.year, today.month, today.day, tzinfo=_user_tz()) + timedelta(hours=12)
        
        df = client.metric_samples(start.isoformat(), end.isoformat(), "HeartRate")
        if hasattr(df, 'iterrows') and len(df) > 0:
            readings = []
            for _, row in df.iterrows():
                val = row.get('value', row.get('avg'))
                ts = str(row.get('start_date', row.get('start_time', '')))
                if val:
                    readings.append({"time": ts, "bpm": round(float(val))})
            
            if readings:
                bpms = [r["bpm"] for r in readings]
                return {
                    "min_bpm": min(bpms),
                    "max_bpm": max(bpms),
                    "avg_bpm": round(sum(bpms) / len(bpms)),
                    "readings_count": len(readings),
                    "readings": readings[-20:]  # Last 20 for summary
                }
    except Exception as e:
        logger.debug(f"HR overnight fetch failed: {e}")
    return None


def fetch_calendar_data(client):
    """Fetch yesterday's calendar (what preceded sleep) + today's calendar (what's ahead).
    This is a basic implementation - you may need to customize based on your calendar setup."""
    result = {"yesterday": [], "today": [], "yesterday_count": 0, "today_count": 0,
              "yesterday_real_count": 0, "today_real_count": 0}
    today = today_local()
    
    for label, target_date in [("yesterday", today - timedelta(days=1)), ("today", today)]:
        try:
            start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=_user_tz())
            end = start + timedelta(days=1)
            events = client.calendar_events(start.isoformat(), end.isoformat())
            event_list = []
            if hasattr(events, 'iterrows'):
                for _, row in events.iterrows():
                    title = str(row.get('title', row.get('summary', '')))
                    start_time = str(row.get('start_time', row.get('start', '')))
                    # Basic heuristic for "real" meetings - you may want to customize this
                    is_real = bool(title and not any(word in title.lower() for word in ['block', 'focus', 'break']))
                    event_list.append({"title": title, "start": start_time, "real": is_real})
            elif hasattr(events, '__len__'):
                for e in events:
                    if hasattr(e, 'get'):
                        title = e.get('title', e.get('summary', ''))
                        is_real = bool(title and not any(word in title.lower() for word in ['block', 'focus', 'break']))
                        event_list.append({"title": title, "start": str(e.get('start_time', e.get('start', ''))), "real": is_real})
            
            real_meetings = [e for e in event_list if e.get("real")]
            result[label] = event_list[:15]
            result[f"{label}_count"] = len(event_list)
            result[f"{label}_real_count"] = len(real_meetings)
        except Exception as e:
            logger.debug(f"Calendar fetch failed for {label}: {e}")
    
    return result


def fetch_location_data(client):
    """Fetch recent location data from Fulcra to show where sleep happened."""
    try:
        today = today_local()
        # Yesterday evening through this morning
        start = datetime(today.year, today.month, today.day, tzinfo=_user_tz()) - timedelta(hours=14)
        end = datetime(today.year, today.month, today.day, tzinfo=_user_tz()) + timedelta(hours=12)
        
        loc = client.metric_samples(start.isoformat(), end.isoformat(), "LocationSample")
        if hasattr(loc, 'iterrows') and len(loc) > 0:
            # Get the most common location (where they slept)
            lats = [float(row.get('latitude', row.get('value', 0))) for _, row in loc.iterrows() if row.get('latitude') or row.get('value')]
            lons = [float(row.get('longitude', 0)) for _, row in loc.iterrows() if row.get('longitude')]
            if lats and lons:
                return {"lat": round(sum(lats)/len(lats), 4), "lon": round(sum(lons)/len(lons), 4), "samples": len(lats)}
    except Exception as e:
        logger.debug(f"Location fetch failed: {e}")
    
    # Try get_user_info for timezone-based location hint
    try:
        user_info = client.get_user_info()
        if hasattr(user_info, 'get'):
            tz = user_info.get('timezone', '')
            if tz:
                return {"timezone": tz, "inferred": True}
    except:
        pass
    
    return None


def fetch_exercise_data(client):
    """Fetch today's exercise/walk data — steps, walking speed, active energy."""
    result = {"steps": 0, "walking_speed_samples": 0, "walk_detected": False, "walk_times": [], "step_samples": 0}
    today = today_local()
    
    try:
        start = datetime(today.year, today.month, today.day, tzinfo=_user_tz())
        end = start + timedelta(days=1)
        
        # Step count
        try:
            steps = client.metric_samples(start.isoformat(), end.isoformat(), "StepCount")
            if isinstance(steps, list):
                result["steps"] = sum(s.get("value", 0) for s in steps)
                result["step_samples"] = len(steps)
            elif hasattr(steps, 'iterrows'):
                result["steps"] = int(steps["value"].sum()) if "value" in steps.columns else 0
                result["step_samples"] = len(steps)
        except Exception as e:
            logger.debug(f"StepCount fetch failed: {e}")
        
        # Walking speed — presence of samples = walking happened
        try:
            ws = client.metric_samples(start.isoformat(), end.isoformat(), "WalkingSpeed")
            ws_list = ws if isinstance(ws, list) else (list(ws.itertuples(index=False)) if hasattr(ws, 'itertuples') else [])
            result["walking_speed_samples"] = len(ws_list) if hasattr(ws_list, '__len__') else 0
            
            if result["walking_speed_samples"] > 0:
                result["walk_detected"] = True
                # Extract walk times
                for s in (ws_list[:10] if isinstance(ws_list, list) else []):
                    t = s.get("start_date", "") if isinstance(s, dict) else ""
                    if t:
                        result["walk_times"].append(t)
        except Exception as e:
            logger.debug(f"WalkingSpeed fetch failed: {e}")
        
        # If steps > 3000 but no walking speed data, still flag as likely walk
        if result["steps"] > 3000 and not result["walk_detected"]:
            result["walk_detected"] = True
            
    except Exception as e:
        logger.debug(f"Exercise data fetch failed: {e}")
    
    return result


def location_to_context(loc_data):
    """Convert location data to human-readable context."""
    if not loc_data:
        return ""
    
    if loc_data.get("inferred"):
        tz = loc_data.get("timezone", "")
        if "New_York" in tz:
            return "Location: East Coast (from Fulcra timezone data)"
        return f"Location timezone: {tz}"
    
    lat = loc_data.get("lat", 0)
    lon = loc_data.get("lon", 0)
    
    if lat and lon:
        return f"📍 Location: {lat:.2f}°N, {lon:.2f}°W — from Fulcra location data"
    
    return ""


def fetch_annotations_data():
    """Fetch Elemind, coffee, and other annotations from Fulcra for sleep context."""
    try:
        from fulcra_annotations import fetch_annotations
        data = fetch_annotations(days=3)
        
        lines = []
        
        # Coffee — timing matters for sleep
        coffee = data.get("summary", {}).get("coffee", {})
        if coffee:
            lines.append(f"COFFEE (last 3 days): {coffee.get('total_cups', 0)} cups total, avg {coffee.get('avg_per_day', 0)}/day")
            for date, info in sorted(coffee.get("by_date", {}).items()):
                lines.append(f"  {date}: {info['count']} cups at {', '.join(info['times'])}")
            late = coffee.get("late_coffees_after_2pm", [])
            if late:
                lines.append(f"  ⚠️ LATE COFFEES (after 2 PM): {len(late)} — these impact sleep onset and deep sleep")
                for lc in late:
                    lines.append(f"    {lc['date']} at {lc['time']}")
        
        # Sleep Quality (subjective, logged morning after)
        sq = data.get("summary", {}).get("sleep_quality", {})
        if sq:
            lines.append(f"SUBJECTIVE SLEEP QUALITY: avg {sq.get('avg_value', '?')}/5 ({sq.get('entries', 0)} entries)")
            for r in sq.get("readings", []):
                lines.append(f"  {r['date']}: {r['value']}/5 ({r['label']})")
        
        # Dream Intensity
        di = data.get("summary", {}).get("dream_intensity", {})
        if di:
            lines.append(f"DREAM INTENSITY: avg {di.get('avg_value', '?')}/5 ({di.get('entries', 0)} entries)")
            for r in di.get("readings", []):
                lines.append(f"  {r['date']}: {r['value']}/5 ({r['label']})")
        
        # Wake-ups / Sleep Interruptions
        wu = data.get("summary", {}).get("wake_ups", {})
        if wu:
            lines.append(f"SLEEP INTERRUPTIONS (self-reported): avg {wu.get('avg', '?')}/night")
            for date, count in sorted(wu.get("by_date", {}).items()):
                lines.append(f"  {date}: {count} wake-ups")
        
        # Nocturia
        nc = data.get("summary", {}).get("nocturia", {})
        if nc:
            lines.append(f"NOCTURIA (woke to pee): avg {nc.get('avg', '?')}/night")
            for date, count in sorted(nc.get("by_date", {}).items()):
                lines.append(f"  {date}: {count} times")
        
        # Evening medications — bedtime supplement stack timing
        evening_meds = data.get("summary", {}).get("evening_medications", {})
        if evening_meds:
            lines.append(f"EVENING MEDICATIONS (bedtime stack): Taken {evening_meds.get('nights_taken', 0)} of last 3 nights")
            for date, time in sorted(evening_meds.get("times", {}).items()):
                lines.append(f"  {date}: taken at {time}")
        
        # Elemind — sleep device usage
        elemind = data.get("summary", {}).get("elemind", {})
        if elemind:
            lines.append(f"ELEMIND (neurostim headband): Used {elemind.get('nights_used', 0)} of last 3 nights")
            lines.append(f"  Dates: {', '.join(elemind.get('dates', []))}")
        
        # Morning pills — timing regularity matters
        pills = data.get("summary", {}).get("morning_pills", {})
        if pills:
            lines.append(f"MORNING PILLS: {pills.get('days_taken', 0)} days logged, median time {pills.get('avg_time', '?')}")
        
        # Mood — subjective state
        mood = data.get("summary", {}).get("mood", {})
        if mood:
            lines.append(f"MOOD: avg {mood.get('avg_value', '?')}/5 ({mood.get('entries', 0)} entries)")
            for r in mood.get("readings", []):
                lines.append(f"  {r['date']}: {r['value']}/5 ({r['label']})")
        
        # Semaglutide
        sema = data.get("semaglutide", [])
        if sema:
            lines.append(f"MEDICATION INJECTION: {len(sema)} logged — dates: {', '.join(s['date'] for s in sema)}")
        
        return "\n".join(lines) if lines else ""
    except Exception as e:
        logger.warning(f"Annotation fetch failed (non-fatal): {e}")
        return ""


def load_context():
    """Load biometric context and supplements info."""
    context_text = ""
    try:
        if CONTEXT_FILE.exists():
            text = CONTEXT_FILE.read_text()
            # Extract key sections only (not full file — too long)
            sections = []
            for section_name in ["Medications & Supplements", "Active Theories", "Key Correlations", "Personal Baselines"]:
                idx = text.find(f"## {section_name}")
                if idx >= 0:
                    next_section = text.find("\n## ", idx + 1)
                    sections.append(text[idx:next_section if next_section > 0 else idx + 1000][:500])
            context_text = "\n".join(sections)
    except Exception:
        pass
    return context_text[:2000]  # Cap at 2K chars


def generate_briefing_text(data):
    """Use LLM to generate the demo-quality briefing."""
    token = get_llm_token()
    if not token:
        return None
    
    # Build the data summary for the prompt
    last_night = data.get("last_night", {})
    history = data.get("history", [])
    hrv_data = data.get("hrv", [])
    rhr_data = data.get("rhr", [])
    hr_curve = data.get("hr_overnight", {})
    context = data.get("context", "")
    
    if last_night.get("status") != "ok":
        return "Sleep data not yet synced from Apple Watch. Check back after your watch connects."
    
    # Format 7-night trend table
    trend_lines = []
    for night in history[:7]:
        trend_lines.append(
            f"  {night['date']}: {night['total_sleep_h']}h, "
            f"deep {night['deep_pct']:.0f}%, REM {night['rem_pct']:.0f}%, "
            f"eff {night['efficiency']:.0f}%, bed {night.get('bedtime_str','?')}"
        )
    trend_text = "\n".join(trend_lines) if trend_lines else "No trend data"
    
    # HRV/RHR summary
    hrv_text = ", ".join([f"{h['date']}: {h['value']}ms" for h in hrv_data[-7:]]) if hrv_data else "No HRV data"
    rhr_text = ", ".join([f"{r['date']}: {r['value']}bpm" for r in rhr_data[-7:]]) if rhr_data else "No RHR data"
    
    # HR curve
    hr_text = ""
    if hr_curve:
        hr_text = f"Overnight HR: min {hr_curve['min_bpm']}bpm, max {hr_curve['max_bpm']}bpm, avg {hr_curve['avg_bpm']}bpm"
    
    # Calendar data — use REAL meeting counts (excluding time blocks)
    cal = data.get("calendar", {})
    yesterday_events = cal.get("yesterday", [])
    today_events = cal.get("today", [])
    yesterday_real = cal.get("yesterday_real_count", 0)
    today_real = cal.get("today_real_count", 0)
    yesterday_cal = f"Yesterday's calendar ({yesterday_real} real meetings, {cal.get('yesterday_count', 0)} total calendar entries):\n"
    yesterday_cal += "  REAL MEETINGS (count these for cognitive load):\n"
    for e in yesterday_events[:15]:
        marker = "✅" if e.get("real") else "⬜ [Block/focus time]"
        yesterday_cal += f"  {marker} {e.get('title', 'Unknown')} (at {e.get('start', '?')})\n"
    today_cal = f"Today's calendar ({today_real} real meetings, {cal.get('today_count', 0)} total calendar entries):\n"
    today_cal += "  REAL MEETINGS (count these for cognitive load):\n"
    for e in today_events[:15]:
        marker = "✅" if e.get("real") else "⬜ [Block/focus time]"
        today_cal += f"  {marker} {e.get('title', 'Unknown')} (at {e.get('start', '?')})\n"
    
    # Location data
    loc = data.get("location")
    loc_text = location_to_context(loc) if loc else "Location: not available"
    
    # Exercise/walk data
    exercise = data.get("exercise", {})
    exercise_text = ""
    if exercise.get("walk_detected"):
        walk_times_str = ""
        if exercise.get("walk_times"):
            walk_times_str = f" Walk detected at: {', '.join(exercise['walk_times'][:3])}"
        exercise_text = f"TODAY'S EXERCISE (from Fulcra):\n- Steps: {exercise.get('steps', 0):,}\n- Walking detected: YES ({exercise.get('walking_speed_samples', 0)} speed samples){walk_times_str}\n- This may be morning exercise/walk. Correlate walk timing with sleep quality."
    elif exercise.get("steps", 0) > 0:
        exercise_text = f"TODAY'S EXERCISE (from Fulcra):\n- Steps so far: {exercise.get('steps', 0):,}\n- No dedicated walk detected yet"
    else:
        exercise_text = "TODAY'S EXERCISE: No data synced yet"
    
    # Annotations (coffee, Elemind, pills, mood)
    annotations = data.get("annotations", "")
    annotations_block = ""
    if annotations:
        annotations_block = f"\nANNOTATIONS (from Fulcra — user-logged events):\n{annotations}\n"
    
    # Day of week context
    now = now_local()
    day_name = now.strftime("%A")
    date_str = now.strftime("%B %d, %Y")
    
    prompt = f"""You are an AI health assistant. Analyze last night's sleep data objectively.

TONE: Calm, factual, like a good coach reviewing game tape. Data first, then brief interpretation.
FORMAT: 8-12 lines total. Lead with key numbers, end with one actionable insight.
HEADER: "Sleep Brief — {day_name}, {date_str}" (use exact date provided).
NO melodrama, hyperbole, or wellness-speak. Just useful analysis.

REQUIRED: Must cross-reference sleep with at least one other data stream (subjective sleep quality, dream intensity, wake-up count, coffee timing, Elemind usage, evening meds, calendar load, exercise timing) to show data connections. Compare subjective sleep quality rating vs objective metrics (deep%, REM%, efficiency). If there's a mismatch (felt bad but metrics ok, or vice versa), call it out — that's the insight. If Elemind was used, note whether it correlated with better/worse deep sleep. If late coffee was logged, flag the impact. If nocturia was high, connect to sleep fragmentation.

DATA SUMMARY:
Sleep: {last_night.get('total_sleep_h', '?')}h total, {last_night.get('bedtime_str', '?')} bedtime
Stages: {last_night.get('deep_pct', 0):.0f}% deep, {last_night.get('rem_pct', 0):.0f}% REM, {last_night.get('efficiency', 0):.0f}% efficiency  
7-day trend: {', '.join([f"{n['date']}: {n['total_sleep_h']}h" for n in history[-3:]]) if history else "No trend data"}
HRV: {', '.join([f"{h['value']}ms" for h in hrv_data[-3:]]) if hrv_data else "No data"}
Calendar load: Yesterday {cal.get('yesterday_real_count', 0)} meetings, today {cal.get('today_real_count', 0)} meetings
Exercise: {exercise.get('steps', 0):,} steps{',' if exercise.get('walk_detected') else ', no walk detected'}
{' morning walk detected' if exercise.get('walk_detected') else ''}
{annotations_block}
CONTEXT: Optimal bedtime varies by individual. Sleep hygiene factors include room temperature, light exposure, caffeine timing, exercise timing, and stress levels. Evening Medications = bedtime supplement stack (timing relative to bed matters).

Generate brief analysis connecting sleep quality to coffee/evening meds/calendar/exercise patterns. What should be adjusted tonight?"""

    try:
        resp = requests.post(LLM_ENDPOINT, json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600,
            "temperature": 0.3
        }, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }, timeout=90)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"LLM briefing generation failed: {e}")
        return None


def run():
    """Generate and save the pre-computed sleep briefing."""
    logger.info("Generating sleep briefing...")
    
    try:
        client = get_fulcra_client()
    except Exception as e:
        logger.error(f"Fulcra auth failed: {e}")
        return None
    
    # Gather all data
    last_night = get_last_night_sleep(client)
    history = get_sleep_history(client, days=7)
    biometrics = fetch_hrv_rhr(client, days=7)
    hr_overnight = fetch_hr_overnight(client)
    calendar = fetch_calendar_data(client)
    location = fetch_location_data(client)
    exercise = fetch_exercise_data(client)
    context = load_context()
    annotations = fetch_annotations_data()
    
    data = {
        "last_night": last_night,
        "history": history,
        "hrv": biometrics.get("hrv", []),
        "rhr": biometrics.get("rhr", []),
        "hr_overnight": hr_overnight,
        "calendar": calendar,
        "location": location,
        "exercise": exercise,
        "context": context,
        "annotations": annotations
    }
    
    # Generate the briefing text
    briefing_text = generate_briefing_text(data)
    
    # Build the output
    now = now_local()
    output = {
        "generated_at": now.isoformat(),
        "generated_at_human": now.strftime("%I:%M %p %Z on %A, %B %d"),
        "generated_date": str(now.date()),  # YYYY-MM-DD for staleness checks
        "night_of": str((now - timedelta(days=1)).date()) if now.hour < 12 else str(now.date()),
        "status": last_night.get("status", "error"),
        "briefing": briefing_text,
        "data": {
            "last_night": last_night,
            "history": [
                {
                    "date": n.get("date"),
                    "total_h": n.get("total_sleep_h"),
                    "deep_pct": n.get("deep_pct"),
                    "rem_pct": n.get("rem_pct"),
                    "efficiency": n.get("efficiency"),
                    "bedtime": n.get("bedtime_str"),
                    "wake": n.get("wake_str")
                }
                for n in history
            ],
            "hrv": biometrics.get("hrv", []),
            "rhr": biometrics.get("rhr", []),
            "hr_overnight": hr_overnight
        }
    }
    
    # Write atomically — JSON (full data) + TXT (briefing only for instant read)
    tmp = str(OUTPUT_FILE) + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    os.rename(tmp, str(OUTPUT_FILE))
    
    # Plain text briefing — this is what gets read for instant response
    # CRITICAL: Never overwrite a good briefing with a failed one
    txt_file = OUTPUT_DIR / "sleep-briefing.txt"
    if briefing_text:
        tmp_txt = str(txt_file) + ".tmp"
        with open(tmp_txt, 'w') as f:
            # Machine-readable header for staleness detection
            f.write(f"<!-- generated_date={now.date()} generated_at={now.isoformat()} -->\n")
            f.write(briefing_text)
        os.rename(tmp_txt, str(txt_file))
    else:
        logger.warning("LLM returned null — keeping previous briefing.txt intact")
    
    logger.info(f"Sleep briefing saved: {OUTPUT_FILE}")
    logger.info(f"Status: {last_night.get('status')}, Generated at: {output['generated_at_human']}")
    
    if briefing_text:
        logger.info(f"Briefing preview: {briefing_text[:150]}...")
    
    # Pre-render accurate sleep chart with matplotlib
    try:
        from sleep_chart import create_chart
        chart_path = str(OUTPUT_DIR / "sleep-briefing-chart.png")
        create_chart(output, chart_path)
        logger.info(f"Sleep chart generated: {chart_path}")
    except Exception as e:
        logger.warning(f"Sleep chart generation failed (non-fatal): {e}")
    
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run()
    if result and result.get("briefing"):
        print(f"\n{'='*60}")
        print(f"🛌 Sleep Briefing — {result['generated_at_human']}")
        print(f"{'='*60}")
        print(result["briefing"])
    else:
        print("Failed to generate briefing")