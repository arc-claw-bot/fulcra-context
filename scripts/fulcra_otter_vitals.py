#!/usr/bin/env python3
"""
Cross-reference and align an Otter.ai meeting transcript with a user's metric time series.
"""

import sys
import argparse
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from fulcra_data_service import get_service, get_catalog
    from fulcra_timezone import get_user_tz, to_local
except ImportError:
    print("Could not import fulcra modules.")
    sys.exit(1)

def parse_offset(time_str):
    """Convert time string HH:MM:SS or MM:SS to seconds."""
    parts = time_str.split(':')
    parts.reverse()
    seconds = int(parts[0])
    if len(parts) > 1:
        seconds += int(parts[1]) * 60
    if len(parts) > 2:
        seconds += int(parts[2]) * 3600
    return seconds

def parse_transcript(content):
    """Parse Otter.ai transcript content into structured utterances."""
    lines = content.split('\n')
    utterances = []
    
    current_speaker = None
    current_offset_seconds = 0
    current_text = []
    
    time_regex = re.compile(r'^([a-zA-Z0-9\s.\(\)]+?)\s+((\d+:)?\d+:\d+)$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        match = time_regex.match(line)
        if match:
            if current_speaker:
                utterances.append({
                    "speaker": current_speaker.strip(),
                    "offsetSeconds": current_offset_seconds,
                    "text": " ".join(current_text).strip()
                })
            current_speaker = match.group(1)
            current_offset_seconds = parse_offset(match.group(2))
            current_text = []
        else:
            if current_speaker:
                current_text.append(line)
                
    if current_speaker:
        utterances.append({
            "speaker": current_speaker.strip(),
            "offsetSeconds": current_offset_seconds,
            "text": " ".join(current_text).strip()
        })
        
    return utterances

def main():
    parser = argparse.ArgumentParser(description="Align an Otter.ai transcript with Fulcra metrics.")
    parser.add_argument("meeting_title", type=str, help="Exact title of the meeting in the calendar")
    parser.add_argument("--hours", type=int, default=168, help="Hours to look back for the meeting (default: 168)")
    parser.add_argument("--metric", type=str, default="HeartRate", help="Health metric ID from catalog (e.g. HeartRate)")
    args = parser.parse_args()

    service = get_service()
    user_tz = get_user_tz()
    
    # Get metadata from catalog
    catalog = get_catalog()
    metric_meta = next((m for m in catalog if m.get('id') == args.metric), {})
    metric_unit = metric_meta.get('unit', '')
    if metric_unit:
        metric_unit = f" {metric_unit}"
    metric_col = metric_meta.get('column_name', 'heart_rate')
    val_key = f"mean_{metric_col}"

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)

    print(f"Fetching calendar events for the last {args.hours} hours...")
    events = service.get_calendar_events(start.isoformat(), end.isoformat())
    
    # Find matching meeting
    meeting = None
    for e in events:
        if e.get("title") == args.meeting_title:
            meeting = e
            break
            
    if not meeting:
        print(f"Error: Could not find a meeting titled '{args.meeting_title}' in the last {args.hours} hours.")
        sys.exit(1)
        
    m_start = meeting.get("start_date")
    m_end = meeting.get("end_date")
    
    if not m_start or not m_end:
        print("Error: Meeting lacks start or end date.")
        sys.exit(1)

    print(f"Fetching {args.metric} data for the meeting duration...")
    metric_series = service.get_metric_time_series(m_start, m_end, args.metric, sample_rate=1, agg_function="mean")
    
    if not metric_series:
        print(f"Error: No {args.metric} data found during this meeting.")
        sys.exit(1)
        
    vals = [pt.get(val_key) or pt.get(metric_col) for pt in metric_series]
    vals = [v for v in vals if v is not None]
    
    if not vals:
        print(f"Error: No numeric {args.metric} values recorded during this meeting.")
        sys.exit(1)

    print("Locating latest Otter.ai transcript in Fulcra Library...")
    # Get latest folder
    folders = service.get_library_files("/meeting-transcripts/otter")
    if not folders:
        print("Error: No folders found in /meeting-transcripts/otter")
        sys.exit(1)
        
    latest_folder = sorted([f for f in folders if f.endswith('/') and f != 'dropbox/'], reverse=True)[0]
    
    # Get txt file in folder
    files = service.get_library_files(f"/meeting-transcripts/otter/{latest_folder}")
    txt_files = [f for f in files if f.endswith('.txt')]
    
    if not txt_files:
        print(f"Error: No .txt files found in /meeting-transcripts/otter/{latest_folder}")
        sys.exit(1)
        
    target_file = txt_files[0]
    target_path = f"/meeting-transcripts/otter/{latest_folder}{target_file}"
    
    print(f"Downloading {target_path}...")
    transcript_content = service.download_library_file(target_path)
    
    if not transcript_content:
        print("Error: Failed to download transcript.")
        sys.exit(1)
        
    utterances = parse_transcript(transcript_content)
    if not utterances:
        print("Error: Failed to parse any utterances from the transcript.")
        sys.exit(1)

    # Process and print stats
    avg = sum(vals) / len(vals)
    max_val = max(vals)
    min_val = min(vals)

    fmt = ".1f" if isinstance(avg, float) and avg < 50 else ".0f"

    start_dt = to_local(datetime.fromisoformat(m_start.replace("Z", "+00:00")))
    
    print("\n=========================================================")
    print(f"📅 {meeting['title']} ({start_dt.strftime('%I:%M %p %Z')})")
    print("=========================================================")
    print(f"❤️  Avg: {avg:{fmt}}{metric_unit} | Min: {min_val:{fmt}}{metric_unit} | Max: {max_val:{fmt}}{metric_unit}\n")
    print("--- Key Metric Moments & Transcripts ---\n")
    
    # Find top 5 spikes
    moments = []
    for idx, pt in enumerate(metric_series):
        val = pt.get(val_key) or pt.get(metric_col)
        if val is not None:
            moments.append({"val": val, "secondsIntoMeeting": idx})
            
    # Sort by value descending
    top_moments = sorted(moments, key=lambda x: x["val"], reverse=True)[:5]
    # Re-sort top 5 by time ascending
    top_moments = sorted(top_moments, key=lambda x: x["secondsIntoMeeting"])
    
    for moment in top_moments:
        active_utterance = None
        for u in utterances:
            if u["offsetSeconds"] <= moment["secondsIntoMeeting"]:
                active_utterance = u
            else:
                break
                
        mins = moment["secondsIntoMeeting"] // 60
        secs = moment["secondsIntoMeeting"] % 60
        time_str = f"{mins}:{secs:02d}"
        
        print(f"⏱️  [{time_str}] {args.metric} Spiked to: {moment['val']:{fmt}}{metric_unit}")
        if active_utterance:
            text_preview = active_utterance["text"]
            if len(text_preview) > 80:
                text_preview = text_preview[:80] + "..."
            print(f"   🗣️  {active_utterance['speaker']}: \"{text_preview}\"")
        else:
            print("   🗣️  (No active speaker detected)")
        print("")

if __name__ == "__main__":
    main()
