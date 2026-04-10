#!/usr/bin/env python3
"""
Enhanced Fulcra Sleep Briefing with Comprehensive Metrics

Extends the original sleep briefing to include ALL available Fulcra metrics
that are relevant to sleep analysis and overall wellness tracking.

New metrics included:
- ActiveCaloriesBurned: Exercise intensity analysis
- RespiratoryRate: Breathing patterns during sleep
- BloodOxygenSaturation: Sleep-related oxygen levels
- BodyTemperature: Thermal regulation during sleep
- EnvironmentalAudioLevel: Sleep environment noise
- And many more...

Usage:
    python3 fulcra_enhanced_sleep_briefing.py
    python3 fulcra_enhanced_sleep_briefing.py --days 14  # Extended analysis period
"""

import json
import logging
import os
import sys
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Add scripts dir to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from fulcra_sleep_utils import get_fulcra_client, get_last_night_sleep, get_sleep_history
from fulcra_timezone import now_local, today_local, get_user_tz
from fulcra_comprehensive_metrics import (
    get_metric_data, analyze_metric_data, METRIC_CATEGORIES, 
    get_wellness_snapshot, get_cardiovascular_metrics, get_respiratory_metrics
)

logger = logging.getLogger(__name__)

# Enhanced output directory
OUTPUT_DIR = Path(os.environ.get('FULCRA_OUTPUT_DIR', Path.home() / '.openclaw/data/fulcra-analysis'))
OUTPUT_FILE = OUTPUT_DIR / "enhanced-sleep-briefing.json"
OUTPUT_TEXT_FILE = OUTPUT_DIR / "enhanced-sleep-briefing.txt"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LLM configuration
LLM_ENDPOINT = os.environ.get('LLM_ENDPOINT', 'http://localhost:18789/v1/chat/completions')
LLM_MODEL = os.environ.get('LLM_MODEL', 'openclaw')

# Context files
CONTEXT_DIR = Path(os.environ.get('CONTEXT_DIR', Path.home() / '.openclaw/memory/topics'))
CONTEXT_FILE = CONTEXT_DIR / "biometric-context.md"


def get_llm_token():
    """Get LLM API token from OpenClaw config or environment."""
    token = os.environ.get('LLM_API_TOKEN')
    if token:
        return token
    
    try:
        with open(os.path.expanduser("~/.openclaw/openclaw.json")) as f:
            config = json.load(f)
        return config.get("gateway", {}).get("auth", {}).get("token", "")
    except:
        return ""


def fetch_enhanced_metrics(days=7):
    """
    Fetch comprehensive metrics relevant to sleep and wellness analysis.
    
    Returns dict with categorized metrics data.
    """
    logger.info("Fetching enhanced metrics for comprehensive sleep analysis")
    
    # Priority metrics for sleep analysis
    sleep_relevant_metrics = [
        # Respiratory during sleep
        "RespiratoryRate", "BloodOxygenSaturation", "SleepApneaEvent", 
        "SleepingBreathingDisturbances",
        
        # Activity that affects sleep
        "ActiveCaloriesBurned", "AppleWatchExerciseTime", "StepCount",
        "PhysicalEffort", "WorkoutEffortScore",
        
        # Body regulation
        "BodyTemperature", "SleepingWristTemperature",
        
        # Environmental factors
        "EnvironmentalAudioLevel", "TimeInDaylight",
        
        # Wellness indicators
        "SymptomFatigue", "MoodChanges", "SymptomNightSweats",
        
        # Additional cardiovascular
        "BloodPressureSystolic", "BloodPressureDiastolic"
    ]
    
    results = {
        "sleep_relevant": {},
        "cardiovascular": {},
        "respiratory": {},
        "wellness_snapshot": {},
        "errors": []
    }
    
    # Fetch sleep-relevant metrics
    try:
        results["sleep_relevant"] = get_metric_data(sleep_relevant_metrics, days=days)
    except Exception as e:
        logger.error(f"Error fetching sleep-relevant metrics: {e}")
        results["errors"].append(f"Sleep metrics error: {e}")
    
    # Fetch cardiovascular metrics (comprehensive)
    try:
        results["cardiovascular"] = get_cardiovascular_metrics(days=days)
    except Exception as e:
        logger.error(f"Error fetching cardiovascular metrics: {e}")
        results["errors"].append(f"Cardiovascular metrics error: {e}")
    
    # Fetch respiratory metrics (comprehensive)
    try:
        results["respiratory"] = get_respiratory_metrics(days=days)
    except Exception as e:
        logger.error(f"Error fetching respiratory metrics: {e}")
        results["errors"].append(f"Respiratory metrics error: {e}")
    
    # Get wellness snapshot
    try:
        results["wellness_snapshot"] = get_wellness_snapshot(days=1)  # Recent snapshot
    except Exception as e:
        logger.error(f"Error fetching wellness snapshot: {e}")
        results["errors"].append(f"Wellness snapshot error: {e}")
    
    return results


def analyze_enhanced_metrics(enhanced_data):
    """
    Analyze the comprehensive metrics data and generate insights.
    """
    insights = {
        "respiratory_analysis": {},
        "activity_impact": {},
        "environmental_factors": {},
        "wellness_indicators": {},
        "comprehensive_score": {}
    }
    
    # Analyze respiratory metrics
    respiratory_metrics = enhanced_data.get("respiratory", {})
    sleep_relevant = enhanced_data.get("sleep_relevant", {})
    
    # Respiratory rate analysis
    if "RespiratoryRate" in respiratory_metrics and respiratory_metrics["RespiratoryRate"].get("data"):
        rr_analysis = analyze_metric_data(
            "RespiratoryRate", 
            respiratory_metrics["RespiratoryRate"]["data"], 
            "detailed"
        )
        insights["respiratory_analysis"]["breathing_rate"] = rr_analysis
    
    # Blood oxygen analysis
    if "BloodOxygenSaturation" in sleep_relevant and sleep_relevant["BloodOxygenSaturation"].get("data"):
        o2_analysis = analyze_metric_data(
            "BloodOxygenSaturation",
            sleep_relevant["BloodOxygenSaturation"]["data"],
            "detailed"
        )
        insights["respiratory_analysis"]["oxygen_saturation"] = o2_analysis
    
    # Activity impact on sleep
    activity_metrics = ["ActiveCaloriesBurned", "StepCount", "PhysicalEffort"]
    for metric in activity_metrics:
        if metric in sleep_relevant and sleep_relevant[metric].get("data"):
            analysis = analyze_metric_data(metric, sleep_relevant[metric]["data"], "trend")
            insights["activity_impact"][metric.lower()] = analysis
    
    # Environmental factors
    env_metrics = ["EnvironmentalAudioLevel", "TimeInDaylight"]
    for metric in env_metrics:
        if metric in sleep_relevant and sleep_relevant[metric].get("data"):
            analysis = analyze_metric_data(metric, sleep_relevant[metric]["data"], "summary")
            insights["environmental_factors"][metric.lower()] = analysis
    
    # Wellness indicators
    wellness_metrics = ["SymptomFatigue", "MoodChanges", "SymptomNightSweats"]
    for metric in wellness_metrics:
        if metric in sleep_relevant and sleep_relevant[metric].get("data"):
            analysis = analyze_metric_data(metric, sleep_relevant[metric]["data"], "summary")
            insights["wellness_indicators"][metric.lower()] = analysis
    
    return insights


def generate_enhanced_llm_analysis(sleep_data, enhanced_metrics, insights):
    """
    Generate comprehensive LLM analysis incorporating all available metrics.
    """
    # Build comprehensive prompt
    prompt = f"""You are a sleep and wellness expert analyzing comprehensive biometric data. Generate a thorough but readable analysis.

SLEEP DATA:
{json.dumps(sleep_data, indent=2, default=str)}

ENHANCED METRICS (includes 188 potential data streams):
{json.dumps(enhanced_metrics, indent=2, default=str)}

COMPUTATIONAL INSIGHTS:
{json.dumps(insights, indent=2, default=str)}

ANALYSIS REQUIREMENTS:
1. Sleep Quality Assessment: Use traditional metrics (stages, efficiency, fragmentation)
2. Respiratory Analysis: Incorporate breathing rate, oxygen saturation, sleep apnea events
3. Activity Impact: How daily activity affected sleep (calories burned, exercise timing)
4. Environmental Factors: Noise levels, daylight exposure impact
5. Wellness Correlation: Fatigue symptoms, mood changes, temperature regulation
6. Comprehensive Health Picture: Cardiovascular + respiratory + activity integration
7. Actionable Insights: Specific recommendations based on ALL available data

TONE: Professional but accessible, like a knowledgeable health coach
LENGTH: Comprehensive analysis (~800-1200 words)
AVOID: References to specific names, personal identifying information
FOCUS: Patterns, trends, actionable insights from the rich dataset

Generate a complete wellness briefing that showcases the power of comprehensive biometric monitoring."""

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_llm_token()}"
        }
        
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        response = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"LLM API error: {response.status_code} - {response.text}")
            return "LLM analysis temporarily unavailable. Raw data analysis shows comprehensive metrics collected successfully."
            
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return f"Enhanced metrics collected but LLM analysis failed: {e}"


def load_context_data():
    """Load biometric context and theories."""
    context_data = {"biometric_context": None, "supplements": None}
    
    try:
        if CONTEXT_FILE.exists():
            context_data["biometric_context"] = CONTEXT_FILE.read_text()
    except Exception as e:
        logger.debug(f"Context load failed: {e}")
    
    return context_data


def run_enhanced_briefing(days=7):
    """
    Main function to run comprehensive enhanced sleep briefing.
    """
    logger.info(f"Starting enhanced Fulcra sleep briefing with {days} days of data")
    
    try:
        # Get traditional sleep data
        sleep_data = {
            "last_night": get_last_night_sleep(),
            "sleep_history": get_sleep_history(days=days)
        }
        
        # Get comprehensive enhanced metrics
        enhanced_metrics = fetch_enhanced_metrics(days=days)
        
        # Analyze the enhanced data
        insights = analyze_enhanced_metrics(enhanced_metrics)
        
        # Load context
        context_data = load_context_data()
        
        # Build comprehensive result
        result = {
            "timestamp": datetime.now().isoformat(),
            "analysis_period_days": days,
            "sleep_data": sleep_data,
            "enhanced_metrics": enhanced_metrics,
            "computational_insights": insights,
            "context": context_data,
            "metrics_summary": {
                "sleep_relevant_count": len([k for k, v in enhanced_metrics.get("sleep_relevant", {}).items() 
                                           if v.get("data") and len(v["data"]) > 0]),
                "cardiovascular_count": len([k for k, v in enhanced_metrics.get("cardiovascular", {}).items() 
                                           if v.get("data") and len(v["data"]) > 0]),
                "respiratory_count": len([k for k, v in enhanced_metrics.get("respiratory", {}).items() 
                                        if v.get("data") and len(v["data"]) > 0]),
                "total_metrics_with_data": 0  # Will be calculated
            },
            "errors": enhanced_metrics.get("errors", [])
        }
        
        # Calculate total metrics with data
        total_metrics = 0
        for category in ["sleep_relevant", "cardiovascular", "respiratory", "wellness_snapshot"]:
            if category in enhanced_metrics:
                total_metrics += len([k for k, v in enhanced_metrics[category].items() 
                                    if isinstance(v, dict) and v.get("data") and len(v["data"]) > 0])
        result["metrics_summary"]["total_metrics_with_data"] = total_metrics
        
        # Generate LLM analysis
        llm_analysis = generate_enhanced_llm_analysis(sleep_data, enhanced_metrics, insights)
        result["llm_analysis"] = llm_analysis
        
        # Save comprehensive JSON
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        # Save human-readable text
        with open(OUTPUT_TEXT_FILE, 'w') as f:
            f.write(f"Enhanced Sleep & Wellness Analysis\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Analysis Period: {days} days\n")
            f.write(f"Metrics with Data: {total_metrics}\n")
            f.write("="*60 + "\n\n")
            f.write(llm_analysis)
            
            if result["errors"]:
                f.write("\n\nData Collection Notes:\n")
                for error in result["errors"]:
                    f.write(f"- {error}\n")
        
        logger.info(f"Enhanced briefing complete. {total_metrics} metrics with data collected.")
        return result
        
    except Exception as e:
        logger.error(f"Enhanced briefing failed: {e}")
        error_result = {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "status": "failed"
        }
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(error_result, f, indent=2)
        
        return error_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Fulcra Sleep Briefing with Comprehensive Metrics")
    parser.add_argument("--days", type=int, default=7, help="Days of data to analyze")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    result = run_enhanced_briefing(days=args.days)
    
    if result.get("error"):
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    else:
        print(f"Enhanced briefing complete:")
        print(f"- Analysis period: {args.days} days")
        print(f"- Metrics with data: {result['metrics_summary']['total_metrics_with_data']}")
        print(f"- Output: {OUTPUT_FILE}")
        print(f"- Text output: {OUTPUT_TEXT_FILE}")
        
        if result.get("errors"):
            print("Data collection notes:")
            for error in result["errors"]:
                print(f"  - {error}")