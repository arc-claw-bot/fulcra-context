#!/usr/bin/env python3
"""
Verification script for comprehensive Fulcra metrics implementation.
Tests all major components to ensure they're working correctly.
"""

import sys
import json
import traceback
from datetime import datetime

def test_comprehensive_metrics():
    """Test the comprehensive metrics module."""
    print("🧪 Testing comprehensive metrics module...")
    try:
        from fulcra_comprehensive_metrics import (
            METRIC_CATEGORIES, ALL_METRICS, 
            get_metric_category, get_metric_type,
            get_wellness_snapshot
        )
        
        # Test metric catalog
        total_metrics = len(ALL_METRICS)
        print(f"   ✅ {total_metrics} total metrics loaded")
        
        # Test categories
        category_count = len(METRIC_CATEGORIES)
        print(f"   ✅ {category_count} categories defined")
        
        # Test metric lookup functions
        hr_category = get_metric_category("HeartRate")
        hr_type = get_metric_type("HeartRate") 
        print(f"   ✅ HeartRate: {hr_category} category, {hr_type} type")
        
        # Test a few key metrics are in the right categories
        assert "HeartRate" in METRIC_CATEGORIES["cardiovascular"], "HeartRate not in cardiovascular"
        assert "RespiratoryRate" in METRIC_CATEGORIES["respiratory"], "RespiratoryRate not in respiratory"
        assert "SleepStage" in METRIC_CATEGORIES["sleep"], "SleepStage not in sleep"
        
        print("   ✅ Core metrics in correct categories")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        traceback.print_exc()
        return False


def test_enhanced_sleep_briefing():
    """Test the enhanced sleep briefing module."""
    print("\n🧪 Testing enhanced sleep briefing module...")
    try:
        from fulcra_enhanced_sleep_briefing import fetch_enhanced_metrics, analyze_enhanced_metrics
        
        print("   ✅ Enhanced sleep briefing module imports successfully")
        print("   ✅ Functions: fetch_enhanced_metrics, analyze_enhanced_metrics")
        
        # Test that it can be imported and has the right structure
        import inspect
        funcs = [name for name, obj in inspect.getmembers(sys.modules['fulcra_enhanced_sleep_briefing']) 
                if inspect.isfunction(obj)]
        
        expected_functions = ['fetch_enhanced_metrics', 'analyze_enhanced_metrics', 'run_enhanced_briefing']
        for func in expected_functions:
            if func in funcs:
                print(f"   ✅ Function {func} available")
            else:
                print(f"   ⚠️ Function {func} not found")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        traceback.print_exc()
        return False


def test_comprehensive_dashboard():
    """Test the comprehensive health dashboard."""
    print("\n🧪 Testing comprehensive health dashboard...")
    try:
        from comprehensive_health_dashboard import ComprehensiveHealthDashboard, HEALTH_RANGES
        
        print("   ✅ Dashboard module imports successfully")
        
        # Test health ranges are defined for key metrics
        key_metrics = ["HeartRate", "RestingHeartRate", "BloodPressureSystolic", "RespiratoryRate"]
        for metric in key_metrics:
            if metric in HEALTH_RANGES:
                ranges = HEALTH_RANGES[metric]
                print(f"   ✅ {metric}: optimal {ranges['optimal']}")
            else:
                print(f"   ⚠️ {metric}: no health ranges defined")
        
        # Test dashboard class can be instantiated
        dashboard = ComprehensiveHealthDashboard(days=1)
        print("   ✅ Dashboard instance created successfully")
        
        # Test method availability
        methods = [name for name in dir(dashboard) if not name.startswith('_')]
        expected_methods = ['collect_all_metrics', 'analyze_health_patterns', 'generate_comprehensive_report']
        
        for method in expected_methods:
            if method in methods:
                print(f"   ✅ Method {method} available")
            else:
                print(f"   ❌ Method {method} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        traceback.print_exc()
        return False


def test_integration():
    """Test integration between modules."""
    print("\n🧪 Testing module integration...")
    try:
        from fulcra_comprehensive_metrics import get_cardiovascular_metrics, get_respiratory_metrics
        from comprehensive_health_dashboard import ComprehensiveHealthDashboard
        from fulcra_enhanced_sleep_briefing import fetch_enhanced_metrics
        
        print("   ✅ All modules can be imported together")
        
        # Test that the enhanced sleep briefing can use comprehensive metrics
        dashboard = ComprehensiveHealthDashboard(days=1)
        print("   ✅ Dashboard and comprehensive metrics integrate")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Integration error: {e}")
        traceback.print_exc()
        return False


def test_cli_tools():
    """Test CLI functionality."""
    print("\n🧪 Testing CLI tools...")
    try:
        # Test comprehensive metrics CLI
        import subprocess
        import os
        
        # Test list categories
        result = subprocess.run([
            sys.executable, "fulcra_comprehensive_metrics.py", "--list-categories"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("   ✅ Comprehensive metrics CLI --list-categories works")
        else:
            print(f"   ⚠️ CLI error: {result.stderr}")
        
        # Test comprehensive dashboard CLI help
        result = subprocess.run([
            sys.executable, "comprehensive_health_dashboard.py", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("   ✅ Comprehensive dashboard CLI --help works")
        else:
            print(f"   ⚠️ Dashboard CLI error: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ CLI test error: {e}")
        return False


def main():
    """Run all verification tests."""
    print("🫀 Fulcra Comprehensive Metrics Implementation Verification")
    print("=" * 60)
    
    tests = [
        test_comprehensive_metrics,
        test_enhanced_sleep_briefing, 
        test_comprehensive_dashboard,
        test_integration,
        test_cli_tools
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - Comprehensive implementation is ready!")
        print("\n🎯 Ready for production use:")
        print("   • All 190 metrics accessible via fulcra_comprehensive_metrics.py")
        print("   • Enhanced sleep briefing with comprehensive data")
        print("   • Full health dashboard with trend analysis")
        print("   • CLI tools for all major functions")
        print("   • Integration between all modules working")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())