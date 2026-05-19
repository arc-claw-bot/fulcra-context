#!/usr/bin/env python3
"""
Fulcra Data Service - Centralized data layer for all Fulcra operations

This is the single source of truth for Fulcra data processing. All scripts should
import from here instead of duplicating timezone, parsing, and aggregation logic.

Key principles:
- ALL dates use LOCAL timezone for daily grouping
- Consistent error handling and fallbacks
- Standardized data structures
- No duplication of core logic
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pathlib import Path

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from fulcra_timezone import get_user_tz, now_local, today_local
from fulcra_cli_adapter import (
    download_library_file as fetch_library_file_content,
    fetch_calendar_events,
    fetch_calendars,
    fetch_catalog,
    fetch_library_files,
    fetch_location_updates,
    fetch_location_visits,
    fetch_metric_samples,
    fetch_metric_time_series,
    fetch_user_info,
    fetch_workouts,
)

class FulcraDataService:
    """Centralized service for all Fulcra data operations."""
    
    def __init__(self):
        self.api = None
        self.tz = get_user_tz()
        
    def _ensure_api(self):
        """Initialize API connection if not already done."""
        if self.api is not None:
            return self.api
            
        try:
            from fulcra_api.core import FulcraAPI

            token_candidates = [
                Path(os.environ["FULCRA_TOKEN_FILE"]) if os.environ.get("FULCRA_TOKEN_FILE") else None,
                Path.home() / '.config/fulcra/token.json',
            ]
            token_candidates = [path for path in token_candidates if path is not None]

            token_data = None
            for candidate in token_candidates:
                if candidate.exists():
                    token_data = json.loads(candidate.read_text())
                    break

            if token_data is None:
                raise FileNotFoundError("No Fulcra token file found in known locations")
            
            self.api = FulcraAPI()
            self.api.fulcra_cached_access_token = token_data['access_token']
            # Set expiration 1 hour from now
            self.api.fulcra_cached_access_token_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
            
            return self.api
        except Exception as e:
            raise Exception(f"Failed to initialize Fulcra API: {e}")
    
    def _to_local_date(self, timestamp_str):
        """Convert UTC timestamp to local date string (YYYY-MM-DD)."""
        try:
            dt_utc = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            dt_local = dt_utc.astimezone(self.tz)
            return dt_local.date().strftime('%Y-%m-%d')
        except Exception:
            # Fallback to UTC date slice
            return str(timestamp_str)[:10]

    def _normalize_date_input(self, value):
        """Convert date or datetime inputs to a CLI/API-friendly ISO string."""
        if isinstance(value, str):
            return value
        return value.isoformat()

    def _get_metric_samples(self, start_date, end_date, metric_name):
        """Fetch raw metric samples, preferring CLI when available."""
        start_iso = self._normalize_date_input(start_date)
        end_iso = self._normalize_date_input(end_date)

        samples = fetch_metric_samples(start_iso, end_iso, metric_name)
        if samples is not None:
            return samples

        try:
            api = self._ensure_api()
            return api.metric_samples(start_iso, end_iso, metric_name)
        except Exception:
            return []

    def _get_metric_time_series(self, start_date, end_date, metric_name, sample_rate=1, agg_function="mean"):
        """Fetch aggregated metric time series, preferring CLI when available."""
        start_iso = self._normalize_date_input(start_date)
        end_iso = self._normalize_date_input(end_date)

        series = fetch_metric_time_series(start_iso, end_iso, metric_name, sample_rate, agg_function)
        if series is not None:
            return series

        try:
            api = self._ensure_api()
            return api.metric_time_series(start_iso, end_iso, metric_name, sample_rate=sample_rate, agg_function=agg_function)
        except Exception:
            return []

    def _get_workouts(self, start_date, end_date):
        """Fetch workouts, preferring CLI when available."""
        start_iso = self._normalize_date_input(start_date)
        end_iso = self._normalize_date_input(end_date)

        workouts = fetch_workouts(start_iso, end_iso)
        if workouts is not None:
            return workouts

        try:
            api = self._ensure_api()
            if hasattr(api, "apple_workouts"):
                return api.apple_workouts(start_iso, end_iso)
            return api.workouts(start_iso, end_iso)
        except Exception:
            return []

    def _get_calendar_events(self, start_date, end_date):
        """Fetch calendar events, preferring CLI when available."""
        start_iso = self._normalize_date_input(start_date)
        end_iso = self._normalize_date_input(end_date)

        events = fetch_calendar_events(start_iso, end_iso)
        if events is not None:
            return events

        try:
            api = self._ensure_api()
            return api.calendar_events(start_iso, end_iso)
        except Exception:
            return []

    def _get_library_files(self, path: str):
        """Fetch file listing from Fulcra Library."""
        return fetch_library_files(path) or []

    def _download_library_file(self, path: str):
        """Download file content from Fulcra Library."""
        return fetch_library_file_content(path)

    def _get_calendars(self):
        """Fetch calendars, preferring CLI when available."""
        cals = fetch_calendars()
        if cals is not None:
            return cals

        try:
            api = self._ensure_api()
            if hasattr(api, 'calendars'):
                return api.calendars()
            return []
        except Exception:
            return []

    def _get_catalog(self):
        """Fetch the data catalog, preferring CLI when available."""
        cat = fetch_catalog()
        if cat is not None:
            return cat

        try:
            api = self._ensure_api()
            if hasattr(api, 'catalog'):
                return api.catalog()
            return []
        except Exception:
            return []

    def get_metric_samples(self, start_date, end_date, metric_name):
        """Return raw metric samples, preferring a Fulcra CLI when present."""
        samples = self._get_metric_samples(start_date, end_date, metric_name)
        return samples if isinstance(samples, list) else []

    def get_metric_time_series(self, start_date, end_date, metric_name, sample_rate=1, agg_function="mean"):
        """Return aggregated metric time series, preferring a Fulcra CLI when present."""
        series = self._get_metric_time_series(start_date, end_date, metric_name, sample_rate, agg_function)
        return series if isinstance(series, list) else []

    def get_calendar_events(self, start_date, end_date):
        """Return raw calendar events, preferring a Fulcra CLI when present."""
        events = self._get_calendar_events(start_date, end_date)
        return events if isinstance(events, list) else []

    def get_library_files(self, path: str):
        """Return file listing from Fulcra Library."""
        return self._get_library_files(path)

    def download_library_file(self, path: str):
        """Return downloaded file content from Fulcra Library."""
        return self._download_library_file(path)

    def get_calendars(self):
        """Return raw calendars, preferring a Fulcra CLI when present."""
        cals = self._get_calendars()
        return cals if isinstance(cals, list) else []

    def get_catalog(self):
        """Return the data catalog, preferring a Fulcra CLI when present."""
        cat = self._get_catalog()
        return cat if isinstance(cat, list) else []

    # SDK-style compatibility methods for migrated one-off scripts. Prefer the
    # explicit get_* methods in new code; these keep old analysis logic usable
    # while centralizing token handling and CLI-first data access.
    def metric_samples(self, start_time=None, end_time=None, metric_name=None, *args, **kwargs):
        if len(args) >= 3:
            start_time, end_time, metric_name = args[:3]
        start_time = start_time or kwargs.get("start") or kwargs.get("start_date")
        end_time = end_time or kwargs.get("end") or kwargs.get("end_date")
        metric_name = metric_name or kwargs.get("metric") or kwargs.get("metric_name")
        return self.get_metric_samples(start_time, end_time, metric_name)

    def calendar_events(self, start_time=None, end_time=None, *args, **kwargs):
        if len(args) >= 2:
            start_time, end_time = args[:2]
        start_time = start_time or kwargs.get("start") or kwargs.get("start_date")
        end_time = end_time or kwargs.get("end") or kwargs.get("end_date")
        return self.get_calendar_events(start_time, end_time)

    def apple_workouts(self, start_time=None, end_time=None, *args, **kwargs):
        if len(args) >= 2:
            start_time, end_time = args[:2]
        start_time = start_time or kwargs.get("start") or kwargs.get("start_date")
        end_time = end_time or kwargs.get("end") or kwargs.get("end_date")
        workouts = self._get_workouts(start_time, end_time)
        return workouts if isinstance(workouts, list) else []

    def workouts(self, start_time=None, end_time=None, *args, **kwargs):
        return self.apple_workouts(start_time, end_time, *args, **kwargs)

    def apple_location_updates(self, start_time=None, end_time=None, *args, **kwargs):
        if len(args) >= 2:
            start_time, end_time = args[:2]
        start_time = start_time or kwargs.get("start") or kwargs.get("start_date")
        end_time = end_time or kwargs.get("end") or kwargs.get("end_date")
        start_iso = self._normalize_date_input(start_time)
        end_iso = self._normalize_date_input(end_time)

        updates = fetch_location_updates(start_iso, end_iso)
        if updates is not None:
            return updates

        try:
            api = self._ensure_api()
            return api.apple_location_updates(start_time=start_iso, end_time=end_iso) or []
        except Exception:
            return []

    def apple_location_visits(self, start_time=None, end_time=None, *args, **kwargs):
        if len(args) >= 2:
            start_time, end_time = args[:2]
        start_time = start_time or kwargs.get("start") or kwargs.get("start_date")
        end_time = end_time or kwargs.get("end") or kwargs.get("end_date")
        start_iso = self._normalize_date_input(start_time)
        end_iso = self._normalize_date_input(end_time)

        visits = fetch_location_visits(start_iso, end_iso)
        if visits is not None:
            return visits

        try:
            api = self._ensure_api()
            return api.apple_location_visits(start_time=start_iso, end_time=end_iso) or []
        except Exception:
            return []

    def get_user_info(self):
        info = fetch_user_info()
        if isinstance(info, dict):
            return info
        try:
            return self._ensure_api().get_user_info() or {}
        except Exception:
            return {}

    def _annotation_call(self, method_name, start_time=None, end_time=None, *args, **kwargs):
        if len(args) >= 2:
            start_time, end_time = args[:2]
        start_time = start_time or kwargs.get("start") or kwargs.get("start_date")
        end_time = end_time or kwargs.get("end") or kwargs.get("end_date")
        try:
            api = self._ensure_api()
            method = getattr(api, method_name)
            return method(start_time, end_time) or []
        except Exception:
            return []

    def moment_annotations(self, start_time=None, end_time=None, *args, **kwargs):
        return self._annotation_call("moment_annotations", start_time, end_time, *args, **kwargs)

    def scale_annotations(self, start_time=None, end_time=None, *args, **kwargs):
        return self._annotation_call("scale_annotations", start_time, end_time, *args, **kwargs)

    def numeric_annotations(self, start_time=None, end_time=None, *args, **kwargs):
        return self._annotation_call("numeric_annotations", start_time, end_time, *args, **kwargs)

    def boolean_annotations(self, start_time=None, end_time=None, *args, **kwargs):
        return self._annotation_call("boolean_annotations", start_time, end_time, *args, **kwargs)

    def duration_annotations(self, start_time=None, end_time=None, *args, **kwargs):
        return self._annotation_call("duration_annotations", start_time, end_time, *args, **kwargs)
    
    def get_metric_daily(self, start_date, end_date, metric_name, precision=1):
        """
        Get daily aggregated metrics (avg/min/max/count) using LOCAL dates.
        
        Args:
            start_date: Date string (YYYY-MM-DD) or datetime
            end_date: Date string (YYYY-MM-DD) or datetime  
            metric_name: Fulcra metric name (e.g., 'HeartRateVariabilitySDNN')
            precision: Decimal places for rounding (default 1, use 2+ for SpO2/small values)
            
        Returns:
            Dict with date keys and {avg, min, max, count} values
        """
        start_iso = self._normalize_date_input(start_date)
        end_iso = self._normalize_date_input(end_date)
        samples = self._get_metric_samples(start_iso, end_iso, metric_name)
        if not isinstance(samples, list):
            return {}
        
        # Group by local date
        by_date = defaultdict(list)
        for sample in samples:
            ts = sample.get('start_date') or sample.get('start_time') or ''
            val = sample.get('value')
            if val is not None and ts:
                local_date = self._to_local_date(ts)
                by_date[local_date].append(float(val))
        
        # Aggregate
        result = {}
        for date, values in sorted(by_date.items()):
            if values:
                result[date] = {
                    'avg': round(sum(values) / len(values), precision),
                    'min': round(min(values), precision), 
                    'max': round(max(values), precision),
                    'count': len(values),
                }
        
        return result
    
    def get_nutrition_daily(self, start_date, end_date):
        """
        Get daily nutrition totals using LOCAL dates.
        
        DEDUPLICATES by HKExternalUUID to fix double-counting issues from
        food tracking apps that sync the same entries multiple times.
        
        Returns:
            Dict with metric names as keys, each containing date-keyed daily totals
        """
        metrics = [
            'CaloriesConsumed', 'DietaryProteinConsumed', 'TotalFatConsumed',
            'DietaryCarbohydratesConsumed', 'DietaryFiberConsumed', 'DietarySugarConsumed'
        ]
        
        nutrition = {}
        for metric in metrics:
            samples = self._get_metric_samples(start_date, end_date, metric)
            if not isinstance(samples, list):
                continue

            # DEDUPLICATION: Track unique UUIDs to prevent double-counting
            seen_uuids = set()
            deduped_samples = []

            for sample in samples:
                # Use HKExternalUUID from extras for deduplication
                extras = sample.get('extras', {})
                external_uuid = extras.get('HKExternalUUID')

                if external_uuid:
                    if external_uuid not in seen_uuids:
                        seen_uuids.add(external_uuid)
                        deduped_samples.append(sample)
                    # Skip if we've already seen this UUID
                else:
                    # If no UUID, include it (rare case)
                    deduped_samples.append(sample)

            # Group by local date and sum (don't average)
            by_date = defaultdict(list)
            for sample in deduped_samples:
                ts = sample.get('start_date') or sample.get('start_time') or ''
                val = sample.get('value')
                if val is not None and ts:
                    local_date = self._to_local_date(ts)
                    by_date[local_date].append(float(val))

            # Sum for daily totals
            daily_totals = {}
            for date, values in sorted(by_date.items()):
                if values:
                    total = sum(values)
                    daily_totals[date] = {
                        'total': round(total, 1),
                        'avg': round(total, 1),  # For compatibility
                        'count': len(values),
                        'dedupe_count': len(samples) if isinstance(samples, list) else 0,  # Original count before dedup
                    }

            # Clean up metric name
            clean_name = metric.replace('Dietary', '').replace('Consumed', '').replace('Total', '')
            nutrition[clean_name] = daily_totals
                
        return nutrition
    
    def get_workouts_daily(self, start_date, end_date):
        """Get workouts grouped by LOCAL date."""
        workouts = self._get_workouts(start_date, end_date)
        if not isinstance(workouts, list):
            return []
        
        result = []
        for workout in workouts:
            start_ts = str(workout.get('start_date', ''))
            if not start_ts:
                continue
                
            local_date = self._to_local_date(start_ts)
            
            # Process workout stats
            hr_stats = workout.get('heart_rate', {})
            stats = workout.get('statistics', {})
            active_cal = stats.get('HKQuantityTypeIdentifierActiveEnergyBurned', {})
            distance = stats.get('HKQuantityTypeIdentifierDistanceWalkingRunning', {})
            
            duration_sec = workout.get('duration', 0)
            activity = workout.get('workout_activity_type', 'unknown')
            
            # Detect phantom workouts
            extras = workout.get('extras', {})
            is_indoor = extras.get('HKIndoorWorkout') == 1
            is_phantom = is_indoor and duration_sec > 7200  # >2h indoor = suspect
            
            result.append({
                'date': local_date,
                'activity': activity,
                'duration_min': round(duration_sec / 60, 1),
                'hr_avg': round(hr_stats.get('average', 0), 1),
                'hr_max': hr_stats.get('maximum', 0),
                'hr_min': hr_stats.get('minimum', 0),
                'active_cal': round(active_cal.get('sum', 0)),
                'distance_mi': round(distance.get('sum', 0), 2) if distance else 0,
                'is_indoor': is_indoor,
                'is_phantom': is_phantom,
                'start_time': start_ts,
            })
        
        return result
    
    def get_calendar_daily(self, start_date, end_date):
        """Get calendar events grouped by LOCAL date."""
        events = self._get_calendar_events(start_date, end_date)
        if not isinstance(events, list):
            return {}
        
        # Import meeting detection if available
        try:
            from fulcra_calendar_utils import is_real_meeting
        except ImportError:
            is_real_meeting = lambda e: bool(e.get('attendees') or e.get('participants'))
        
        # Deduplicate events by (title, start_time) tuple
        seen_events = set()
        deduped_events = []
        
        for event in events:
            title = event.get('title', 'Untitled')
            start_ts = event.get('start_date', '')
            
            # Create dedup key from title + start time (to minute precision)
            dedup_key = (title.strip(), start_ts[:16])  # YYYY-MM-DDTHH:MM
            
            if dedup_key not in seen_events:
                seen_events.add(dedup_key)
                deduped_events.append(event)
        
        by_date = defaultdict(lambda: {"total": 0, "real": 0, "events": []})
        
        for event in deduped_events:
            start_ts = str(event.get('start_date', ''))
            if not start_ts:
                continue
                
            local_date = self._to_local_date(start_ts)
            by_date[local_date]["total"] += 1
            by_date[local_date]["events"].append({
                'title': event.get('title', 'Untitled'),
                'start_time': start_ts,
                'attendees': len(event.get('attendees', []))
            })
            
            if is_real_meeting(event):
                by_date[local_date]["real"] += 1
        
        return dict(by_date)


# Global service instance
_service = None

def get_service():
    """Get the global FulcraDataService instance."""
    global _service
    if _service is None:
        _service = FulcraDataService()
    return _service


# Convenience functions that other scripts can import directly
def get_library_files(path: str):
    """Get library files - convenience wrapper."""
    return get_service().get_library_files(path)

def download_library_file(path: str):
    """Download library file - convenience wrapper."""
    return get_service().download_library_file(path)

def get_catalog():
    """Get catalog - convenience wrapper."""
    return get_service().get_catalog()

def get_metric_daily(start_date, end_date, metric_name):
    """Get daily metrics - convenience wrapper."""
    return get_service().get_metric_daily(start_date, end_date, metric_name)

def get_metric_time_series(start_date, end_date, metric_name, sample_rate=1, agg_function="mean"):
    """Get aggregated time series - convenience wrapper."""
    return get_service().get_metric_time_series(start_date, end_date, metric_name, sample_rate, agg_function)

def get_nutrition_daily(start_date, end_date):
    """Get daily nutrition - convenience wrapper."""
    return get_service().get_nutrition_daily(start_date, end_date)

def get_workouts_daily(start_date, end_date):
    """Get daily workouts - convenience wrapper."""
    return get_service().get_workouts_daily(start_date, end_date)

def get_calendar_daily(start_date, end_date):
    """Get daily calendar - convenience wrapper."""
    return get_service().get_calendar_daily(start_date, end_date)


# Migration helpers for existing scripts
def parse_metric_daily(samples):
    """DEPRECATED: Use get_metric_daily() instead."""
    # This is here for backward compatibility during migration
    service = get_service()
    by_date = defaultdict(list)
    
    for s in samples:
        ts = s.get('start_date') or s.get('start_time') or ''
        val = s.get('value')
        if val is not None and ts:
            local_date = service._to_local_date(ts)
            by_date[local_date].append(float(val))
    
    result = {}
    for date, vals in sorted(by_date.items()):
        if vals:
            result[date] = {
                'avg': round(sum(vals) / len(vals), 1),
                'min': round(min(vals), 1),
                'max': round(max(vals), 1),
                'count': len(vals),
            }
    
    return result

def parse_nutrition_daily(samples):
    """DEPRECATED: Use get_nutrition_daily() instead."""
    # This is here for backward compatibility during migration
    service = get_service()
    by_date = defaultdict(list)
    
    for s in samples:
        ts = s.get('start_date') or s.get('start_time') or ''
        val = s.get('value')
        if val is not None and ts:
            local_date = service._to_local_date(ts)
            by_date[local_date].append(float(val))
    
    result = {}
    for date, vals in sorted(by_date.items()):
        if vals:
            total = sum(vals)
            result[date] = {
                'total': round(total, 1),
                'avg': round(total, 1),
                'count': len(vals),
            }
    
    return result
