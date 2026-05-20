#!/usr/bin/env python3
"""
Third Space Analyzer (POC)

Finds and ranks geographic locations where a user spends time outside of their
primary anchor (Home/Work), filtered by customizable schedule templates (e.g., weekends).
Fetches Heart Rate and HRV data during those stays to gauge physiological recovery,
comparing them against the user's temporal baseline.

Usage:
    python3 third_space_analyzer.py --template weekends --range "14 days"
"""

import argparse
import datetime
import os
import shlex
from collections import Counter
from math import radians, cos, sin, asin, sqrt
from typing import List, Dict, Any, Optional

import fulcra_cli_adapter
from weather_provider import WeatherProvider

def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371000 
    return c * r

class ScheduleTemplate:
    def __init__(self, template_name: str):
        self.name = template_name.lower()

    def is_active(self, dt: datetime.datetime) -> bool:
        if self.name == "weekends":
            return dt.weekday() >= 5
        elif self.name == "weekdays":
            return dt.weekday() < 5
        return True

def fetch_cli_json(cmd_args: List[str]) -> List[Dict[str, Any]]:
    # Instead of raw _run_cli, we build the command locally using the explicit ENV fallback
    # to avoid breaking the core adapter, but still leverage our public wrapper.
    base_cmd_env = os.environ.get("FULCRA_CLI_COMMAND", "fulcra-api")
    base_cmd = shlex.split(base_cmd_env)
    cmd = [*base_cmd, *cmd_args]
    payload = fulcra_cli_adapter._run_cli_public(cmd)
    if payload is None:
        return []
    return payload if isinstance(payload, list) else [payload]

def get_temporal_baseline(time_range: str, schedule: ScheduleTemplate, metric: str) -> Optional[float]:
    print(f"Fetching baseline for {metric} over {time_range}...")
    series = fetch_cli_json(["metric-time-series", "-s", "3600", "-a", "mean", metric, time_range])
    
    valid_vals = []
    for item in series:
        if "time" not in item or item.get("time") is None:
            continue
        dt = datetime.datetime.fromisoformat(item["time"].replace("Z", "+00:00"))
        
        # We only want the baseline for the active schedule (e.g., weekends only)
        if not schedule.is_active(dt):
            continue
            
        for k, v in item.items():
            if k != 'time' and isinstance(v, (int, float)):
                valid_vals.append(v)
                
    if valid_vals:
        return sum(valid_vals) / len(valid_vals)
    return None

def main():
    parser_obj = argparse.ArgumentParser()
    parser_obj.add_argument("--template", type=str, default="weekends")
    parser_obj.add_argument("--range", type=str, default="14 days")
    args = parser_obj.parse_args()

    schedule = ScheduleTemplate(args.template)
    
    weather_provider = WeatherProvider()
    if not weather_provider.is_configured():
        print("\n[!] NOTE: WEATHER_API_KEY environment variable is not set.")
        print("[!] Environmental context (Temperature/Conditions) will be skipped.")
        print("[!] To enable this, get a free key at https://www.visualcrossing.com/ and set it.\n")
    # Calculate Baselines first
    hr_baseline = get_temporal_baseline(args.range, schedule, "HeartRate")
    hrv_baseline = get_temporal_baseline(args.range, schedule, "HeartRateVariabilitySDNN")
    
    print(f"\n--- Temporal Baselines ({args.template.capitalize()}) ---")
    print(f"Baseline HR:  {hr_baseline:.1f} bpm" if hr_baseline else "Baseline HR:  No data")
    print(f"Baseline HRV: {hrv_baseline:.1f} ms" if hrv_baseline else "Baseline HRV: No data")
    print("----------------------------------------\n")

    # Fetch Location Data
    print(f"Fetching location data over {args.range}...")
    locations = fetch_cli_json(["location-time-series", "-s", "900", "-r", args.range])

    valid_points = []
    for loc in locations:
        if loc.get("lat") is None or loc.get("long") is None or loc.get("slice_time") is None:
            continue
        dt = datetime.datetime.fromisoformat(loc["slice_time"].replace("Z", "+00:00"))
        valid_points.append({
            "lat": loc["lat"], "long": loc["long"], "time": dt, "address": loc.get("address", "Unknown Address")
        })

    if not valid_points:
        print("No valid location data found.")
        return

    anchor_counter = Counter()
    for pt in valid_points:
        grid_key = (round(pt["lat"], 3), round(pt["long"], 3))
        anchor_counter[grid_key] += 1
        
    primary_anchor_key, primary_count = anchor_counter.most_common(1)[0]
    print(f"Detected Primary Anchor at approx {primary_anchor_key} ({primary_count} samples).")

    third_space_points = []
    for pt in valid_points:
        if not schedule.is_active(pt["time"]):
            continue
        if haversine(pt["long"], pt["lat"], primary_anchor_key[1], primary_anchor_key[0]) > 300:
            third_space_points.append(pt)

    if not third_space_points:
        print("No third space activity detected.")
        return

    third_space_points.sort(key=lambda x: x["time"])
    stays = []
    current_stay = None
    
    for pt in third_space_points:
        grid_key = (round(pt["lat"], 3), round(pt["long"], 3))
        if current_stay is None:
            current_stay = {"grid_key": grid_key, "start": pt["time"], "end": pt["time"], "points": 1, "address": pt["address"]}
        else:
            time_diff = (pt["time"] - current_stay["end"]).total_seconds()
            if grid_key == current_stay["grid_key"] and time_diff <= 3600:
                current_stay["end"] = pt["time"]
                current_stay["points"] += 1
            else:
                if current_stay["points"] >= 1: stays.append(current_stay)
                current_stay = {"grid_key": grid_key, "start": pt["time"], "end": pt["time"], "points": 1, "address": pt["address"]}
    if current_stay and current_stay["points"] >= 1:
        stays.append(current_stay)

    print(f"Grouped points into {len(stays)} discrete Stays.")
    print("Fetching HR & HRV for each stay...")

    for stay in stays:
        start_iso = stay["start"].isoformat()
        end_iso = (stay["end"] + datetime.timedelta(seconds=900)).isoformat()
        
        hr_series = fulcra_cli_adapter.fetch_metric_time_series(start_iso, end_iso, "HeartRate", 60, "mean")
        hrv_series = fulcra_cli_adapter.fetch_metric_time_series(start_iso, end_iso, "HeartRateVariabilitySDNN", 60, "mean")
        
        stay["avg_hr"] = sum([v for i in (hr_series or []) for k,v in i.items() if k!='time' and isinstance(v, (int,float))]) / len([v for i in (hr_series or []) for k,v in i.items() if k!='time' and isinstance(v, (int,float))]) if hr_series and [v for i in hr_series for k,v in i.items() if k!='time' and isinstance(v, (int,float))] else None
        stay["avg_hrv"] = sum([v for i in (hrv_series or []) for k,v in i.items() if k!='time' and isinstance(v, (int,float))]) / len([v for i in (hrv_series or []) for k,v in i.items() if k!='time' and isinstance(v, (int,float))]) if hrv_series and [v for i in hrv_series for k,v in i.items() if k!='time' and isinstance(v, (int,float))] else None

        # Fetch Weather
        midpoint = stay["start"] + (stay["end"] - stay["start"]) / 2
        weather = weather_provider.get_historical_weather(stay["grid_key"][0], stay["grid_key"][1], midpoint)
        stay["weather"] = weather
    location_stats = {}
    for stay in stays:
        gk = stay["grid_key"]
        if gk not in location_stats:
            location_stats[gk] = {"address": stay["address"], "total_seconds": 0, "hr_values": [], "hrv_values": [], "stay_count": 0}
        
        location_stats[gk]["total_seconds"] += (stay["end"] - stay["start"]).total_seconds() + 900
        location_stats[gk]["stay_count"] += 1
        if stay["avg_hr"] is not None: location_stats[gk]["hr_values"].append(stay["avg_hr"])
        if stay["avg_hrv"] is not None: location_stats[gk]["hrv_values"].append(stay["avg_hrv"])
        if stay.get("weather"): 
            if "weather_conditions" not in location_stats[gk]:
                location_stats[gk]["weather_conditions"] = []
            location_stats[gk]["weather_conditions"].append(stay["weather"])

    # Calculate Recovery Score
    for gk, stats in location_stats.items():
        avg_hr = sum(stats["hr_values"]) / len(stats["hr_values"]) if stats["hr_values"] else None
        avg_hrv = sum(stats["hrv_values"]) / len(stats["hrv_values"]) if stats["hrv_values"] else None
        
        score = 0
        
        # Normalize the deltas to percentage shifts so they can be mathematically combined
        if avg_hr and hr_baseline:
            hr_pct_delta = ((hr_baseline - avg_hr) / hr_baseline) * 100 
            score += hr_pct_delta # Dropping HR 10% below baseline adds +10 to score
            
        if avg_hrv and hrv_baseline:
            hrv_pct_delta = ((avg_hrv - hrv_baseline) / hrv_baseline) * 100
            score += hrv_pct_delta # Raising HRV 10% above baseline adds +10 to score
            
        stats["avg_hr"] = avg_hr
        stats["avg_hrv"] = avg_hrv
        stats["recovery_score"] = score if (avg_hr and hr_baseline) or (avg_hrv and hrv_baseline) else -9999

    ranked = sorted(location_stats.items(), key=lambda x: x[1]["recovery_score"], reverse=True)

    print("\n--- Top Recovery Spaces (Ranked by Score) ---")
    for gk, stats in ranked[:10]:
        hours = stats["total_seconds"] / 3600.0
        print(f"Location: {stats['address']}")
        print(f"Visits: {stats['stay_count']} | Approx Duration: {hours:.1f} hours")
        
        hr_str = f"{stats['avg_hr']:.1f} bpm" if stats['avg_hr'] else "N/A"
        hrv_str = f"{stats['avg_hrv']:.1f} ms" if stats['avg_hrv'] else "N/A"
        
        hr_delta = f"({stats['avg_hr'] - hr_baseline:+.1f})" if stats['avg_hr'] and hr_baseline else ""
        hrv_delta = f"({stats['avg_hrv'] - hrv_baseline:+.1f})" if stats['avg_hrv'] and hrv_baseline else ""
        
        print(f"Heart Rate: {hr_str} {hr_delta} | HRV: {hrv_str} {hrv_delta}")
        
        if stats.get("weather_conditions"):
            # Get the most common condition and average temp
            temps = [w["temp_f"] for w in stats["weather_conditions"] if w.get("temp_f")]
            conds = [w["condition"] for w in stats["weather_conditions"] if w.get("condition")]
            
            avg_temp = sum(temps) / len(temps) if temps else None
            
            # Count manually to avoid UnboundLocalError with inner Counter imports
            cond_counts = {}
            for c in conds:
                cond_counts[c] = cond_counts.get(c, 0) + 1
            
            common_cond = max(cond_counts, key=cond_counts.get) if cond_counts else "Unknown"
            
            if avg_temp:
                print(f"Optimal Conditions: {avg_temp:.1f}F | {common_cond}")
        print(f"Recovery Score: {stats['recovery_score']:.1f}")
        print("---")

if __name__ == "__main__":
    main()
