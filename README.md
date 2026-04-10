# Fulcra Context — Personal Data for AI Partners

Access your human's biometrics, sleep, activity, calendar, and location data via the Fulcra Life API. Now supports **ALL 188 Fulcra metrics** with comprehensive health analysis, trend detection, and actionable insights.

## Quick Start

1. **Setup Fulcra account**: Download [Context iOS app](https://apps.apple.com/app/id1633037434) or visit [Portal](https://portal.fulcradynamics.com/)

2. **Authorize the agent**:
   ```bash
   python3 scripts/fulcra_auth.py authorize
   ```

3. **Check last night's sleep**:
   ```python
   from fulcra_sleep_utils import get_last_night_sleep
   sleep = get_last_night_sleep()
   print(f"{sleep['total_sleep_h']}h sleep, {sleep['deep_pct']}% deep")
   ```

4. **Access comprehensive metrics**:
   ```python
   from fulcra_comprehensive_metrics import get_wellness_snapshot, get_cardiovascular_metrics
   
   # Quick wellness overview
   data = get_wellness_snapshot(days=1)
   
   # All cardiovascular metrics (16 total)
   cardio = get_cardiovascular_metrics(days=7)
   ```

5. **Generate full health dashboard**:
   ```python
   from comprehensive_health_dashboard import ComprehensiveHealthDashboard
   
   dashboard = ComprehensiveHealthDashboard(days=30)
   dashboard.collect_all_metrics()
   dashboard.analyze_health_patterns()
   report = dashboard.generate_comprehensive_report()
   ```

## What's Included

### 🫀 **NEW: Comprehensive Metrics (188 Total)**
- **fulcra_comprehensive_metrics.py**: Access ALL Fulcra metrics organized by category
- **comprehensive_health_dashboard.py**: Full health analysis with trend detection and alerts
- **fulcra_enhanced_sleep_briefing.py**: Sleep analysis enhanced with comprehensive metrics
- Supports: Cardiovascular (16), Respiratory (11), Activity (13), Sleep (6), Movement (15), Body measurements (8), Nutrition (23), Vitamins/Minerals (26), Blood/Lab (3), Reproductive (15), Symptoms (30), Environmental (9), Wellness events (7), Sports-specific (13), and more

### 📊 Sleep Analysis
- **fulcra_sleep_utils.py**: Accurate sleep duration using `sleep_cycles` API, fixes UTC date selection bug
- **fulcra_sleep_briefing.py**: Comprehensive LLM-generated analysis with cross-referenced data streams
- **sleep_chart.py**: Publication-ready dark-theme visualizations

### 📝 User Annotations
- **fulcra_annotations.py**: Coffee timing, mood, medications, subjective sleep quality
- Correlate user-logged events with objective biometric data

### 🌍 Timezone Handling
- **fulcra_timezone.py**: Dynamic timezone from Fulcra API, automatic DST handling
- Never hardcode timezones or manually subtract UTC offsets

### 🚨 Monitoring
- **fulcra_data_watchdog.py**: Alert when biometric data goes stale (>12h)
- **fulcra_auth.py**: OAuth2 lifecycle management with refresh tokens

## Key Features

✅ **Complete metrics coverage**: ALL 188 Fulcra metrics organized by category  
✅ **Comprehensive health analysis**: Trend detection, correlation analysis, health alerts  
✅ **Enhanced sleep briefing**: Traditional sleep + respiratory + activity + environment  
✅ **Sleep stage math fix**: Use authoritative `total_time_asleep_ms` (matches Apple Health)  
✅ **UTC date selection fix**: Today's local date = correct UTC bucket for sleep data  
✅ **Timezone-aware**: Fetches user's timezone from Fulcra, handles DST automatically  
✅ **Cross-referenced analysis**: Sleep + HRV + calendar + exercise + annotations  
✅ **Production-ready**: 6,000+ lines of battle-tested utilities  
✅ **Privacy-safe**: Generic paths, no hardcoded personal info, sanitized for publishing  

## Environment Variables

```bash
# Output directory (default: ~/.openclaw/data/fulcra-analysis)
export FULCRA_OUTPUT_DIR=/custom/path

# LLM for briefing generation (default: OpenClaw gateway)
export LLM_ENDPOINT=http://localhost:8080/v1/chat/completions
export LLM_MODEL=gpt-4
export LLM_API_TOKEN=your_token

# Context files (default: ~/.openclaw/memory/topics)
export CONTEXT_DIR=~/.openclaw/memory/topics

# Timezone override (default: from Fulcra API)
export OPENCLAW_TIMEZONE=America/New_York
```

## Cron Jobs

```bash
# Keep token fresh
0 */12 * * * python3 scripts/fulcra_auth.py refresh

# Pre-compute sleep briefing
0 */2 * * * python3 scripts/fulcra_sleep_briefing.py

# Monitor data freshness
0 */4 * * * python3 scripts/fulcra_data_watchdog.py
```

## Links

- 🏠 [Fulcra Platform](https://fulcradynamics.com)
- 📖 [Developer Docs](https://fulcradynamics.github.io/developer-docs/)
- 🐍 [Python Client](https://github.com/fulcradynamics/fulcra-api-python)
- 🔗 [MCP Server](https://github.com/fulcradynamics/fulcra-context-mcp)
- 💬 [Discord](https://discord.com/invite/aunahVEnPU)