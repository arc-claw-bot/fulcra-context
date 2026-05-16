#!/usr/bin/env python3
"""
Fetch existing Fulcra annotations and summarize them for context analysis.

This script is read-only. To create annotation definitions or record new
annotation events, use the separate fulcra-annotations skill.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fulcra_timezone import get_user_tz
    LOCAL_TZ = get_user_tz()
except Exception:
    import zoneinfo
    LOCAL_TZ = zoneinfo.ZoneInfo(os.environ.get("OPENCLAW_TIMEZONE", "America/New_York"))


def get_api():
    from fulcra_data_service import get_service

    return get_service()


def utc_to_local(ts_str):
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return dt.astimezone(LOCAL_TZ)


def _entry(record, annotation_type):
    meta = record.get("metadata") or {}
    local_time = utc_to_local(record["recorded_at"])
    return {
        "type": annotation_type,
        "source": meta.get("name") or record.get("source_name", "unknown"),
        "timestamp": local_time.strftime("%Y-%m-%d %H:%M"),
        "date": local_time.strftime("%Y-%m-%d"),
        "time": local_time.strftime("%H:%M"),
        "day_of_week": local_time.strftime("%A"),
        "value": record.get("value"),
        "note": record.get("note"),
    }


def _add_scale_label(entry, record):
    meta = record.get("metadata") or {}
    spec = meta.get("spec") or {}
    scale = spec.get("scale") or {}
    mapping = scale.get("label_mapping", {}).get("string", {}).get("mapping", {})
    value = entry.get("value")
    if value is not None:
        entry["label"] = mapping.get(str(value), str(value))


def fetch_annotations(days=3):
    api = get_api()
    now = datetime.now(LOCAL_TZ)
    start = now - timedelta(days=days)

    results = {
        "period": {
            "start": start.isoformat(),
            "end": now.isoformat(),
            "days": days,
        },
        "moments": [],
        "scales": [],
        "numeric": [],
        "boolean": [],
        "duration": [],
        "summary": {},
    }

    fetchers = [
        ("moments", "moment_annotations", "moment"),
        ("scales", "scale_annotations", "scale"),
        ("numeric", "numeric_annotations", "numeric"),
        ("boolean", "boolean_annotations", "boolean"),
        ("duration", "duration_annotations", "duration"),
    ]

    for bucket, method_name, annotation_type in fetchers:
        try:
            records = getattr(api, method_name)(start.isoformat(), now.isoformat())
            for record in records or []:
                entry = _entry(record, annotation_type)
                if annotation_type == "scale":
                    _add_scale_label(entry, record)
                results[bucket].append(entry)
        except Exception as e:
            results.setdefault("errors", []).append(f"{method_name}: {e}")

    by_source = defaultdict(lambda: {"count": 0, "types": set(), "latest": None})
    for bucket in ["moments", "scales", "numeric", "boolean", "duration"]:
        for entry in results[bucket]:
            source = entry.get("source") or "unknown"
            item = by_source[source]
            item["count"] += 1
            item["types"].add(entry["type"])
            item["latest"] = max(item["latest"] or entry["timestamp"], entry["timestamp"])

    results["summary"]["by_source"] = {
        source: {
            "count": item["count"],
            "types": sorted(item["types"]),
            "latest": item["latest"],
        }
        for source, item in sorted(by_source.items())
    }
    results["summary"]["counts"] = {
        bucket: len(results[bucket])
        for bucket in ["moments", "scales", "numeric", "boolean", "duration"]
    }
    return results


def format_text(data):
    lines = [
        f"Fulcra annotations ({data['period']['days']}-day window)",
        f"Period: {data['period']['start'][:10]} to {data['period']['end'][:10]}",
        "",
    ]
    counts = data.get("summary", {}).get("counts", {})
    if counts:
        lines.append("Counts:")
        for key, count in counts.items():
            lines.append(f"  {key}: {count}")
        lines.append("")

    by_source = data.get("summary", {}).get("by_source", {})
    if by_source:
        lines.append("Sources:")
        for source, info in by_source.items():
            type_text = ", ".join(info["types"])
            lines.append(f"  {source}: {info['count']} records ({type_text}), latest {info['latest']}")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = fetch_annotations(days=args.days)
    print(json.dumps(data, indent=2) if args.json else format_text(data))
