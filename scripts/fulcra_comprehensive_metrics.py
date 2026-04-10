#!/usr/bin/env python3
"""
Comprehensive Fulcra Metrics Utility

This module provides access to ALL 188 metrics available in the Fulcra API catalog.
Organized by category for easy discovery and use.

Usage:
    from fulcra_comprehensive_metrics import get_metric_data, METRIC_CATEGORIES
    
    # Get single metric
    data = get_metric_data("ActiveCaloriesBurned", days=7)
    
    # Get multiple metrics
    data = get_metric_data(["RespiratoryRate", "BloodOxygenSaturation"], days=1)
    
    # Browse available metrics by category
    print(METRIC_CATEGORIES["cardiovascular"])
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Add scripts dir to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from fulcra_timezone import now_local, today_local, get_user_tz

logger = logging.getLogger(__name__)

# Comprehensive metric categories - organized for discovery
METRIC_CATEGORIES = {
    "cardiovascular": [
        "HeartRate", "RestingHeartRate", "HeartRateVariabilitySDNN",
        "HeartRateRecoveryOneMinute", "BloodPressureDiastolic", "BloodPressureSystolic",
        "PeripheralPerfusionIndex", "AFibBurden", "HighHeartRateEvent", 
        "LowHeartRateEvent", "IrregularHeartRhythmEvent", "WalkingHeartRate",
        "SymptomRapidPoundingOrFlutteringHeartbeat", "SymptomSkippedHeartbeat",
        "SymptomChestTightnessOrPain"
    ],
    
    "respiratory": [
        "RespiratoryRate", "BloodOxygenSaturation", "PeakExpiratoryFlowRate",
        "ForcedExpiratoryVolumeOneSecond", "ForcedVitalCapacity", "SleepApneaEvent",
        "SleepingBreathingDisturbances", "SymptomShortnessOfBreath", "SymptomCoughing",
        "SymptomWheezing", "InhalerUse"
    ],
    
    "sleep": [
        "SleepStage", "SleepApneaEvent", "SleepingBreathingDisturbances",
        "SleepingWristTemperature", "SleepChanges", "SymptomNightSweats"
    ],
    
    "activity": [
        "StepCount", "ActiveCaloriesBurned", "BasalCaloriesBurned", "StairFlightsClimbed",
        "AppleWatchExerciseTime", "AppleWatchMoveTime", "AppleWatchStandTime",
        "PhysicalEffort", "WorkoutEffortScore", "EstimatedWorkoutEffortScore",
        "VO2Max", "LowCardioFitnessEvent", "SixMinuteWalkDistance"
    ],
    
    "movement": [
        "WalkingSpeed", "WalkingAsymmetry", "WalkingDoubleSupport", "WalkingSteadiness",
        "WalkingStrideLength", "WalkingSteadinessDecreaseEvent", "StandHour",
        "RunningSpeed", "RunningPower", "RunningGroundContactTime", "RunningStrideLength",
        "RunningVerticalOscillation", "CyclingSpeed", "CyclingCadence", "CyclingPower",
        "CyclingFunctionalThresholdPower"
    ],
    
    "body_measurements": [
        "Weight", "Height", "BodyMassIndex", "BodyFatPercentage", "LeanBodyMass",
        "WaistCircumference", "BodyTemperature", "BasalBodyTemperature"
    ],
    
    "nutrition": [
        "CaloriesConsumed", "DietaryCarbohydratesConsumed", "DietaryProteinConsumed",
        "TotalFatConsumed", "SaturatedFatConsumed", "MonounsaturatedFatConsumed",
        "PolyunsaturatedFatConsumed", "DietaryFiberConsumed", "DietarySugarConsumed",
        "DietaryCholesterolConsumed", "DietaryWaterConsumed", "DietaryCaffeineConsumed",
        "AlcoholicDrinksConsumed"
    ],
    
    "vitamins_minerals": [
        "DietaryVitaminAConsumed", "DietaryVitaminB6Consumed", "DietaryVitaminB12Consumed",
        "DietaryVitaminCConsumed", "DietaryVitaminDConsumed", "DietaryVitaminEConsumed",
        "DietaryVitaminKConsumed", "DietaryCalciumConsumed", "DietaryIronConsumed",
        "DietaryMagnesiumConsumed", "DietaryPotassiumConsumed", "DietaryZincConsumed",
        "DietaryBiotinConsumed", "DietaryFolateConsumed", "DietaryNiacinConsumed",
        "DietaryPantothenicAcidConsumed", "DietaryPhosphorusConsumed", "DietaryRiboflavinConsumed",
        "DietarySeleniumConsumed", "DietarySodiumConsumed", "DietaryThiaminConsumed",
        "DietaryChlorideConsumed", "DietaryChromiumConsumed", "DietaryCopperConsumed",
        "DietaryIodineConsumed", "DietaryManganeseConsumed", "DietaryMolybdenumConsumed"
    ],
    
    "blood_lab": [
        "BloodGlucose", "BloodAlcoholContent", "InsulinUnitsDelivered"
    ],
    
    "reproductive": [
        "MenstrualFlow", "OvulationTestResult", "PregnancyTestResult", "ProgesteroneTestResult",
        "CervicalMucusQuality", "ContraceptiveUse", "SexualActivity", "Pregnancy",
        "Lactation", "BleedingDuringPregnancy", "BleedingAfterPregnancy",
        "InfrequentMenstrualCycles", "IrregularMenstrualCycles", "IntermenstrualBleeding",
        "PersistentIntermenstrualBleeding", "ProlongedMenstrualPeriods"
    ],
    
    "symptoms": [
        "SymptomAbdominalCramps", "SymptomAcne", "SymptomBladderIncontinence",
        "SymptomBloating", "SymptomBreastPain", "SymptomChills", "SymptomConstipation",
        "SymptomDiarrhea", "SymptomDizziness", "SymptomDrySkin", "SymptomFainting",
        "SymptomFatigue", "SymptomFever", "SymptomGeneralizedBodyAche", "SymptomHairLoss",
        "SymptomHeadache", "SymptomHeartburn", "SymptomHotFlashes", "SymptomLossOfSmell",
        "SymptomLossOfTaste", "SymptomLowerBackPain", "SymptomMemoryLapse", "SymptomNausea",
        "SymptomPelvicPain", "SymptomRunnyNose", "SymptomSinusCongestion", "SymptomSoreThroat",
        "SymptomVaginalDryness", "SymptomVomiting"
    ],
    
    "environmental": [
        "EnvironmentalAudioLevel", "EnvironmentalAudioLevelIncreaseEvent",
        "EnvironmentalSoundReduction", "HeadphonesAudioLevel", "HeadphonesAudioLevelIncreaseEvent",
        "TimeInDaylight", "UVExposure", "WaterTemperature", "UnderwaterDepth"
    ],
    
    "wellness_events": [
        "HandwashingEvent", "ToothbrushingEvent", "MindfulSession", "FallCount",
        "ElectrodermalActivity", "MoodChanges", "AppetiteChange"
    ],
    
    "sports_specific": [
        "SwimmingStrokeCount", "DistanceTraveledSwimming", "RowingSpeed", 
        "DistanceTraveledRowing", "PaddleSportsSpeed", "DistanceTraveledPaddleSports",
        "CrossCountrySkiingSpeed", "DistanceTraveledCrossCountrySkiing",
        "DistanceTraveledDownhillSnowSports", "DistanceTraveledSkatingSports",
        "StairAscentSpeed", "StairDescentSpeed"
    ],
    
    "distance_travel": [
        "DistanceTraveledOnFoot", "DistanceTraveledCycling", "DistanceTraveledWithWheelchair",
        "WheelchairPushes"
    ],
    
    "fitness_points": [
        "NikeFuelPoints"
    ]
}

# Flatten all metrics for easy lookup
ALL_METRICS = []
for category, metrics in METRIC_CATEGORIES.items():
    ALL_METRICS.extend(metrics)

# Metric types for proper handling
METRIC_TYPES = {
    "cumulative": [
        "ActiveCaloriesBurned", "BasalCaloriesBurned", "StepCount", "StairFlightsClimbed",
        "AppleWatchExerciseTime", "AppleWatchMoveTime", "AppleWatchStandTime",
        "CaloriesConsumed", "AlcoholicDrinksConsumed", "DietaryWaterConsumed",
        "DistanceTraveledOnFoot", "DistanceTraveledCycling", "SwimmingStrokeCount",
        "FallCount", "InhalerUse", "InsulinUnitsDelivered", "WheelchairPushes",
        "SixMinuteWalkDistance", "TimeInDaylight", "NikeFuelPoints"
    ] + [m for m in ALL_METRICS if m.startswith("Dietary") and m.endswith("Consumed")],
    
    "discrete": [
        "HeartRate", "BloodPressureSystolic", "BloodPressureDiastolic", "RespiratoryRate",
        "BloodOxygenSaturation", "BodyTemperature", "Weight", "Height", "BodyMassIndex",
        "VO2Max", "BloodGlucose", "WalkingSpeed", "RunningSpeed", "CyclingSpeed"
    ],
    
    "event": [m for m in ALL_METRICS if "Event" in m or m.endswith("ingEvent")],
    
    "stage": ["SleepStage"],
    
    "scale": [m for m in ALL_METRICS if m.startswith("Symptom") or m in ["MenstrualFlow", "CervicalMucusQuality"]]
}


def get_fulcra_client():
    """Get authenticated Fulcra API client."""
    from fulcra_api.core import FulcraAPI
    api = FulcraAPI()
    
    token_path = os.path.expanduser('~/.config/fulcra/token.json')
    try:
        with open(token_path) as f:
            token_data = json.load(f)
        api.fulcra_cached_access_token = token_data['access_token']
        api.fulcra_cached_access_token_expiration = datetime.now() + timedelta(hours=1)
        return api
    except Exception as e:
        logger.error(f"Failed to load Fulcra token: {e}")
        raise


def get_metric_data(metric_names, days=7, start_date=None, end_date=None):
    """
    Fetch data for one or more metrics from Fulcra API.
    
    Args:
        metric_names: String or list of metric names to fetch
        days: Number of days to look back (ignored if start_date/end_date provided)
        start_date: Specific start date (datetime object)
        end_date: Specific end date (datetime object)
    
    Returns:
        Dict with metric names as keys, data as values
    """
    if isinstance(metric_names, str):
        metric_names = [metric_names]
    
    # Set up date range
    if start_date and end_date:
        start_dt = start_date
        end_dt = end_date
    else:
        today = today_local()
        user_tz = get_user_tz()
        end_dt = datetime(today.year, today.month, today.day, tzinfo=user_tz) + timedelta(days=1)
        start_dt = end_dt - timedelta(days=days)
    
    client = get_fulcra_client()
    results = {}
    
    for metric_name in metric_names:
        if metric_name not in ALL_METRICS:
            logger.warning(f"Unknown metric: {metric_name}")
            results[metric_name] = {"error": "Unknown metric", "data": []}
            continue
            
        try:
            logger.info(f"Fetching {metric_name} from {start_dt} to {end_dt}")
            data = client.metric_samples(start_dt.isoformat(), end_dt.isoformat(), metric_name)
            
            if isinstance(data, list):
                # Process and standardize the data
                processed_data = []
                for sample in data:
                    processed_sample = {
                        "start_date": sample.get("start_date"),
                        "end_date": sample.get("end_date"),
                        "value": sample.get("value"),
                        "metric": metric_name
                    }
                    processed_data.append(processed_sample)
                
                results[metric_name] = {
                    "data": processed_data,
                    "count": len(processed_data),
                    "metric_type": get_metric_type(metric_name),
                    "category": get_metric_category(metric_name)
                }
            else:
                results[metric_name] = {"error": "Unexpected data format", "data": []}
                
        except Exception as e:
            logger.error(f"Failed to fetch {metric_name}: {e}")
            results[metric_name] = {"error": str(e), "data": []}
    
    return results


def get_metric_type(metric_name):
    """Get the type classification for a metric."""
    for metric_type, metrics in METRIC_TYPES.items():
        if metric_name in metrics:
            return metric_type
    return "unknown"


def get_metric_category(metric_name):
    """Get the category for a metric."""
    for category, metrics in METRIC_CATEGORIES.items():
        if metric_name in metrics:
            return category
    return "unknown"


def analyze_metric_data(metric_name, data_list, analysis_type="summary"):
    """
    Analyze metric data and return insights.
    
    Args:
        metric_name: Name of the metric
        data_list: List of data samples
        analysis_type: Type of analysis ("summary", "trend", "detailed")
    
    Returns:
        Dict with analysis results
    """
    if not data_list:
        return {"error": "No data to analyze"}
    
    values = [float(sample["value"]) for sample in data_list if sample.get("value") is not None]
    
    if not values:
        return {"error": "No valid values to analyze"}
    
    analysis = {
        "metric": metric_name,
        "sample_count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "latest": values[-1] if values else None
    }
    
    if analysis_type in ["trend", "detailed"]:
        # Add trend analysis
        if len(values) >= 2:
            recent_half = values[len(values)//2:]
            early_half = values[:len(values)//2]
            
            recent_avg = sum(recent_half) / len(recent_half)
            early_avg = sum(early_half) / len(early_half)
            
            trend_pct = ((recent_avg - early_avg) / early_avg * 100) if early_avg != 0 else 0
            
            analysis["trend"] = {
                "direction": "increasing" if trend_pct > 5 else "decreasing" if trend_pct < -5 else "stable",
                "change_percent": round(trend_pct, 1),
                "recent_avg": round(recent_avg, 2),
                "early_avg": round(early_avg, 2)
            }
    
    if analysis_type == "detailed":
        # Add detailed statistics
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        analysis["median"] = sorted_values[n//2] if n % 2 == 1 else (sorted_values[n//2-1] + sorted_values[n//2]) / 2
        analysis["percentile_25"] = sorted_values[n//4] if n >= 4 else None
        analysis["percentile_75"] = sorted_values[3*n//4] if n >= 4 else None
        
        # Standard deviation
        mean_val = analysis["mean"]
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        analysis["std_dev"] = variance ** 0.5
    
    return analysis


def get_wellness_snapshot(days=1):
    """
    Get a comprehensive wellness snapshot with key metrics.
    Focuses on the most commonly used health indicators.
    """
    key_metrics = [
        "HeartRate", "RestingHeartRate", "HeartRateVariabilitySDNN",
        "RespiratoryRate", "BloodOxygenSaturation", "StepCount",
        "ActiveCaloriesBurned", "SleepStage", "BodyTemperature"
    ]
    
    return get_metric_data(key_metrics, days=days)


def get_activity_summary(days=7):
    """Get comprehensive activity metrics summary."""
    activity_metrics = METRIC_CATEGORIES["activity"] + METRIC_CATEGORIES["movement"]
    return get_metric_data(activity_metrics, days=days)


def get_cardiovascular_metrics(days=7):
    """Get all cardiovascular-related metrics."""
    return get_metric_data(METRIC_CATEGORIES["cardiovascular"], days=days)


def get_respiratory_metrics(days=7):
    """Get all respiratory-related metrics."""
    return get_metric_data(METRIC_CATEGORIES["respiratory"], days=days)


if __name__ == "__main__":
    """Example usage and testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fulcra Comprehensive Metrics")
    parser.add_argument("--metric", help="Metric name to fetch")
    parser.add_argument("--category", help="Category to fetch", choices=METRIC_CATEGORIES.keys())
    parser.add_argument("--days", type=int, default=7, help="Days to look back")
    parser.add_argument("--wellness", action="store_true", help="Get wellness snapshot")
    parser.add_argument("--list-categories", action="store_true", help="List all categories")
    parser.add_argument("--list-metrics", help="List metrics in category")
    
    args = parser.parse_args()
    
    if args.list_categories:
        print("Available categories:")
        for cat, metrics in METRIC_CATEGORIES.items():
            print(f"  {cat}: {len(metrics)} metrics")
    
    elif args.list_metrics:
        if args.list_metrics in METRIC_CATEGORIES:
            print(f"Metrics in {args.list_metrics}:")
            for metric in METRIC_CATEGORIES[args.list_metrics]:
                print(f"  {metric}")
        else:
            print(f"Unknown category: {args.list_metrics}")
    
    elif args.wellness:
        data = get_wellness_snapshot(days=args.days)
        print(json.dumps(data, indent=2, default=str))
    
    elif args.metric:
        data = get_metric_data(args.metric, days=args.days)
        print(json.dumps(data, indent=2, default=str))
    
    elif args.category:
        if args.category in METRIC_CATEGORIES:
            data = get_metric_data(METRIC_CATEGORIES[args.category], days=args.days)
            print(json.dumps(data, indent=2, default=str))
        else:
            print(f"Unknown category: {args.category}")
    
    else:
        print("Use --help for usage information")