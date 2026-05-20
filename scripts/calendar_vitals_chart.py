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
import numpy as np

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

def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _sample_rate_for_window(start_dt, end_dt, is_all_day=False):
    if is_all_day or not start_dt or not end_dt:
        return 1800
    duration_seconds = max(0, int((end_dt - start_dt).total_seconds()))
    if duration_seconds > 12 * 3600:
        return 1800
    if duration_seconds > 3 * 3600:
        return 300
    return 60


def _catmull_rom_spline(P0, P1, P2, P3, num_points=20):
    """Compute points for a single Catmull-Rom spline segment."""
    t = np.linspace(0, 1, num_points)
    t2 = t * t
    t3 = t2 * t
    alpha = 0.5

    pts = []
    for i in range(num_points):
        x = alpha * ((2 * P1[0]) +
                    (-P0[0] + P2[0]) * t[i] +
                    (2*P0[0] - 5*P1[0] + 4*P2[0] - P3[0]) * t2[i] +
                    (-P0[0] + 3*P1[0] - 3*P2[0] + P3[0]) * t3[i])
        y = alpha * ((2 * P1[1]) +
                    (-P0[1] + P2[1]) * t[i] +
                    (2*P0[1] - 5*P1[1] + 4*P2[1] - P3[1]) * t2[i] +
                    (-P0[1] + 3*P1[1] - 3*P2[1] + P3[1]) * t3[i])
        pts.append((x, y))
    return pts

def _smooth_curve(times, values, points_per_segment=20):
    """Generate a smoothed Catmull-Rom spline through the given datetime and value arrays."""
    if len(times) < 3:
        return times, values

    ts = [t.timestamp() for t in times]
    pts = list(zip(ts, values))

    # Pad ends to compute first and last segments
    pts.insert(0, pts[0])
    pts.append(pts[-1])

    smooth_ts = []
    smooth_vals = []

    for i in range(1, len(pts)-2):
        # Exclude the last point of the segment to avoid overlap, unless it's the very last segment
        segment = _catmull_rom_spline(pts[i-1], pts[i], pts[i+1], pts[i+2], points_per_segment)
        if i < len(pts) - 3:
            segment = segment[:-1]
        for p in segment:
            smooth_ts.append(p[0])
            smooth_vals.append(p[1])

    smooth_times = [datetime.fromtimestamp(t, tz=times[0].tzinfo) for t in smooth_ts]
    return smooth_times, smooth_vals


def plot_calendar_vitals(hours=24, out_file=None, include_all_day=False, metric="HeartRate"):
    if out_file is None:
        out_file = DEFAULT_DATA_DIR / f"calendar_{metric.lower()}.png"
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    service = get_service()
    user_tz = get_user_tz()

    # Get metadata from catalog
    catalog = get_catalog()
    metric_meta = next((m for m in catalog if m.get('id') == metric), {})
    metric_unit = metric_meta.get('unit', '')
    if metric_unit:
        metric_unit = f" {metric_unit}" # prepend space for formatting
    metric_col = metric_meta.get('column_name', 'heart_rate')
    val_key = f"mean_{metric_col}"

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    events = service.get_calendar_events(start.isoformat(), end.isoformat())
    if not events:
        print(f"No events found in the last {hours} hours.")
        return

    calendars = service.get_calendars()
    cal_map = {c.get('calendar_id'): c.get('calendar_name', 'Unknown Calendar') for c in calendars}

    # Filter events that actually have metric data
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

        event_start = _parse_dt(s)
        event_end = _parse_dt(e)
        if not event_start or not event_end:
            continue

        window_start = max(event_start, start)
        window_end = min(event_end, end)
        if window_end <= window_start:
            continue

        rate = _sample_rate_for_window(window_start, window_end, is_all_day)
        metric_series = service.get_metric_time_series(
            window_start.isoformat(), window_end.isoformat(), metric, sample_rate=rate, agg_function="mean"
        )
        if metric_series and len(metric_series) > 0:
            aligned.append({
                "title": event.get('title', 'Untitled'),
                "calendar_name": cal_name,
                "start": s,
                "end": e,
                "metric_series": metric_series
            })

    if not aligned:
        print(f"No {metric} data found for any events in the timeframe.")
        return

    # Fetch processed transcripts for annotations
    try:
        from fulcra_data_service import get_library_files, download_library_file
        import json

        # Override CLI command temporarily for file fetch if needed
        import os
        old_cmd = os.environ.get("FULCRA_CLI_COMMAND")
        os.environ["FULCRA_CLI_COMMAND"] = "uv tool run git+https://git@github.com/fulcradynamics/fulcra-api-python.git@file-commands"

        annotations = []
        files = get_library_files("/meeting-transcripts/processed")
        if files:
            for f in files:
                if f.endswith('.json'):
                    content = download_library_file(f"/meeting-transcripts/processed/{f}")
                    if content:
                        try:
                            annotations.append(json.loads(content))
                        except Exception:
                            pass

        # Restore environment
        if old_cmd is None:
            del os.environ["FULCRA_CLI_COMMAND"]
        else:
            os.environ["FULCRA_CLI_COMMAND"] = old_cmd

    except ImportError:
        annotations = []

    # Create figure
    num_events = len(aligned)
    fig, axes = plt.subplots(num_events, 1, figsize=(10, 4.5 * num_events), squeeze=False)
    fig.patch.set_facecolor(BG)

    for idx, ev in enumerate(aligned):
        ax = axes[idx, 0]
        ax.set_facecolor(PANEL)

        times = []
        vals = []
        for pt in ev['metric_series']:
            val = pt.get(val_key) or pt.get(metric_col)
            ts = pt.get('time') or pt.get('start_date')
            if val is not None and ts is not None:
                times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                vals.append(val)

        if not vals:
            ax.text(0.5, 0.5, f"No numeric {metric} data", color=SUBTEXT, ha='center', va='center')
            continue

        smooth_times, smooth_vals = _smooth_curve(times, vals)
        ax.plot(smooth_times, smooth_vals, color=HR_LINE, linewidth=1.8, alpha=0.85)

        # Overlay any matching transcript annotations
        for ann in annotations:
            # Check if this annotation belongs to this meeting title
            # In a real app we'd match exact timestamps or event IDs, but for this poc title matching is sufficient
            if ann.get("meeting_title") in ev['title']:
                spikes = ann.get("spikes", [])
                if spikes:
                    # Plot up to 3 top spikes to show more context without overcrowding
                    top_spikes = sorted(spikes, key=lambda x: x["metric_value"], reverse=True)[:3]
                    
                    event_start = _parse_dt(ev['start'])
                    event_end = _parse_dt(ev['end'])
                    
                    footer_items = []
                    
                    for i, spike in enumerate(top_spikes):
                        spike_time = datetime.fromisoformat(spike["utc_time"].replace("Z", "+00:00"))
                        
                        # Ensure the spike falls within this event window
                        if event_start <= spike_time <= event_end:
                            spike_val = spike["metric_value"]
                            summary = spike.get("context_summary", "Spike detected")
                            
                            time_str = spike_time.astimezone(user_tz).strftime('%I:%M %p')
                            
                            # Use a bold yellow marker
                            ANNOTATION_COLOR = '#ffcc00'
                            ax.plot(spike_time, spike_val, 'o', color=ANNOTATION_COLOR, markersize=7, zorder=5)
                            
                            # Alternate Y-offset to prevent text overlap
                            y_offset = 15 if i % 2 == 0 else -20
                            ax.annotate(time_str,
                                        xy=(spike_time, spike_val),
                                        xytext=(0, y_offset),
                                        textcoords="offset points",
                                        color=ANNOTATION_COLOR,
                                        fontsize=9,
                                        fontweight='bold',
                                        ha='center')
                                        
                            footer_items.append((time_str, summary))
                            
                    if footer_items:
                        # Sort footer items by time
                        footer_items.sort(key=lambda x: datetime.strptime(x[0], '%I:%M %p'))
                        import textwrap
                        footer_lines = []
                        for t_str, summ in footer_items:
                            wrapped = textwrap.fill(f"[{t_str}] {summ}", width=110, subsequent_indent="  ")
                            footer_lines.append(wrapped)
                        footer_text = "Meeting Context:\n" + "\n".join(footer_lines)
                        
                        ax.annotate(footer_text, 
                                    xy=(0, -0.15), 
                                    xycoords='axes fraction',
                                    color=TEXT, 
                                    fontsize=10, 
                                    ha='left', 
                                    va='top')

        avg_val = sum(vals) / len(vals)
        max_val = max(vals)
        min_val = min(vals)

        # Localize times for the title
        start_dt = to_local(datetime.fromisoformat(ev['start'].replace("Z", "+00:00")))
        end_dt = to_local(datetime.fromisoformat(ev['end'].replace("Z", "+00:00")))

        date_str = start_dt.strftime('%B %-d, %Y')
        time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"

        cal_tag = f"[{ev['calendar_name']}] " if ev.get('calendar_name') else ""

        # If values are floats like 85.0 for HeartRate, 0f is fine, but HRV might need 1f. Let's format conditionally.
        fmt = ".1f" if isinstance(avg_val, float) and avg_val < 50 else ".0f"
        stats_str = f"Avg: {avg_val:{fmt}}{metric_unit}  Max: {max_val:{fmt}}{metric_unit}  Min: {min_val:{fmt}}{metric_unit}"

        title_line1 = f"{cal_tag}{ev['title']}"
        title_line2 = f"{date_str}  •  {time_str}    |    {stats_str}"

        ax.set_title(title_line1, color='#ffffff', pad=24, loc='left', fontsize=13, fontweight='bold')
        ax.annotate(title_line2,
                    xy=(0, 1), xytext=(0, 8),
                    xycoords='axes fraction', textcoords='offset points',
                    color=SUBTEXT, fontsize=10, ha='left', va='bottom')

        ax.tick_params(colors=SUBTEXT, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#30363d')

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%I:%M %p', tz=user_tz))
        ax.grid(True, axis='y', color='#30363d', linestyle='--', alpha=0.5)

    plt.tight_layout(pad=3.0)
    plt.savefig(out_file, facecolor=fig.get_facecolor(), edgecolor='none', dpi=120, bbox_inches='tight')
    plt.close()

    print(f"Calendar vitals chart saved to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate calendar vitals chart.")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back")
    parser.add_argument("--out", type=str, default=None, help="Output PNG path")
    parser.add_argument("--include-all-day", action="store_true", help="Include all-day events")
    parser.add_argument("--metric", type=str, default="HeartRate", help="Health metric ID from catalog (e.g. HeartRate, HeartRateVariabilitySDNN)")
    args = parser.parse_args()

    plot_calendar_vitals(hours=args.hours, out_file=args.out, include_all_day=args.include_all_day, metric=args.metric)
