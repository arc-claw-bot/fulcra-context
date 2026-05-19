import sys
import argparse
import json
import zipfile
import xml.etree.ElementTree as ET
import re
import subprocess
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from pathlib import Path

# Add fulcra-context scripts to path
SCRIPT_DIR = Path('/home/leif/.openclaw/workspace/fulcra-context/scripts').resolve()
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from fulcra_data_service import get_service, get_catalog
    from fulcra_timezone import get_user_tz, to_local
except ImportError:
    print("Could not import fulcra modules.")
    sys.exit(1)

def extract_docx_text(file_path):
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
    parser = argparse.ArgumentParser(description="Process transcript and extract top spikes for LLM summarization.")
    parser.add_argument("file_path", type=str, help="Path to local docx file")
    parser.add_argument("--metric", type=str, default="HeartRate", help="Health metric ID")
    args = parser.parse_args()

    service = get_service()
    user_tz = get_user_tz()

    catalog = get_catalog()
    metric_meta = next((m for m in catalog if m.get('id') == args.metric), {})
    metric_col = metric_meta.get('column_name', 'heart_rate')
    val_key = f"mean_{metric_col}"

    try:
        lines = extract_docx_text(args.file_path)
    except Exception as e:
        print(f"Error extracting docx: {e}")
        sys.exit(1)

    title, start_time, utterances = parse_transcript(lines)
    if not utterances or not start_time:
        print("Error: Failed to parse utterances or start time.")
        sys.exit(1)

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=user_tz)

    duration_seconds = utterances[-1]['offsetSeconds'] + 60
    end_time = start_time + timedelta(seconds=duration_seconds)

    m_start = start_time.astimezone(timezone.utc).isoformat()
    m_end = end_time.astimezone(timezone.utc).isoformat()

    metric_series = service.get_metric_time_series(m_start, m_end, args.metric, sample_rate=1, agg_function="mean")

    if not metric_series:
        print(json.dumps({"error": f"No {args.metric} data found during this meeting ({m_start} to {m_end})."}))
        sys.exit(1)

    moments = []
    for pt in metric_series:
        val = pt.get(val_key) or pt.get(metric_col)
        ts_str = pt.get("time") or pt.get("start_date")
        if val is not None and ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            offset = (ts - start_time.astimezone(timezone.utc)).total_seconds()
            if offset >= 0:
                moments.append({"val": val, "secondsIntoMeeting": offset, "utc_time": ts.isoformat()})

    top_moments = sorted(moments, key=lambda x: x["val"], reverse=True)[:5]
    top_moments = sorted(top_moments, key=lambda x: x["secondsIntoMeeting"])

    output_data = {
        "meeting_title": title,
        "start_time_utc": m_start,
        "end_time_utc": m_end,
        "metric": args.metric,
        "spikes": []
    }

    for moment in top_moments:
        # Get surrounding context (60s before, 60s after)
        target_sec = moment["secondsIntoMeeting"]
        context_utterances = [
            u for u in utterances
            if u["offsetSeconds"] >= target_sec - 60 and u["offsetSeconds"] <= target_sec + 60
        ]

        # Capture the high-resolution 1-second sample data around the spike (e.g., 30s before and after)
        local_series = [
            pt for pt in metric_series
            if pt.get("time") and
               abs((datetime.fromisoformat(pt["time"].replace("Z", "+00:00")) -
                   datetime.fromisoformat(moment["utc_time"].replace("Z", "+00:00"))).total_seconds()) <= 30
        ]

        # Clean up the series format for the output
        clean_series = []
        for pt in local_series:
            val = pt.get(val_key) or pt.get(metric_col)
            if val is not None:
                clean_series.append({
                    "time": pt["time"],
                    "value": val
                })

        output_data["spikes"].append({
            "utc_time": moment["utc_time"],
            "offset_seconds": target_sec,
            "metric_value": moment["val"],
            "context_transcript": context_utterances,
            "metric_series_window": clean_series
        })

    print(json.dumps(output_data, indent=2))

if __name__ == "__main__":
    main()
