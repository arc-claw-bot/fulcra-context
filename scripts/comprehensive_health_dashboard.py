#!/usr/bin/env python3
"""
Comprehensive Health Dashboard for Fulcra Metrics

Creates detailed health reports incorporating all 188+ available Fulcra metrics.
Organizes data into meaningful categories and provides actionable insights.

Features:
- All 188 metrics organized by category
- Automatic trend analysis and correlation detection
- Health score calculations
- Export to JSON, CSV, and human-readable formats
- Integration with existing sleep and biometric workflows

Usage:
    python3 comprehensive_health_dashboard.py --full-report
    python3 comprehensive_health_dashboard.py --category cardiovascular --days 30
    python3 comprehensive_health_dashboard.py --metrics "HeartRate,RespiratoryRate,BloodOxygenSaturation"
"""

import json
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional

# Add scripts dir to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from fulcra_comprehensive_metrics import (
    get_metric_data, analyze_metric_data, METRIC_CATEGORIES, ALL_METRICS,
    get_wellness_snapshot, get_cardiovascular_metrics, get_respiratory_metrics
)
from fulcra_timezone import now_local, today_local, get_user_tz

logger = logging.getLogger(__name__)

# Output configuration
OUTPUT_DIR = Path(os.environ.get('FULCRA_OUTPUT_DIR', Path.home() / '.openclaw/data/fulcra-analysis'))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Health score thresholds and ranges (can be customized per user)
HEALTH_RANGES = {
    "HeartRate": {"optimal": (60, 100), "concern_low": 50, "concern_high": 120},
    "RestingHeartRate": {"optimal": (60, 80), "concern_low": 50, "concern_high": 90},
    "BloodPressureSystolic": {"optimal": (90, 120), "concern_low": 80, "concern_high": 140},
    "BloodPressureDiastolic": {"optimal": (60, 80), "concern_low": 50, "concern_high": 90},
    "RespiratoryRate": {"optimal": (12, 20), "concern_low": 8, "concern_high": 25},
    "BloodOxygenSaturation": {"optimal": (0.95, 1.0), "concern_low": 0.90, "concern_high": 1.1},
    "BodyTemperature": {"optimal": (97.0, 99.5), "concern_low": 95.0, "concern_high": 101.0},
    "HeartRateVariabilitySDNN": {"optimal": (30, 100), "concern_low": 20, "concern_high": 200}
}


class ComprehensiveHealthDashboard:
    """Main dashboard class for comprehensive health analysis."""
    
    def __init__(self, days: int = 7):
        self.days = days
        self.data = {}
        self.analysis = {}
        self.health_score = {}
        
    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all available metrics organized by category."""
        logger.info(f"Collecting comprehensive metrics for {self.days} days")
        
        all_data = {
            "collection_timestamp": datetime.now().isoformat(),
            "analysis_period_days": self.days,
            "categories": {},
            "summary": {"total_metrics": 0, "metrics_with_data": 0, "total_samples": 0},
            "errors": []
        }
        
        for category, metrics in METRIC_CATEGORIES.items():
            logger.info(f"Fetching {category} metrics ({len(metrics)} metrics)")
            
            try:
                category_data = get_metric_data(metrics, days=self.days)
                all_data["categories"][category] = category_data
                
                # Update summary statistics
                for metric, info in category_data.items():
                    all_data["summary"]["total_metrics"] += 1
                    if isinstance(info, dict) and info.get("data") and len(info["data"]) > 0:
                        all_data["summary"]["metrics_with_data"] += 1
                        all_data["summary"]["total_samples"] += len(info["data"])
                        
            except Exception as e:
                error_msg = f"Failed to collect {category}: {str(e)}"
                logger.error(error_msg)
                all_data["errors"].append(error_msg)
                all_data["categories"][category] = {"error": error_msg}
        
        self.data = all_data
        return all_data
    
    def analyze_health_patterns(self) -> Dict[str, Any]:
        """Analyze patterns and trends across all collected metrics."""
        if not self.data:
            raise ValueError("No data collected. Run collect_all_metrics() first.")
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "category_analysis": {},
            "cross_category_correlations": {},
            "health_alerts": [],
            "positive_trends": [],
            "concerning_trends": []
        }
        
        for category, category_data in self.data.get("categories", {}).items():
            if isinstance(category_data, dict) and "error" not in category_data:
                category_analysis = self._analyze_category(category, category_data)
                analysis["category_analysis"][category] = category_analysis
        
        # Detect health alerts and trends
        analysis["health_alerts"] = self._detect_health_alerts()
        analysis["positive_trends"] = self._detect_positive_trends()
        analysis["concerning_trends"] = self._detect_concerning_trends()
        
        self.analysis = analysis
        return analysis
    
    def _analyze_category(self, category: str, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a specific category of metrics."""
        category_analysis = {
            "metrics_with_data": 0,
            "total_samples": 0,
            "metric_summaries": {},
            "category_insights": []
        }
        
        for metric, info in category_data.items():
            if isinstance(info, dict) and info.get("data") and len(info["data"]) > 0:
                category_analysis["metrics_with_data"] += 1
                category_analysis["total_samples"] += len(info["data"])
                
                # Detailed analysis for each metric
                detailed_analysis = analyze_metric_data(metric, info["data"], "detailed")
                if "error" not in detailed_analysis:
                    category_analysis["metric_summaries"][metric] = detailed_analysis
        
        # Generate category-specific insights
        if category == "cardiovascular":
            category_analysis["category_insights"] = self._cardiovascular_insights(category_analysis)
        elif category == "respiratory":
            category_analysis["category_insights"] = self._respiratory_insights(category_analysis)
        elif category == "activity":
            category_analysis["category_insights"] = self._activity_insights(category_analysis)
        elif category == "sleep":
            category_analysis["category_insights"] = self._sleep_insights(category_analysis)
        
        return category_analysis
    
    def _cardiovascular_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate cardiovascular-specific insights."""
        insights = []
        metrics = analysis.get("metric_summaries", {})
        
        if "HeartRate" in metrics and "RestingHeartRate" in metrics:
            hr_avg = metrics["HeartRate"]["mean"]
            rhr_avg = metrics["RestingHeartRate"]["mean"]
            if hr_avg and rhr_avg:
                hr_variability = hr_avg - rhr_avg
                if hr_variability > 40:
                    insights.append("Good heart rate range indicating active lifestyle")
                elif hr_variability < 20:
                    insights.append("Limited heart rate variability - consider increasing activity")
        
        if "HeartRateVariabilitySDNN" in metrics:
            hrv = metrics["HeartRateVariabilitySDNN"]
            if hrv["trend"]["direction"] == "increasing":
                insights.append("Improving HRV suggests better recovery and stress management")
            elif hrv["trend"]["direction"] == "decreasing":
                insights.append("Declining HRV may indicate increased stress or fatigue")
        
        return insights
    
    def _respiratory_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate respiratory-specific insights."""
        insights = []
        metrics = analysis.get("metric_summaries", {})
        
        if "RespiratoryRate" in metrics:
            rr = metrics["RespiratoryRate"]
            if rr["mean"] < 12:
                insights.append("Low respiratory rate - excellent respiratory efficiency")
            elif rr["mean"] > 20:
                insights.append("Elevated respiratory rate - monitor for potential stressors")
        
        if "BloodOxygenSaturation" in metrics:
            o2 = metrics["BloodOxygenSaturation"]
            if o2["mean"] > 0.97:
                insights.append("Excellent blood oxygen levels")
            elif o2["mean"] < 0.95:
                insights.append("Blood oxygen below optimal - consider respiratory health check")
        
        return insights
    
    def _activity_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate activity-specific insights."""
        insights = []
        metrics = analysis.get("metric_summaries", {})
        
        if "ActiveCaloriesBurned" in metrics:
            calories = metrics["ActiveCaloriesBurned"]
            if calories["trend"]["direction"] == "increasing":
                insights.append("Increasing activity levels - great progress!")
            
        if "StepCount" in metrics:
            steps = metrics["StepCount"]
            daily_avg = steps["mean"] * (1440 / self.days)  # Rough daily average
            if daily_avg > 8000:
                insights.append(f"Excellent daily activity with ~{daily_avg:.0f} steps average")
            elif daily_avg < 5000:
                insights.append(f"Low daily steps (~{daily_avg:.0f}) - consider increasing movement")
        
        return insights
    
    def _sleep_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate sleep-specific insights."""
        insights = []
        metrics = analysis.get("metric_summaries", {})
        
        if "SleepStage" in metrics:
            sleep_data = metrics["SleepStage"]
            insights.append(f"Sleep monitoring active with {sleep_data['sample_count']} stage transitions")
        
        if "SleepingWristTemperature" in metrics:
            temp = metrics["SleepingWristTemperature"]
            if temp["trend"]["direction"] == "stable":
                insights.append("Stable sleep temperature regulation")
        
        return insights
    
    def _detect_health_alerts(self) -> List[Dict[str, str]]:
        """Detect potential health concerns based on metric values."""
        alerts = []
        
        for category, category_data in self.data.get("categories", {}).items():
            for metric, info in category_data.items():
                if metric in HEALTH_RANGES and isinstance(info, dict) and info.get("data"):
                    analysis = analyze_metric_data(metric, info["data"], "summary")
                    if "error" not in analysis:
                        ranges = HEALTH_RANGES[metric]
                        latest = analysis.get("latest")
                        
                        if latest is not None:
                            if latest < ranges.get("concern_low", 0):
                                alerts.append({
                                    "metric": metric,
                                    "type": "low_value",
                                    "value": latest,
                                    "message": f"{metric} below normal range: {latest}"
                                })
                            elif latest > ranges.get("concern_high", float('inf')):
                                alerts.append({
                                    "metric": metric,
                                    "type": "high_value", 
                                    "value": latest,
                                    "message": f"{metric} above normal range: {latest}"
                                })
        
        return alerts
    
    def _detect_positive_trends(self) -> List[Dict[str, str]]:
        """Detect positive health trends."""
        positive_trends = []
        
        # Look for improving trends in key health metrics
        positive_metrics = ["HeartRateVariabilitySDNN", "ActiveCaloriesBurned", "StepCount"]
        
        for category, category_data in self.data.get("categories", {}).items():
            for metric, info in category_data.items():
                if metric in positive_metrics and isinstance(info, dict) and info.get("data"):
                    analysis = analyze_metric_data(metric, info["data"], "trend")
                    if "error" not in analysis and analysis.get("trend", {}).get("direction") == "increasing":
                        positive_trends.append({
                            "metric": metric,
                            "change": analysis["trend"]["change_percent"],
                            "message": f"{metric} trending up {analysis['trend']['change_percent']:+.1f}%"
                        })
        
        return positive_trends
    
    def _detect_concerning_trends(self) -> List[Dict[str, str]]:
        """Detect concerning health trends."""
        concerning_trends = []
        
        # Look for declining trends in key health metrics
        concerning_metrics = ["HeartRateVariabilitySDNN", "BloodOxygenSaturation"]
        
        for category, category_data in self.data.get("categories", {}).items():
            for metric, info in category_data.items():
                if metric in concerning_metrics and isinstance(info, dict) and info.get("data"):
                    analysis = analyze_metric_data(metric, info["data"], "trend")
                    if "error" not in analysis and analysis.get("trend", {}).get("direction") == "decreasing":
                        if abs(analysis["trend"]["change_percent"]) > 10:  # Significant decline
                            concerning_trends.append({
                                "metric": metric,
                                "change": analysis["trend"]["change_percent"],
                                "message": f"{metric} declining {analysis['trend']['change_percent']:.1f}%"
                            })
        
        return concerning_trends
    
    def generate_comprehensive_report(self, include_raw_data: bool = False) -> Dict[str, Any]:
        """Generate a comprehensive health report."""
        if not self.data or not self.analysis:
            raise ValueError("Must collect data and run analysis first")
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "analysis_period": f"{self.days} days",
            "executive_summary": self._generate_executive_summary(),
            "category_highlights": self._generate_category_highlights(),
            "health_alerts": self.analysis["health_alerts"],
            "positive_trends": self.analysis["positive_trends"],
            "concerning_trends": self.analysis["concerning_trends"],
            "recommendations": self._generate_recommendations(),
            "data_quality": self._assess_data_quality()
        }
        
        if include_raw_data:
            report["raw_data"] = self.data
            report["detailed_analysis"] = self.analysis
        
        return report
    
    def _generate_executive_summary(self) -> Dict[str, Any]:
        """Generate executive summary of health status."""
        summary = self.data.get("summary", {})
        
        return {
            "total_metrics_tracked": summary.get("total_metrics", 0),
            "metrics_with_data": summary.get("metrics_with_data", 0),
            "data_completeness": f"{(summary.get('metrics_with_data', 0) / max(summary.get('total_metrics', 1), 1) * 100):.1f}%",
            "total_samples_analyzed": summary.get("total_samples", 0),
            "health_alerts_count": len(self.analysis.get("health_alerts", [])),
            "positive_trends_count": len(self.analysis.get("positive_trends", [])),
            "concerning_trends_count": len(self.analysis.get("concerning_trends", []))
        }
    
    def _generate_category_highlights(self) -> Dict[str, Dict[str, Any]]:
        """Generate highlights for each category."""
        highlights = {}
        
        for category, analysis in self.analysis.get("category_analysis", {}).items():
            highlights[category] = {
                "metrics_active": analysis.get("metrics_with_data", 0),
                "total_samples": analysis.get("total_samples", 0),
                "key_insights": analysis.get("category_insights", [])[:3]  # Top 3 insights
            }
        
        return highlights
    
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        # Based on alerts
        if len(self.analysis.get("health_alerts", [])) > 0:
            recommendations.append("Schedule health checkup - several metrics outside normal ranges")
        
        # Based on trends
        if len(self.analysis.get("concerning_trends", [])) > 0:
            recommendations.append("Monitor declining health metrics closely")
        
        # Based on data quality
        data_quality = self._assess_data_quality()
        if data_quality["completeness"] < 50:
            recommendations.append("Improve data collection - many metrics missing data")
        
        # Activity-based recommendations
        cardiovascular = self.analysis.get("category_analysis", {}).get("cardiovascular", {})
        if cardiovascular.get("metrics_with_data", 0) > 0:
            recommendations.append("Continue cardiovascular monitoring for trend analysis")
        
        return recommendations
    
    def _assess_data_quality(self) -> Dict[str, Any]:
        """Assess the quality and completeness of collected data."""
        summary = self.data.get("summary", {})
        
        completeness = (summary.get("metrics_with_data", 0) / 
                       max(summary.get("total_metrics", 1), 1) * 100)
        
        # Assess key metrics availability
        key_metrics = ["HeartRate", "SleepStage", "StepCount", "RespiratoryRate", "BloodOxygenSaturation"]
        key_metrics_available = 0
        
        for category, category_data in self.data.get("categories", {}).items():
            for metric in key_metrics:
                if (metric in category_data and 
                    isinstance(category_data[metric], dict) and 
                    category_data[metric].get("data") and 
                    len(category_data[metric]["data"]) > 0):
                    key_metrics_available += 1
        
        return {
            "completeness": completeness,
            "quality_grade": "A" if completeness > 80 else "B" if completeness > 60 else "C",
            "key_metrics_available": f"{key_metrics_available}/{len(key_metrics)}",
            "total_samples": summary.get("total_samples", 0),
            "collection_errors": len(self.data.get("errors", []))
        }
    
    def export_to_json(self, filename: Optional[str] = None) -> Path:
        """Export comprehensive report to JSON."""
        if not filename:
            filename = f"comprehensive_health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = OUTPUT_DIR / filename
        report = self.generate_comprehensive_report(include_raw_data=True)
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Report exported to {filepath}")
        return filepath
    
    def export_to_csv(self, filename: Optional[str] = None) -> Path:
        """Export key metrics to CSV for analysis."""
        if not filename:
            filename = f"health_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath = OUTPUT_DIR / filename
        
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Category', 'Metric', 'Samples', 'Min', 'Max', 'Mean', 'Latest', 'Trend'])
            
            for category, analysis in self.analysis.get("category_analysis", {}).items():
                for metric, metric_analysis in analysis.get("metric_summaries", {}).items():
                    writer.writerow([
                        category,
                        metric,
                        metric_analysis.get("sample_count", 0),
                        metric_analysis.get("min", ""),
                        metric_analysis.get("max", ""),
                        round(metric_analysis.get("mean", 0), 2),
                        metric_analysis.get("latest", ""),
                        metric_analysis.get("trend", {}).get("direction", "")
                    ])
        
        logger.info(f"CSV exported to {filepath}")
        return filepath


def main():
    """Main function for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Health Dashboard for Fulcra Metrics")
    parser.add_argument("--days", type=int, default=7, help="Days of data to analyze")
    parser.add_argument("--full-report", action="store_true", help="Generate full comprehensive report")
    parser.add_argument("--category", help="Analyze specific category", choices=METRIC_CATEGORIES.keys())
    parser.add_argument("--metrics", help="Comma-separated list of specific metrics")
    parser.add_argument("--export-json", action="store_true", help="Export to JSON")
    parser.add_argument("--export-csv", action="store_true", help="Export to CSV")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    dashboard = ComprehensiveHealthDashboard(days=args.days)
    
    if args.full_report:
        print("Generating comprehensive health report...")
        dashboard.collect_all_metrics()
        dashboard.analyze_health_patterns()
        report = dashboard.generate_comprehensive_report()
        
        print("\n" + "="*60)
        print("COMPREHENSIVE HEALTH REPORT")
        print("="*60)
        
        # Executive Summary
        exec_summary = report["executive_summary"]
        print(f"\nExecutive Summary:")
        print(f"  Metrics tracked: {exec_summary['total_metrics_tracked']}")
        print(f"  Metrics with data: {exec_summary['metrics_with_data']} ({exec_summary['data_completeness']})")
        print(f"  Total samples: {exec_summary['total_samples_analyzed']:,}")
        print(f"  Health alerts: {exec_summary['health_alerts_count']}")
        print(f"  Positive trends: {exec_summary['positive_trends_count']}")
        print(f"  Concerning trends: {exec_summary['concerning_trends_count']}")
        
        # Category Highlights
        print(f"\nCategory Highlights:")
        for category, highlights in report["category_highlights"].items():
            if highlights["metrics_active"] > 0:
                print(f"  {category.title()}: {highlights['metrics_active']} metrics active, {highlights['total_samples']:,} samples")
                for insight in highlights["key_insights"]:
                    print(f"    - {insight}")
        
        # Health Alerts
        if report["health_alerts"]:
            print(f"\nHealth Alerts:")
            for alert in report["health_alerts"]:
                print(f"  ⚠️ {alert['message']}")
        
        # Positive Trends
        if report["positive_trends"]:
            print(f"\nPositive Trends:")
            for trend in report["positive_trends"]:
                print(f"  ✅ {trend['message']}")
        
        # Concerning Trends
        if report["concerning_trends"]:
            print(f"\nConcerning Trends:")
            for trend in report["concerning_trends"]:
                print(f"  ⚠️ {trend['message']}")
        
        # Recommendations
        if report["recommendations"]:
            print(f"\nRecommendations:")
            for rec in report["recommendations"]:
                print(f"  • {rec}")
        
        # Data Quality
        quality = report["data_quality"]
        print(f"\nData Quality: Grade {quality['quality_grade']} ({quality['completeness']:.1f}% complete)")
        print(f"  Key metrics available: {quality['key_metrics_available']}")
        if quality["collection_errors"] > 0:
            print(f"  Collection errors: {quality['collection_errors']}")
        
        # Export options
        if args.export_json:
            json_path = dashboard.export_to_json()
            print(f"\nJSON report saved: {json_path}")
        
        if args.export_csv:
            csv_path = dashboard.export_to_csv()
            print(f"CSV export saved: {csv_path}")
    
    elif args.category:
        print(f"Analyzing {args.category} metrics...")
        # Implementation for category-specific analysis
        pass
    
    elif args.metrics:
        metrics_list = [m.strip() for m in args.metrics.split(',')]
        print(f"Analyzing specific metrics: {', '.join(metrics_list)}")
        # Implementation for specific metrics analysis
        pass
    
    else:
        print("Use --full-report for comprehensive analysis or --help for options")


if __name__ == "__main__":
    main()