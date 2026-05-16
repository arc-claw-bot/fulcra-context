---
name: fulcra-context
description: Access user-consented Fulcra context data including biometrics, sleep, activity, calendar, location, and the full Fulcra metric catalog via the Fulcra Life API, MCP server, and CLI. Use for read/context/analysis workflows; use the companion fulcra-annotations skill for creating or recording annotation events.
homepage: https://fulcradynamics.com
metadata: {"openclaw":{"emoji":"🫀","requires":{"bins":["python3","uv","jq"]},"version":"2026.05.16"}}
---

# Fulcra Context

Fulcra gives agents and their humans scoped, secure access to read and write real-world context and shared human/agent memory: attention, events, location, calendar, health, wearables, and other streams. This skill is the read/context side: biometrics, sleep, activity, location, calendar, and health metrics. Use the companion `fulcra-annotations` skill when an agent needs to write events or memories back.

## What This Enables

With Fulcra Context, agents can:
- Know how a user slept → adjust briefing intensity
- See heart rate / HRV trends → detect stress, suggest breaks
- Check location → context-aware suggestions (home vs. office vs. traveling)
- Read calendar → proactive meeting prep, schedule awareness
- Track workouts → recovery-aware task scheduling

## Privacy Model

- **OAuth2 per-user** — the user controls exactly what data the agent can access
- **User data stays user-owned** — Fulcra stores it, the agent gets delegated access only
- **Consent is revocable** — they can disconnect anytime
- **NEVER share Fulcra data publicly without explicit permission**

## Setup

### Option 1: MCP Server (Recommended)

Use Fulcra's hosted MCP server at `https://mcp.fulcradynamics.com/mcp` (Streamable HTTP transport, OAuth2 auth).

The user needs a Fulcra account via the [Context iOS app](https://apps.apple.com/app/id1633037434) or [Portal](https://portal.fulcradynamics.com/).

**Claude Desktop config** (claude_desktop_config.json):
```json
{
  "mcpServers": {
    "fulcra_context": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.fulcradynamics.com/mcp"]
    }
  }
}
```

**Or run locally via uvx:**
```json
{
  "mcpServers": {
    "fulcra_context": {
      "command": "uvx",
      "args": ["fulcra-context-mcp"]
    }
  }
}
```

Also tested with: Goose, Windsurf, VS Code. Open source: [github.com/fulcradynamics/fulcra-context-mcp](https://github.com/fulcradynamics/fulcra-context-mcp)

### Option 2: Fulcra CLI (Beta, Preferred for Automation)

The Fulcra CLI is the preferred interface for new skills, scheduled jobs, and repeatable workflows. It requires Python 3.11+, `uv`, and `jq`.

```bash
fulcra-api --help
```

Authenticate once with the CLI:

```bash
fulcra-api auth login
```

#### Remote/chat auth

Agents often run on a server while the user is in Discord, Telegram, Signal, or another remote chat. Do not assume the browser on the agent host is the user's browser.

When `fulcra-api auth login` prints a device authorization URL and user code:

1. Keep the CLI process running so it can poll for completion.
2. Send the short-lived device URL and code to the intended user in the current trusted chat.
3. Do not send access tokens, refresh tokens, credential files, raw private records, or direct capability URLs.
4. The user opens the URL on any device, confirms the displayed code, and approves access.
5. Verify completion with a non-token command such as `fulcra-api user-info`.

If the CLI also opens a browser on the agent host, ignore that local browser unless the user is actually on that machine. The device URL/code flow is the portable path for remote agents.

This creates `~/.config/fulcra/credentials.json`. The CLI refreshes access tokens as needed. The beta CLI currently exposes these JSON-output commands:

```bash
fulcra-api catalog
fulcra-api get-records HeartRate "1 day"
fulcra-api metric-time-series HeartRate "1 day"
fulcra-api sleep-stages "12 hours"
fulcra-api sleep-cycles "1 week"
fulcra-api calendar-events "1 day"
fulcra-api apple-workouts "1 week"
fulcra-api location-at-time "2026-05-05T12:00:00Z"
fulcra-api user-info
```

For automation, use the CLI-first adapter/service layer rather than hand-rolling `subprocess` calls. Set `FULCRA_CLI_COMMAND` only when the `fulcra-api` binary is not on PATH.

### Option 3: Python Service Layer

Use a shared service wrapper for skill scripts and scheduled workflows. It should prefer CLI credentials, normalize CLI JSON/JSONL output, and keep direct token handling inside the token manager fallback.

```python
from datetime import datetime, timezone, timedelta
from fulcra_data_service import get_service

api = get_service()
now = datetime.now(timezone.utc)
start = (now - timedelta(hours=12)).isoformat()
end = now.isoformat()

sleep = api.get_metric_samples(start, end, "SleepStage")
hr = api.get_metric_samples(start, end, "HeartRate")
events = api.get_calendar_events(start, end)
catalog = api.metrics_catalog()
```

### Authentication Boundary

This public skill does not ship token-printing helpers for chat. Authenticate with Fulcra's CLI or hosted MCP server, then let the scripts read through that already-authorized interface. CLI credentials are managed by Fulcra tooling in the user's home directory.

## Quick Commands

**Recommended:** Use the Fulcra CLI for new workflows, with the Python service layer as fallback for existing scripts.

### Check sleep (last night)

```bash
fulcra-api sleep-stages "12 hours" | jq .
```

```python
from datetime import datetime, timezone, timedelta
from fulcra_data_service import get_service

api = get_service()
now = datetime.now(timezone.utc)
start = (now - timedelta(hours=14)).isoformat()
end = now.isoformat()

sleep = api.get_metric_samples(start, end, "SleepStage")
# Stage values: 0=InBed, 1=Awake, 2=Core, 3=Deep, 4=REM
```

### Check heart rate (recent)

```bash
fulcra-api get-records HeartRate "2 hours" | jq .
```

```python
hr = api.get_metric_samples(
    (now - timedelta(hours=2)).isoformat(),
    now.isoformat(),
    "HeartRate"
)
values = [s['value'] for s in hr if 'value' in s]
avg_hr = sum(values) / len(values) if values else None
```

### Check today's calendar

```bash
fulcra-api calendar-events "1 day" | jq .
```

```python
day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
day_end = day_start + timedelta(hours=24)
events = api.get_calendar_events(day_start.isoformat(), day_end.isoformat())
for e in events:
    print(f"{e.get('title')} — {e.get('start_time')}")
```

### Available metrics

```python
catalog = api.metrics_catalog()
for metric in catalog:
    print(metric.get('name'), '-', metric.get('description'))
```

## Comprehensive Metrics Support (188 Total)

The fulcra-context skill now supports **ALL 188 metrics** available in the Fulcra API catalog, organized into meaningful categories:

### 🫀 Cardiovascular (16 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| HeartRate | Current stress/activity level |
| RestingHeartRate | Baseline cardiovascular fitness |
| HeartRateVariabilitySDNN | Recovery and autonomic nervous system state |
| BloodPressureSystolic | Upper blood pressure reading |
| BloodPressureDiastolic | Lower blood pressure reading |
| PeripheralPerfusionIndex | Circulation efficiency |
| AFibBurden | Atrial fibrillation monitoring |
| HighHeartRateEvent, LowHeartRateEvent | Cardiac event detection |
| IrregularHeartRhythmEvent | Arrhythmia detection |
| WalkingHeartRate | Exercise response |
| HeartRateRecoveryOneMinute | Post-exercise recovery |

### 🫁 Respiratory (11 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| RespiratoryRate | Breathing rate (breaths per minute) |
| BloodOxygenSaturation | Blood oxygen levels |
| PeakExpiratoryFlowRate | Lung function capacity |
| ForcedExpiratoryVolumeOneSecond | Detailed lung function |
| ForcedVitalCapacity | Maximum breathing capacity |
| SleepApneaEvent | Sleep breathing disruptions |
| SleepingBreathingDisturbances | Overall sleep respiratory health |
| InhalerUse | Respiratory medication tracking |

### 😴 Sleep (6 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| SleepStage | Sleep quality — REM, Deep, Light, Awake |
| SleepApneaEvent | Breathing interruptions during sleep |
| SleepingBreathingDisturbances | Overall sleep respiratory patterns |
| SleepingWristTemperature | Body temperature regulation during sleep |
| SleepChanges | Sleep pattern disruptions |

### 🏃 Activity & Exercise (13 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| StepCount | Daily movement and activity level |
| ActiveCaloriesBurned | Exercise intensity and energy expenditure |
| BasalCaloriesBurned | Resting metabolic rate |
| StairFlightsClimbed | Vertical activity and leg strength |
| AppleWatchExerciseTime | Structured exercise duration |
| AppleWatchMoveTime | Active movement minutes |
| AppleWatchStandTime | Anti-sedentary behavior |
| PhysicalEffort | Energy expenditure rate |
| WorkoutEffortScore | Exercise intensity scoring |
| VO2Max | Aerobic fitness capacity |
| SixMinuteWalkDistance | Cardiovascular endurance test |

### 🚶 Movement Analysis (15 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| WalkingSpeed | Gait velocity and mobility |
| WalkingAsymmetry | Balance and gait symmetry |
| WalkingDoubleSupport | Gait stability indicator |
| WalkingSteadiness | Fall risk assessment |
| WalkingStrideLength | Gait efficiency |
| RunningSpeed, RunningPower | Running performance |
| RunningGroundContactTime | Running efficiency |
| RunningStrideLength | Running biomechanics |
| CyclingSpeed, CyclingCadence, CyclingPower | Cycling performance |

### 📏 Body Measurements (8 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| Weight | Body mass tracking |
| Height | Growth monitoring |
| BodyMassIndex | Weight-to-height ratio |
| BodyFatPercentage | Body composition |
| LeanBodyMass | Muscle mass tracking |
| WaistCircumference | Metabolic health indicator |
| BodyTemperature | Core body temperature |
| BasalBodyTemperature | Fertility and metabolic tracking |

### 🍎 Nutrition (23 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| CaloriesConsumed | Daily energy intake |
| DietaryCarbohydratesConsumed | Carb intake tracking |
| DietaryProteinConsumed | Protein intake monitoring |
| TotalFatConsumed | Fat consumption |
| DietaryFiberConsumed | Digestive health tracking |
| DietaryWaterConsumed | Hydration monitoring |
| DietaryCaffeineConsumed | Stimulant intake |
| AlcoholicDrinksConsumed | Alcohol consumption |
| Plus 15 additional micronutrients... |

### 💊 Vitamins & Minerals (26 metrics)
| Category | Metrics Available |
|----------|-------------------|
| Vitamins | A, B6, B12, C, D, E, K, Biotin, Folate, Niacin, etc. |
| Minerals | Calcium, Iron, Magnesium, Potassium, Zinc, etc. |
| Trace Elements | Chromium, Copper, Iodine, Manganese, etc. |

### 🩸 Blood & Lab Values (3 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| BloodGlucose | Blood sugar monitoring |
| BloodAlcoholContent | Alcohol levels |
| InsulinUnitsDelivered | Diabetes management |

### 🤰 Reproductive Health (15 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| MenstrualFlow | Cycle tracking |
| OvulationTestResult | Fertility monitoring |
| PregnancyTestResult | Pregnancy detection |
| CervicalMucusQuality | Fertility indicators |
| ContraceptiveUse | Birth control tracking |
| Plus 10 additional reproductive metrics... |

### 🤒 Symptoms & Events (30 metrics)
| Category | Symptoms Tracked |
|----------|------------------|
| Pain | Headache, back pain, abdominal cramps, etc. |
| Respiratory | Coughing, wheezing, shortness of breath |
| Digestive | Nausea, heartburn, constipation, etc. |
| Neurological | Dizziness, fainting, memory lapse |
| General | Fatigue, fever, chills, etc. |

### 🌍 Environmental (9 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| EnvironmentalAudioLevel | Noise exposure monitoring |
| TimeInDaylight | Light exposure tracking |
| UVExposure | Sun exposure monitoring |
| WaterTemperature | Swimming/bathing conditions |
| UnderwaterDepth | Diving activity tracking |

### 🧘 Wellness Events (7 metrics)
| Metric | What It Tells You |
|--------|-------------------|
| HandwashingEvent | Hygiene habit tracking |
| ToothbrushingEvent | Dental hygiene monitoring |
| MindfulSession | Meditation and mindfulness |
| MoodChanges | Emotional state tracking |
| AppetiteChange | Eating behavior patterns |

### 🏊 Sports-Specific (13 metrics)
| Activity | Metrics Available |
|----------|-------------------|
| Swimming | Stroke count, distance, underwater depth |
| Rowing | Speed, distance, power |
| Cycling | Speed, cadence, power, functional threshold |
| Running | Speed, power, ground contact, stride length |
| Winter Sports | Cross-country skiing, downhill sports |
| Plus others... |

## Usage Examples

### Get Comprehensive Wellness Snapshot
```python
from fulcra_comprehensive_metrics import get_wellness_snapshot

# Get key health metrics from last 24 hours
data = get_wellness_snapshot(days=1)

# This includes: HeartRate, RestingHeartRate, HRV, RespiratoryRate, 
# BloodOxygenSaturation, StepCount, ActiveCaloriesBurned, SleepStage, BodyTemperature
```

### Get Category-Specific Metrics
```python
from fulcra_comprehensive_metrics import get_cardiovascular_metrics, get_respiratory_metrics

# All 16 cardiovascular metrics
cardio_data = get_cardiovascular_metrics(days=7)

# All 11 respiratory metrics  
resp_data = get_respiratory_metrics(days=7)
```

### Get Specific Metrics (Original Request)
```python
from fulcra_comprehensive_metrics import get_metric_data

# The originally requested metrics
specific_metrics = ['ActiveCaloriesBurned', 'RespiratoryRate', 'BloodOxygenSaturation']
data = get_metric_data(specific_metrics, days=7)

# Returns structured data with analysis
for metric, info in data.items():
    print(f"{metric}: {len(info['data'])} samples")
    print(f"  Category: {info['category']}")
    print(f"  Type: {info['metric_type']}")
```

### Comprehensive Health Dashboard
```python
from comprehensive_health_dashboard import ComprehensiveHealthDashboard

# Full health analysis with all 188 metrics
dashboard = ComprehensiveHealthDashboard(days=30)
dashboard.collect_all_metrics()
dashboard.analyze_health_patterns()
report = dashboard.generate_comprehensive_report()

# Export to files
dashboard.export_to_json()
dashboard.export_to_csv()
```

## Integration Patterns

### Morning Briefing
Check sleep + calendar + weather → compose a briefing calibrated to energy level.

### Stress-Aware Communication
Monitor HRV + heart rate → if elevated, keep messages brief and non-urgent.

### Proactive Recovery
After intense workout or poor sleep → suggest lighter schedule, remind about hydration.

### Travel Awareness
Location changes → adjust timezone handling, suggest local info, modify schedule expectations.

## Public Sharing and Synthetic Data

Most users should run this skill against their own consented Fulcra account, not a demo mode.

If an agent needs sample output for documentation, tests, screenshots, videos, or public sharing, generate a separate synthetic fixture and clearly label it as synthetic. Do not mix real biometrics with fake calendar or location data unless the user explicitly asks for that behavior.

Public-safe defaults:

- Use synthetic data for public examples and documentation.
- Do not publish real location, real calendar events, private notes, Magic Links, access tokens, or identifying data.
- If a workflow exposes `FULCRA_DEMO_MODE` or `--demo`, treat it as a local testing helper, not the recommended public path.

## Battle-Tested Utilities

The skill includes production-ready utilities for comprehensive sleep and biometric analysis:

### Annotations API

Read and correlate existing user-logged events with biometric data.

For creating annotation definitions or recording new annotation events, install and use the companion write-focused skill:

<https://github.com/arc-claw-bot/fulcra-annotations-skill>

Recommended boundary:

- `fulcra-context`: read Fulcra context and analyze health/activity/calendar/location data.
- `fulcra-annotations`: create annotation definitions and record user-approved events.

```python
from fulcra_annotations import fetch_annotations

data = fetch_annotations(days=7)
# Returns structured data:
# - User-logged events
# - Subjective ratings
# - Medication or supplement timing if the user records it
# - Notes and tags suitable for correlation
```

**Annotation Types:**
- **Moment**: timestamped events
- **Scale**: subjective 1-5 ratings
- **Numeric**: counts, dosages, or measurements
- **Boolean**: Yes/no events (future-proofed)
- **Duration**: Timed activities (future-proofed)

**Key Correlations:**
- Timing of user-logged events vs. sleep, HRV, and activity trends
- Subjective vs. objective sleep quality mismatches
- Medication, supplement, caffeine, workout, or stress notes if the user chooses to record them

### Sleep Stage Math

**CRITICAL:** Use `sleep_cycles.total_time_asleep_ms` for authoritative sleep duration — it matches Apple Health. Manually summing stage durations from `sleep_agg` undercounts by ~20% because it misses transitional periods.

```python
from fulcra_sleep_utils import get_last_night_sleep, get_sleep_history

# Last night's sleep with proper stage math
sleep = get_last_night_sleep()
# Returns: total_sleep_h, stages (dict), deep_pct, rem_pct, 
#          efficiency, fragmentation, bedtime/wake strings

# 7-day sleep trends
history = get_sleep_history(days=7)
```

**UTC Date Selection Fix:** Fulcra's `sleep_agg` API buckets by UTC calendar day. The bucket for a given UTC date contains sleep that ENDED on that UTC day. Using today's local date (not current UTC date) as the target fixes the "PM bug" where evening API calls return empty results.

### Timezone Handling

**NEVER hardcode timezones.** Use the shared timezone utility:

```python
from fulcra_timezone import get_user_tz, now_local, today_local, to_local

# User's timezone from Fulcra profile (handles DST automatically)
tz = get_user_tz()  # Returns ZoneInfo object

# Current time in user's local timezone
now = now_local()
today = today_local()

# Convert UTC datetime to user's local time
local_dt = to_local(utc_datetime)
```

**Features:**
- Fetches timezone from Fulcra user profile
- Disk caching (refreshed daily)
- Automatic DST handling via Python's `ZoneInfo`
- Fallback chain: API → cache → env var → America/New_York

### Sleep Context Pipeline

Fetch sleep context primitives, then compose any user-facing briefing inside the agent runtime:

```python
from fulcra_sleep_utils import get_last_night_sleep, get_sleep_history

last_night = get_last_night_sleep()
history = get_sleep_history(days=7)
```

**Data Integration:**
- Sleep metrics (stages, efficiency, fragmentation)
- Heart rate variability (HRV) and resting heart rate (RHR) trends
- Overnight heart rate curve (min/max/avg)
- Calendar meeting load (distinguishes real meetings from time blocks)
- Exercise/walk detection from step count and walking speed
- Location data for sleep context
- User-recorded events such as caffeine, medication, supplement, workout, or stress notes
- Subjective sleep quality vs. objective metrics

**LLM boundary:** This public skill does not call LLM endpoints. If an agent turns Fulcra context into a written briefing, keep that model/provider choice inside the user-approved agent runtime.

### Data Staleness Detection

Monitor biometric data freshness and alert on sync failures:

```python
from fulcra_data_watchdog import main

# Check if heart rate data is stale (>12h old)
# Exits 0 = OK, 1 = STALE (needs escalation)
main()
```

**Use case:** Apple Watch sync failures, Fulcra service issues, account problems. Run via cron every 2-4 hours.

### Chart Generation

Generate publication-ready sleep visualizations:

```python
from sleep_chart import create_chart

# Dark theme, health-tech aesthetic
create_chart(sleep_data, "sleep-analysis.png")
# Generates: donut chart, stage breakdown bar, 7-night trends,
# sleep+efficiency dual-axis charts
```

**Features:**
- Premium dark theme optimized for health data
- Sleep stage proportions with efficiency metrics
- 7-night deep sleep and total sleep trends
- Matplotlib-based, high DPI output

## Environment Configuration

The utilities support flexible deployment via environment variables:

```bash
# Data output directory (choose an app-owned writable directory)
export FULCRA_OUTPUT_DIR=/custom/path

# Optional context directory for local baselines or hypotheses
export CONTEXT_DIR=/custom/context/path

# User timezone override (default: from Fulcra API)
export OPENCLAW_TIMEZONE=America/New_York
```

## Deployment Patterns

### Cron Automation

```bash
# Data staleness check every 4 hours
0 */4 * * * python3 scripts/fulcra_data_watchdog.py || echo "STALE DATA ALERT"
```

### Integration with AI Agents

```python
# Fetch raw context and compose in the agent runtime
from fulcra_sleep_utils import get_last_night_sleep

sleep = get_last_night_sleep()

# Historical analysis
history = get_sleep_history(days=30)
avg_deep = sum(n['deep_pct'] for n in history) / len(history)

# Context-aware responses
if last_hrv < baseline_hrv * 0.8:
    tone = "brief and supportive"  # User is stressed
```

## Links

- [Fulcra Platform](https://fulcradynamics.com)
- [Developer Docs](https://fulcradynamics.github.io/developer-docs/)
- [Life API Reference](https://fulcradynamics.github.io/developer-docs/api-reference/)
- [Python Client](https://github.com/fulcradynamics/fulcra-api-python)
- [MCP Server](https://github.com/fulcradynamics/fulcra-context-mcp)
- [Demo Notebooks](https://github.com/fulcradynamics/demos)
- [Discord](https://discord.com/invite/aunahVEnPU)
