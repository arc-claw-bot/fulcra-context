# Fulcra Context

Fulcra gives agents and their humans scoped, secure access to read and write real-world context and shared human/agent memory: attention, events, location, calendar, health, wearables, and other streams. This skill is the read/context side via the Fulcra Life API, MCP server, and CLI. Use it for reusable agent integrations, and pair it with `fulcra-annotations` when an agent needs to write moments or values back.

## Quick Start

1. **Setup Fulcra account**: Download [Context iOS app](https://apps.apple.com/app/id1633037434) or visit [Portal](https://portal.fulcradynamics.com/)

2. **Authorize the agent**:
   ```bash
   fulcra-api auth login
   ```
   For remote chat agents, copy the printed device URL and code to the intended user in Discord, Telegram, Signal, or the active trusted channel. The user can approve from any browser while the CLI keeps polling on the agent host. Never send access tokens or credential files.

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

5. **Generate a local health dashboard summary**:
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
- Compose sleep analysis inside your agent runtime from raw context returned by this skill. This public package does not include LLM-calling report scripts.
- Supports: Cardiovascular (16), Respiratory (11), Activity (13), Sleep (6), Movement (15), Body measurements (8), Nutrition (23), Vitamins/Minerals (26), Blood/Lab (3), Reproductive (15), Symptoms (30), Environmental (9), Wellness events (7), Sports-specific (13), and more

### 📊 Sleep Analysis
- **fulcra_sleep_utils.py**: Accurate sleep duration using `sleep_cycles` API, fixes UTC date selection bug
- Use `fulcra_sleep_utils.py` output to compose briefings inside your agent runtime.
- **sleep_chart.py**: Publication-ready dark-theme visualizations

### 📝 Annotation Workflows
- Reading and correlating existing annotation data belongs in this skill.
- Creating annotation definitions or recording new annotation events should use the companion skill:
  <https://github.com/arc-claw-bot/fulcra-annotations-skill>
- Pair both skills for closed-loop workflows: read context with `fulcra-context`, then record user-approved events with `fulcra-annotations`.

### 🌍 Timezone Handling
- **fulcra_timezone.py**: Dynamic timezone from Fulcra API, automatic DST handling
- Never hardcode timezones or manually subtract UTC offsets

### 🚨 Monitoring
- **fulcra_data_watchdog.py**: Alert when biometric data goes stale (>12h)

## Key Features

✅ **Complete metrics coverage**: ALL 188 Fulcra metrics organized by category
✅ **Comprehensive health analysis**: Trend detection, correlation analysis, health alerts
✅ **Sleep context primitives**: Sleep + respiratory + activity + environment data for agent-authored briefings
✅ **Sleep stage math fix**: Use authoritative `total_time_asleep_ms` (matches Apple Health)
✅ **UTC date selection fix**: Today's local date = correct UTC bucket for sleep data
✅ **Timezone-aware**: Fetches user's timezone from Fulcra, handles DST automatically
✅ **Cross-referenced analysis**: Sleep + HRV + calendar + exercise + annotations
✅ **Production-ready**: 6,000+ lines of battle-tested utilities
✅ **Privacy-safe**: Generic paths, no hardcoded personal info, sanitized for publishing

## Environment Variables

```bash
# Override the Fulcra CLI command when the binary is not on PATH.
export FULCRA_CLI_COMMAND="fulcra-api"

# Output directory (choose an app-owned writable directory)
export FULCRA_OUTPUT_DIR=/custom/path

# Optional context files for local baselines or hypotheses
export CONTEXT_DIR=/custom/context/path

# Timezone override (default: from Fulcra API)
export OPENCLAW_TIMEZONE=America/New_York
```

## Cron Jobs

```bash
# Monitor data freshness
0 */4 * * * python3 scripts/fulcra_data_watchdog.py
```

## Links

- 🏠 [Fulcra Platform](https://fulcradynamics.com)
- 📖 [Developer Docs](https://fulcradynamics.github.io/developer-docs/)
- 🐍 [Python Client](https://github.com/fulcradynamics/fulcra-api-python)
- 🔗 [MCP Server](https://github.com/fulcradynamics/fulcra-context-mcp)
- 💬 [Discord](https://discord.com/invite/aunahVEnPU)
