#!/usr/bin/env python3
"""
Generate calendar + heart rate visualizations from Fulcra data.
Overlays high-resolution heart rate data onto calendar event windows.
"""

import os
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

try:
    from fulcra_data_service import get_service, get_catalog
    from fulcra_timezone import get_user_tz, to_local
except ImportError:
    print("Could not import fulcra modules.")
    exit(1)

# Default data directory
DEFAULT_DATA_DIR = Path.home() / ".fulcra-context" / "analysis"

# Premium dark theme (matching sleep_chart)
BG = '#0d1117'
PANEL = '#161b22'
TEXT = '#c9d1d9'
SUBTEXT = '#8b949e'
HR_LINE = '#ff4d4d'

def plot_calendar_vitals(hours=24, out_file=None, include_all_day=False):
    if out_file is None:
        out_file = DEFAULT_DATA_DIR / "calendar_vitals.png"
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    service = get_service()
    user_tz = get_user_tz()
    
    # Get units from catalog
    catalog = get_catalog()
    hr_meta = next((m for m in catalog if m.get('id') == 'HeartRate'), {})
    hr_unit = hr_meta.get('unit', 'bpm')
    
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    events = service.get_calendar_events(start.isoformat(), end.isoformat())
    if not events:
        print(f"No events found in the last {hours} hours.")
        return

    calendars = service.get_calendars()
    cal_map = {c.get('calendar_id'): c.get('calendar_name', 'Unknown Calendar') for c in calendars}

    # Filter events that actually have heart rate data
    aligned = []
    for event in events:
        s = event.get('start_date')
        e = event.get('end_date')
        is_all_day = event.get('is_all_day', False)
        cal_id = event.get('calendar_id')
        cal_name = cal_map.get(cal_id, 'Unknown Calendar')
        
        if not include_all_day and is_all_day:
            continue
            
        if not s or not e:
            continue
            
        rate = 1800 if is_all_day else 1
        hr_series = service.get_metric_time_series(s, e, "HeartRate", sample_rate=rate, agg_function="mean")
        if hr_series and len(hr_series) > 0:
            aligned.append({
                "title": event.get('title', 'Untitled'),
                "calendar_name": cal_name,
                "start": s,
                "end": e,
                "hr_series": hr_series
            })

    if not aligned:
        print("No heart rate data found for any events in the timeframe.")
        return

    # Create figure
    num_events = len(aligned)
    fig, axes = plt.subplots(num_events, 1, figsize=(10, 3 * num_events), squeeze=False)
    fig.patch.set_facecolor(BG)

    for idx, ev in enumerate(aligned):
        ax = axes[idx, 0]
        ax.set_facecolor(PANEL)
        
        times = []
        hrs = []
        for pt in ev['hr_series']:
            val = pt.get('mean_heart_rate')
            ts = pt.get('time') or pt.get('start_date')
            if val is not None and ts is not None:
                times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                hrs.append(val)
                
        if not hrs:
            ax.text(0.5, 0.5, "No numeric HR data", color=SUBTEXT, ha='center', va='center')
            continue

        ax.plot(times, hrs, color=HR_LINE, linewidth=1.5, alpha=0.8)
        
        avg_hr = sum(hrs) / len(hrs)
        max_hr = max(hrs)
        min_hr = min(hrs)
        
        # Localize times for the title
        start_dt = to_local(datetime.fromisoformat(ev['start'].replace("Z", "+00:00")))
        end_dt = to_local(datetime.fromisoformat(ev['end'].replace("Z", "+00:00")))
        time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
        
        cal_tag = f"[{ev['calendar_name']}] " if ev.get('calendar_name') else ""
        ax.set_title(f"{cal_tag}{ev['title']} ({time_str})  |  Avg: {avg_hr:.0f} {hr_unit}  Max: {max_hr:.0f} {hr_unit}  Min: {min_hr:.0f} {hr_unit}", 
                     color=TEXT, pad=10, loc='left', fontsize=11)
                     
        ax.tick_params(colors=SUBTEXT, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#30363d')
            
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%I:%M %p', tz=user_tz))
        ax.grid(True, axis='y', color='#30363d', linestyle='--', alpha=0.5)

    plt.tight_layout(pad=3.0)
    plt.savefig(out_file, facecolor=fig.get_facecolor(), edgecolor='none', dpi=120)
    plt.close()
    
    print(f"Calendar vitals chart saved to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate calendar vitals chart.")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back")
    parser.add_argument("--out", type=str, default=None, help="Output PNG path")
    parser.add_argument("--include-all-day", action="store_true", help="Include all-day events")
    args = parser.parse_args()
    
    plot_calendar_vitals(hours=args.hours, out_file=args.out, include_all_day=args.include_all_day)
