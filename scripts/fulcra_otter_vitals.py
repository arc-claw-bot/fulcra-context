#!/usr/bin/env python3
"""
Cross-reference and align an Otter.ai meeting transcript with a user's metric time series.
"""

import sys
import argparse
import re
import zipfile
import xml.etree.ElementTree as ET
import subprocess
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from fulcra_data_service import get_service, get_catalog
    from fulcra_timezone import get_user_tz, to_local
except ImportError:
    print("Could not import fulcra modules.")
    sys.exit(1)

def extract_docx_text(file_path):
    """Extract text lines from a .docx file without external dependencies."""
    with zipfile.ZipFile(file_path) as docx:
        xml_content = docx.read('word/document.xml')
        
    tree = ET.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    text_content = []
    for paragraph in tree.findall('.//w:p', ns):
        para_text = []
        for run in paragraph.findall('.//w:r', ns):
            text_node = run.find('w:t', ns)
            if text_node is not None and text_node.text:
                para_text.append(text_node.text)
        if para_text:
            text_content.append(''.join(para_text))
            
    return text_content

def parse_transcript(lines):
    """Parse Otter.ai docx transcript lines into structured utterances."""
    title = lines[0] if len(lines) > 0 else "Unknown Meeting"
    date_str = lines[1] if len(lines) > 1 else ""
    
    start_time = None
    if date_str and '•' in date_str:
        date_part = date_str.split('•')[0].strip()
        try:
            start_time = date_parser.parse(date_part)
        except Exception:
            pass

    utterances = []
    current_speaker = None
    current_offset_seconds = 0
    current_text = []
    
    speaker_time_regex = re.compile(r'^([a-zA-Z0-9\s.\(\)-]+?)\s+((\d+:)?\d+:\d+)$')
    in_transcript = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if not in_transcript:
            if line.startswith("SPEAKERS") or "SUMMARY KEYWORDS" in line:
                continue
            match = speaker_time_regex.match(line)
            if match:
                in_transcript = True
            else:
                continue
            
        match = speaker_time_regex.match(line)
        if match:
            if current_speaker:
                utterances.append({
                    "speaker": current_speaker.strip(),
                    "offsetSeconds": current_offset_seconds,
                    "text": " ".join(current_text).strip()
                })
            current_speaker = match.group(1)
            
            time_str = match.group(2)
            parts = time_str.split(':')
            parts.reverse()
            seconds = int(parts[0])
            if len(parts) > 1:
                seconds += int(parts[1]) * 60
            if len(parts) > 2:
                seconds += int(parts[2]) * 3600
                
            current_offset_seconds = seconds
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
        
    return title, start_time, utterances

def main():
    parser = argparse.ArgumentParser(description="Align an Otter.ai docx transcript with Fulcra metrics.")
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

    print("Locating latest Otter.ai transcript in Fulcra Library...")
    folders = service.get_library_files("/meeting-transcripts/otter")
    if not folders:
        print("Error: No folders found in /meeting-transcripts/otter")
        sys.exit(1)
        
    # Dropbox folder has docx files typically
    files = service.get_library_files("/meeting-transcripts/otter/dropbox")
    docx_files = [f for f in files if f.endswith('.docx')]
    
    if not docx_files:
        print("Error: No .docx files found in /meeting-transcripts/otter/dropbox")
        sys.exit(1)
        
    # Grab the most recent one (assuming alphabetically or modified date sorted by CLI)
    target_file = docx_files[-1]
    remote_path = f"/meeting-transcripts/otter/dropbox/{target_file}"
    local_path = f"/tmp/{target_file.replace(' ', '_')}"
    
    print(f"Downloading {remote_path} to {local_path}...")
    proc = subprocess.run(
        ["fulcra-api", "file", "download", remote_path, local_path],
        capture_output=True,
        text=True
    )
    if proc.returncode != 0:
        # Fallback to uv tool if bare command fails
        proc = subprocess.run(
            ["uv", "tool", "run", "git+https://git@github.com/fulcradynamics/fulcra-api-python.git@file-commands", "file", "download", remote_path, local_path],
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            print(f"Error downloading file: {proc.stderr}")
            sys.exit(1)
            
    try:
        lines = extract_docx_text(local_path)
    except Exception as e:
        print(f"Error extracting docx: {e}")
        sys.exit(1)
        
    title, start_time, utterances = parse_transcript(lines)
    if not utterances:
        print("Error: Failed to parse any utterances from the transcript.")
        sys.exit(1)
        
    if not start_time:
        print("Error: Could not parse a start time from the transcript header.")
        sys.exit(1)
        
    # Localize start time and calculate bounds
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=user_tz)
    
    # Calculate end time based on the last utterance + 60 seconds buffer
    duration_seconds = utterances[-1]['offsetSeconds'] + 60
    end_time = start_time + timedelta(seconds=duration_seconds)
    
    m_start = start_time.astimezone(timezone.utc).isoformat()
    m_end = end_time.astimezone(timezone.utc).isoformat()
    
    print(f"Transcript parsed. Meeting: '{title}' starting at {start_time}")
    print(f"Fetching {args.metric} data for the meeting duration...")
    
    metric_series = service.get_metric_time_series(m_start, m_end, args.metric, sample_rate=1, agg_function="mean")
    
    if not metric_series:
        print(f"Error: No {args.metric} data found during this meeting ({m_start} to {m_end}).")
        sys.exit(1)
        
    vals = [pt.get(val_key) or pt.get(metric_col) for pt in metric_series]
    vals = [v for v in vals if v is not None]
    
    if not vals:
        print(f"Error: No numeric {args.metric} values recorded during this meeting.")
        sys.exit(1)

    # Process and print stats
    avg = sum(vals) / len(vals)
    max_val = max(vals)
    min_val = min(vals)

    fmt = ".1f" if isinstance(avg, float) and avg < 50 else ".0f"
    
    print("\n=========================================================")
    print(f"📅 {title} ({start_time.strftime('%I:%M %p %Z')})")
    print("=========================================================")
    print(f"❤️  Avg: {avg:{fmt}}{metric_unit} | Min: {min_val:{fmt}}{metric_unit} | Max: {max_val:{fmt}}{metric_unit}\n")
    print("--- Key Metric Moments & Transcripts ---\n")
    
    # Map physiological time to transcript time
    # metric_series has absolute UTC timestamps
    moments = []
    for pt in metric_series:
        val = pt.get(val_key) or pt.get(metric_col)
        ts_str = pt.get("time") or pt.get("start_date")
        if val is not None and ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            # Offset in seconds from start of meeting
            offset = (ts - start_time.astimezone(timezone.utc)).total_seconds()
            if offset >= 0:
                moments.append({"val": val, "secondsIntoMeeting": offset})
            
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
                
        mins = int(moment["secondsIntoMeeting"]) // 60
        secs = int(moment["secondsIntoMeeting"]) % 60
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
