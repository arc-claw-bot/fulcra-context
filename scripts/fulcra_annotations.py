#!/usr/bin/env python3
"""
Fetch Fulcra annotations (Coffee, Pills, Supplements, Mood, Elemind, etc.)
and output structured JSON for use in biometric analysis.

Usage:
    python3 scripts/fulcra_annotations.py --days 3 [--json]
"""

import json
import sys
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Add scripts dir to path for shared utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fulcra_timezone import get_user_tz
    LOCAL_TZ = get_user_tz()
except Exception:
    import zoneinfo
    LOCAL_TZ = zoneinfo.ZoneInfo("America/New_York")

def get_api():
    from fulcra_api.core import FulcraAPI
    api = FulcraAPI()
    token_data = json.load(open(os.path.expanduser("~/.config/fulcra/token.json")))
    api.fulcra_cached_access_token = token_data["access_token"]
    exp = token_data.get("expiration")
    if exp:
        api.fulcra_cached_access_token_expiration = datetime.fromisoformat(exp.replace("Z", "+00:00"))
    else:
        api.fulcra_cached_access_token_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    return api


def utc_to_local(ts_str):
    """Convert UTC timestamp string to local datetime."""
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return dt.astimezone(LOCAL_TZ)


def fetch_annotations(days=3):
    api = get_api()
    now = datetime.now(LOCAL_TZ)
    start = now - timedelta(days=days)
    
    results = {
        "period": {
            "start": start.isoformat(),
            "end": now.isoformat(),
            "days": days
        },
        "coffee": [],
        "morning_pills": [],
        "evening_medications": [],
        "semaglutide": [],
        "elemind": [],
        "mood": [],
        "other_moments": [],
        "summary": {}
    }
    
    # Fetch moment annotations (Coffee, Pills, Elemind, Semaglutide, Evening Meds)
    try:
        moments = api.moment_annotations(start.isoformat(), now.isoformat())
        for m in moments:
            # Use metadata.name as canonical name (source_name can be truncated/missing)
            meta = m.get("metadata", {})
            name = (meta.get("name") or m.get("source_name", "")).lower().strip()
            local_time = utc_to_local(m["recorded_at"])
            entry = {
                "timestamp": local_time.strftime("%Y-%m-%d %H:%M"),
                "date": local_time.strftime("%Y-%m-%d"),
                "time": local_time.strftime("%H:%M"),
                "day_of_week": local_time.strftime("%A"),
                "note": m.get("note")
            }
            
            if "coffee" in name:
                results["coffee"].append(entry)
            elif "morning pills" in name or name == "pills":
                results["morning_pills"].append(entry)
            elif "evening" in name and "med" in name:
                results["evening_medications"].append(entry)
            elif "semaglutide" in name:
                results["semaglutide"].append(entry)
            elif "elemind" in name:
                results["elemind"].append(entry)
            else:
                entry["source"] = meta.get("name") or m.get("source_name", "unknown")
                results["other_moments"].append(entry)
    except Exception as e:
        results["errors"] = results.get("errors", [])
        results["errors"].append(f"moment_annotations: {e}")
    
    # Fetch scale annotations (Mood, Sleep Quality, Dream Severity, Edge scales)
    results["sleep_quality"] = []
    results["dream_intensity"] = []
    results["edge_scales"] = []
    try:
        scales = api.scale_annotations(start.isoformat(), now.isoformat())
        for s in scales:
            meta = s.get("metadata") or {}
            name = (meta.get("name") or "unknown").lower().strip()
            local_time = utc_to_local(s["recorded_at"])
            
            # Get human-readable label
            value = s.get("value")
            spec = meta.get("spec") or {}
            scale = spec.get("scale", {})
            label_map = scale.get("label_mapping", {}).get("string", {}).get("mapping", {})
            label = label_map.get(str(value), str(value))
            
            entry = {
                "timestamp": local_time.strftime("%Y-%m-%d %H:%M"),
                "date": local_time.strftime("%Y-%m-%d"),
                "time": local_time.strftime("%H:%M"),
                "day_of_week": local_time.strftime("%A"),
                "value": value,
                "label": label,
                "note": s.get("note")
            }
            
            if name == "mood":
                results["mood"].append(entry)
            elif name == "sleep quality":
                results["sleep_quality"].append(entry)
            elif name in ("dream severity", "dream intensity"):
                results["dream_intensity"].append(entry)
            elif name.startswith("edge"):
                entry["scale_name"] = meta.get("name", "unknown")
                results["edge_scales"].append(entry)
            # Skip 'Good / Bad' and unknown single entries
    except Exception as e:
        results["errors"] = results.get("errors", [])
        results["errors"].append(f"scale_annotations: {e}")
    
    # Fetch numeric annotations (Woke Up, Woke Up to Pee, supplement dosages)
    results["wake_ups"] = []
    results["nocturia"] = []
    results["supplement_doses"] = []
    try:
        nums = api.numeric_annotations(start.isoformat(), now.isoformat())
        for n in nums:
            meta = n.get("metadata") or {}
            name = (meta.get("name") or n.get("source_name", "")).lower().strip()
            local_time = utc_to_local(n["recorded_at"])
            entry = {
                "timestamp": local_time.strftime("%Y-%m-%d %H:%M"),
                "date": local_time.strftime("%Y-%m-%d"),
                "time": local_time.strftime("%H:%M"),
                "value": n.get("value"),
                "note": n.get("note")
            }
            
            if name == "woke up":
                results["wake_ups"].append(entry)
            elif name == "woke up to pee":
                results["nocturia"].append(entry)
            else:
                entry["supplement"] = meta.get("name") or n.get("source_name", "unknown")
                results["supplement_doses"].append(entry)
    except Exception as e:
        results["errors"] = results.get("errors", [])
        results["errors"].append(f"numeric_annotations: {e}")
    
    # Fetch boolean and duration annotations (currently empty but future-proof)
    for annot_type in ["boolean_annotations", "duration_annotations"]:
        try:
            data = getattr(api, annot_type)(start.isoformat(), now.isoformat())
            if data:
                for item in data:
                    local_time = utc_to_local(item["recorded_at"])
                    entry = {
                        "type": annot_type.replace("_annotations", ""),
                        "source": (item.get("metadata") or {}).get("name") or item.get("source_name", "unknown"),
                        "timestamp": local_time.strftime("%Y-%m-%d %H:%M"),
                        "value": item.get("value"),
                        "note": item.get("note")
                    }
                    results["other_moments"].append(entry)
        except Exception:
            pass
    
    # Build summary
    summary = {}
    
    # Coffee summary
    if results["coffee"]:
        by_date = defaultdict(list)
        for c in results["coffee"]:
            by_date[c["date"]].append(c["time"])
        summary["coffee"] = {
            "total_cups": len(results["coffee"]),
            "avg_per_day": round(len(results["coffee"]) / max(len(by_date), 1), 1),
            "by_date": {d: {"count": len(times), "times": sorted(times)} for d, times in sorted(by_date.items())},
            "latest_each_day": {d: max(times) for d, times in by_date.items()},
            "earliest_each_day": {d: min(times) for d, times in by_date.items()}
        }
        # Flag late coffees (after 2 PM)
        late_coffees = [c for c in results["coffee"] if c["time"] >= "14:00"]
        if late_coffees:
            summary["coffee"]["late_coffees_after_2pm"] = [
                {"date": c["date"], "time": c["time"]} for c in late_coffees
            ]
    
    # Pills summary
    if results["morning_pills"]:
        pill_times = [p["time"] for p in results["morning_pills"]]
        summary["morning_pills"] = {
            "days_taken": len(results["morning_pills"]),
            "avg_time": sorted(pill_times)[len(pill_times)//2],  # median
            "times": {p["date"]: p["time"] for p in results["morning_pills"]}
        }
    
    # Evening medications summary
    if results["evening_medications"]:
        summary["evening_medications"] = {
            "nights_taken": len(results["evening_medications"]),
            "times": {e["date"]: e["time"] for e in results["evening_medications"]},
            "dates": [e["date"] for e in results["evening_medications"]]
        }
    
    # Elemind summary
    if results["elemind"]:
        summary["elemind"] = {
            "nights_used": len(results["elemind"]),
            "dates": [e["date"] for e in results["elemind"]]
        }
    
    # Mood summary
    if results["mood"]:
        values = [m["value"] for m in results["mood"] if m["value"] is not None]
        summary["mood"] = {
            "entries": len(results["mood"]),
            "avg_value": round(sum(values) / len(values), 1) if values else None,
            "readings": [{"date": m["date"], "value": m["value"], "label": m["label"]} for m in results["mood"]]
        }
    
    # Sleep Quality summary (subjective, logged morning after)
    if results["sleep_quality"]:
        values = [s["value"] for s in results["sleep_quality"] if s["value"] is not None]
        summary["sleep_quality"] = {
            "entries": len(results["sleep_quality"]),
            "avg_value": round(sum(values) / len(values), 1) if values else None,
            "readings": [{"date": s["date"], "value": s["value"], "label": s["label"]} for s in results["sleep_quality"]]
        }
    
    # Dream Intensity summary
    if results["dream_intensity"]:
        values = [d["value"] for d in results["dream_intensity"] if d["value"] is not None]
        summary["dream_intensity"] = {
            "entries": len(results["dream_intensity"]),
            "avg_value": round(sum(values) / len(values), 1) if values else None,
            "readings": [{"date": d["date"], "value": d["value"], "label": d["label"]} for d in results["dream_intensity"]]
        }
    
    # Wake-up count summary (sleep interruptions)
    if results["wake_ups"]:
        summary["wake_ups"] = {
            "entries": len(results["wake_ups"]),
            "by_date": {w["date"]: w["value"] for w in results["wake_ups"]},
            "avg": round(sum(w["value"] for w in results["wake_ups"]) / len(results["wake_ups"]), 1)
        }
    
    # Nocturia summary (woke up to pee)
    if results["nocturia"]:
        summary["nocturia"] = {
            "entries": len(results["nocturia"]),
            "by_date": {n["date"]: n["value"] for n in results["nocturia"]},
            "avg": round(sum(n["value"] for n in results["nocturia"]) / len(results["nocturia"]), 1)
        }
    
    # Supplement dosage summary
    if results["supplement_doses"]:
        by_supp = defaultdict(list)
        for sd in results["supplement_doses"]:
            by_supp[sd["supplement"]].append({"date": sd["date"], "value": sd["value"]})
        summary["supplement_doses"] = {
            name: {"entries": len(entries), "values": entries}
            for name, entries in sorted(by_supp.items())
        }
    
    results["summary"] = summary
    return results


def format_text(data):
    """Format annotations as human-readable text."""
    lines = []
    lines.append(f"📋 Fulcra Annotations ({data['period']['days']}-day window)")
    lines.append(f"Period: {data['period']['start'][:10]} to {data['period']['end'][:10]}")
    lines.append("")
    
    s = data.get("summary", {})
    
    if "coffee" in s:
        c = s["coffee"]
        lines.append(f"☕ Coffee: {c['total_cups']} cups ({c['avg_per_day']}/day avg)")
        for date, info in sorted(c["by_date"].items()):
            lines.append(f"   {date}: {info['count']} cups at {', '.join(info['times'])}")
        if c.get("late_coffees_after_2pm"):
            lines.append(f"   ⚠️ Late coffees (after 2 PM): {len(c['late_coffees_after_2pm'])} instances")
            for lc in c["late_coffees_after_2pm"]:
                lines.append(f"      {lc['date']} at {lc['time']}")
        lines.append("")
    
    if "morning_pills" in s:
        p = s["morning_pills"]
        lines.append(f"💊 Morning Pills: {p['days_taken']} days logged")
        for date, time in sorted(p["times"].items()):
            lines.append(f"   {date}: {time}")
        lines.append("")
    
    if "evening_medications" in s:
        em = s["evening_medications"]
        lines.append(f"🌙 Evening Medications: {em['nights_taken']} nights logged")
        for date, time in sorted(em["times"].items()):
            lines.append(f"   {date}: {time}")
        lines.append("")
    
    if "elemind" in s:
        e = s["elemind"]
        lines.append(f"🧠 Elemind: {e['nights_used']} nights")
        lines.append(f"   Dates: {', '.join(e['dates'])}")
        lines.append("")
    
    if "mood" in s:
        m = s["mood"]
        lines.append(f"😊 Mood: {m['entries']} entries (avg {m['avg_value']}/5)")
        for r in m["readings"]:
            lines.append(f"   {r['date']}: {r['value']}/5 ({r['label']})")
        lines.append("")
    
    if "sleep_quality" in s:
        sq = s["sleep_quality"]
        lines.append(f"😴 Sleep Quality (subjective): avg {sq['avg_value']}/5 ({sq['entries']} entries)")
        for r in sq["readings"]:
            lines.append(f"   {r['date']}: {r['value']}/5 ({r['label']})")
        lines.append("")
    
    if "dream_intensity" in s:
        di = s["dream_intensity"]
        lines.append(f"💭 Dream Intensity: avg {di['avg_value']}/5 ({di['entries']} entries)")
        for r in di["readings"]:
            lines.append(f"   {r['date']}: {r['value']}/5 ({r['label']})")
        lines.append("")
    
    if "wake_ups" in s:
        wu = s["wake_ups"]
        lines.append(f"⏰ Sleep Interruptions (wake-ups): avg {wu['avg']}/night ({wu['entries']} entries)")
        for date, count in sorted(wu["by_date"].items()):
            lines.append(f"   {date}: {count} wake-ups")
        lines.append("")
    
    if "nocturia" in s:
        nc = s["nocturia"]
        lines.append(f"🚽 Nocturia (woke to pee): avg {nc['avg']}/night ({nc['entries']} entries)")
        for date, count in sorted(nc["by_date"].items()):
            lines.append(f"   {date}: {count} times")
        lines.append("")
    
    if "supplement_doses" in s:
        lines.append("💊 Supplement Doses:")
        for name, info in sorted(s["supplement_doses"].items()):
            latest = info["values"][-1]
            lines.append(f"   {name}: {latest['value']}mg ({info['entries']} logs)")
        lines.append("")
    
    if data.get("semaglutide"):
        lines.append(f"💉 Semaglutide: {len(data['semaglutide'])} logs")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    data = fetch_annotations(days=args.days)
    
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_text(data))