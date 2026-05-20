#!/usr/bin/env python3
"""
Third Space Analyzer (POC)

Finds and ranks geographic locations where a user spends time outside of their
primary anchor (Home/Work), filtered by customizable schedule templates (e.g., weekends).
Fetches Heart Rate data during those stays to gauge physiological recovery.

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

def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great circle distance in meters between two points."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371000 # Radius of earth in meters
    return c * r

class ScheduleTemplate:
    def __init__(self, template_name: str):
        self.name = template_name.lower()

    def is_active(self, dt: datetime.datetime) -> bool:
        if self.name == "weekends":
            return dt.weekday() >= 5 # 5=Saturday, 6=Sunday
        elif self.name == "weekdays":
            return dt.weekday() < 5
        # Default fallback is always active if unknown
        return True

def fetch_and_parse_locations(time_range: str) -> List[Dict[str, Any]]:
    # We invoke the CLI adapter with the specific time_range parameter
    base_cmd_env = os.environ.get("FULCRA_CLI_COMMAND", "uv tool run 'git+https://github.com/fulcradynamics/fulcra-api-python.git@add-cli'")
    base_cmd = shlex.split(base_cmd_env)
    
    cmd = [*base_cmd, "location-time-series", "-s", "900", "-r", time_range]
    print(f"Fetching location data: {' '.join(cmd)}")
    
    payload = fulcra_cli_adapter._run_cli(cmd)
    if payload is None:
        print("Failed to fetch location data.")
        return []
        
    return payload if isinstance(payload, list) else [payload]

def main():
    parser_obj = argparse.ArgumentParser(description="Analyze Third Space locations with Vitals.")
    parser_obj.add_argument("--template", type=str, default="weekends", help="Schedule template (e.g., weekends, weekdays, all)")
    parser_obj.add_argument("--range", type=str, default="14 days", help="Time range (e.g. '14 days')")
    args = parser_obj.parse_args()

    schedule = ScheduleTemplate(args.template)
    
    # 1. Fetch Location Data
    locations = fetch_and_parse_locations(args.range)
    if not locations:
        return

    # Filter out null coordinates and parse times
    valid_points = []
    for loc in locations:
        if loc.get("lat") is None or loc.get("long") is None:
            continue
        if loc.get("slice_time") is None:
            continue
            
        dt = datetime.datetime.fromisoformat(loc["slice_time"].replace("Z", "+00:00"))
        valid_points.append({
            "lat": loc["lat"],
            "long": loc["long"],
            "time": dt,
            "address": loc.get("address", "Unknown Address")
        })

    if not valid_points:
        print("No valid location data found.")
        return

    # 2. Identify the primary anchor (Home/Work) over the ENTIRE time range
    anchor_counter = Counter()
    for pt in valid_points:
        grid_key = (round(pt["lat"], 3), round(pt["long"], 3))
        anchor_counter[grid_key] += 1
        
    if not anchor_counter:
        print("No anchor found.")
        return
        
    primary_anchor_key, primary_count = anchor_counter.most_common(1)[0]
    print(f"Detected Primary Anchor (Home/Work) at approx {primary_anchor_key} with {primary_count} samples.")

    # 3. Apply Schedule Template & filter out the anchor
    third_space_points = []
    for pt in valid_points:
        if not schedule.is_active(pt["time"]):
            continue
            
        dist = haversine(pt["long"], pt["lat"], primary_anchor_key[1], primary_anchor_key[0])
        if dist > 300: # Third space is >300m away
            third_space_points.append(pt)

    print(f"Found {len(third_space_points)} data points in Third Spaces during '{args.template}'.")

    if not third_space_points:
        print("No third space activity detected in this time range.")
        return

    # 4. Group into Discrete Stays
    third_space_points.sort(key=lambda x: x["time"])
    stays = []
    current_stay = None
    
    for pt in third_space_points:
        grid_key = (round(pt["lat"], 3), round(pt["long"], 3))
        
        if current_stay is None:
            current_stay = {
                "grid_key": grid_key, 
                "start": pt["time"], 
                "end": pt["time"], 
                "points": 1, 
                "address": pt["address"]
            }
        else:
            time_diff = (pt["time"] - current_stay["end"]).total_seconds()
            if grid_key == current_stay["grid_key"] and time_diff <= 3600:
                current_stay["end"] = pt["time"]
                current_stay["points"] += 1
            else:
                if current_stay["points"] >= 1: 
                    stays.append(current_stay)
                current_stay = {
                    "grid_key": grid_key, 
                    "start": pt["time"], 
                    "end": pt["time"], 
                    "points": 1, 
                    "address": pt["address"]
                }
    if current_stay and current_stay["points"] >= 1:
        stays.append(current_stay)

    print(f"Grouped points into {len(stays)} discrete 'Stays'.")

    # 5. Fetch Biometric Data for each Stay
    print("Fetching physiological data (Heart Rate) for each stay...")
    for stay in stays:
        # Buffer end time by 900s to cover the sample window
        end_time_buffered = stay["end"] + datetime.timedelta(seconds=900)
        
        hr_series = fulcra_cli_adapter.fetch_metric_time_series(
            stay["start"].isoformat(), 
            end_time_buffered.isoformat(), 
            "HeartRate", 
            sample_rate=60, 
            agg_function="mean"
        )
        
        if hr_series:
            vals = []
            for item in hr_series:
                for k, v in item.items():
                    if k != 'time' and isinstance(v, (int, float)):
                        vals.append(v)
            if vals:
                stay["avg_hr"] = sum(vals) / len(vals)
            else:
                stay["avg_hr"] = None
        else:
            stay["avg_hr"] = None

    # 6. Aggregate by Location and Rank
    location_stats = {}
    for stay in stays:
        gk = stay["grid_key"]
        if gk not in location_stats:
            location_stats[gk] = {
                "address": stay["address"], 
                "total_seconds": 0, 
                "hr_values": [], 
                "stay_count": 0
            }
        
        duration = (stay["end"] - stay["start"]).total_seconds() + 900
        location_stats[gk]["total_seconds"] += duration
        location_stats[gk]["stay_count"] += 1
        if stay.get("avg_hr") is not None:
            # We append the average of this specific stay
            location_stats[gk]["hr_values"].append(stay["avg_hr"])

    # Rank by total duration
    ranked_locations = sorted(location_stats.items(), key=lambda x: x[1]["total_seconds"], reverse=True)

    print("\n--- Top Third Spaces (With HR Context) ---")
    for gk, stats in ranked_locations[:10]:
        hours_spent = stats["total_seconds"] / 3600.0
        avg_hr = sum(stats["hr_values"]) / len(stats["hr_values"]) if stats["hr_values"] else 0
        
        print(f"Location: {stats['address']}")
        print(f"Coordinates: {gk}")
        print(f"Visits: {stats['stay_count']} | Approx Duration: {hours_spent:.1f} hours")
        if avg_hr > 0:
            print(f"Average Heart Rate: {avg_hr:.1f} bpm")
        else:
            print(f"Average Heart Rate: No data")
        print("---")

if __name__ == "__main__":
    main()
