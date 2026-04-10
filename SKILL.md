---
name: fulcra-context
description: Access your human's personal context data (biometrics, sleep, activity, calendar, location) via the Fulcra Life API and MCP server. NOW SUPPORTS ALL 188 FULCRA METRICS with comprehensive health analysis. Requires human's Fulcra account + OAuth2 consent.
homepage: https://fulcradynamics.com
metadata: {"openclaw":{"emoji":"🫀","requires":{"bins":["curl"]},"primaryEnv":"FULCRA_ACCESS_TOKEN","version":"2026.04.10"}}
---

# Fulcra Context — Personal Data for AI Partners

Give your agent situational awareness. With your human's consent, access their biometrics, sleep, activity, location, and calendar data from the Fulcra Life API.

## What This Enables

With Fulcra Context, you can:
- Know how your human slept → adjust morning briefing intensity
- See heart rate / HRV trends → detect stress, suggest breaks
- Check location → context-aware suggestions (home vs. office vs. traveling)
- Read calendar → proactive meeting prep, schedule awareness
- Track workouts → recovery-aware task scheduling

## Privacy Model

- **OAuth2 per-user** — your human controls exactly what data you see
- **Their data stays theirs** — Fulcra stores it, you get read access only
- **Consent is revocable** — they can disconnect anytime
- **NEVER share your human's Fulcra data publicly without explicit permission**

## Setup

### Option 1: MCP Server (Recommended)

Use Fulcra's hosted MCP server at `https://mcp.fulcradynamics.com/mcp` (Streamable HTTP transport, OAuth2 auth).

Your human needs a Fulcra account (free via the [Context iOS app](https://apps.apple.com/app/id1633037434) or [Portal](https://portal.fulcradynamics.com/)).

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
      "args": ["fulcra-context-mcp@latest"]
    }
  }
}
```

Also tested with: Goose, Windsurf, VS Code. Open source: [github.com/fulcradynamics/fulcra-context-mcp](https://github.com/fulcradynamics/fulcra-context-mcp)

### Option 2: Direct API Access

1. Your human creates a Fulcra account
2. They generate an access token via the [Python client](https://github.com/fulcradynamics/fulcra-api-python) or Portal
3. Store the token: `skills.entries.fulcra-context.apiKey` in openclaw.json

### Option 3: Python Client (Tested & Proven)

```bash
pip3 install fulcra-api
```

```python
from fulcra_api.core import FulcraAPI

api = FulcraAPI()
api.authorize()  # Opens device flow — human visits URL and logs in

# Now you have access:
sleep = api.metric_samples(start, end, "SleepStage")
hr = api.metric_samples(start, end, "HeartRate")
events = api.calendar_events(start, end)
catalog = api.metrics_catalog()
```

Save the token for automation:
```python
import json
import base64

# Extract user_id from JWT (more reliable than API call)
def extract_user_id(access_token):
    encoded = access_token.split('.')[1]
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += '=' * padding
    payload = json.loads(base64.urlsafe_b64decode(encoded))
    return payload.get("sub")

token_data = {
    "access_token": api.fulcra_cached_access_token,
    "expiration": api.fulcra_cached_access_token_expiration.isoformat(),
    "user_id": extract_user_id(api.fulcra_cached_access_token),
    "refresh_token": getattr(api, 'fulcra_cached_refresh_token', None)
}
with open(os.path.expanduser("~/.config/fulcra/token.json"), "w") as f:
    json.dump(token_data, f, indent=2)
```

**Important:** The `user_id` is extracted from the JWT's `sub` claim. This is required for calendar and some other endpoints. The auth script (`fulcra_auth.py`) handles this automatically.

Token expires in ~24h. Use the built-in token manager for automatic refresh (see below).

### Token Lifecycle Management

The skill includes `scripts/fulcra_auth.py` which handles the full OAuth2 lifecycle — including **refresh tokens** so your human only authorizes once.

```bash
# First-time setup (interactive — human approves via browser)
python3 scripts/fulcra_auth.py authorize

# Refresh token before expiry (automatic, no human needed)
python3 scripts/fulcra_auth.py refresh

# Check token status
python3 scripts/fulcra_auth.py status

# Get current access token (auto-refreshes if needed, for piping)
export FULCRA_ACCESS_TOKEN=$(python3 scripts/fulcra_auth.py token)
```

**How it works:**
- `authorize` runs the Auth0 device flow and saves both the access token AND refresh token
- `refresh` uses the saved refresh token to get a new access token — no human interaction
- `token` prints the access token (auto-refreshing if expired) — perfect for cron jobs and scripts

**Set up a cron job to keep the token fresh:**

For OpenClaw agents, add a cron job that refreshes the token every 12 hours:
```
python3 /path/to/skills/fulcra-context/scripts/fulcra_auth.py refresh
```

Token data is stored at `~/.config/fulcra/token.json` (permissions restricted to owner).

## Quick Commands

**Recommended:** Use the Python client for reliable data access. The REST API endpoints vary by metric type.

### Check sleep (last night)

```python
from datetime import datetime, timezone, timedelta
from fulcra_api.core import FulcraAPI

api = FulcraAPI()
# Load token (see Token Lifecycle section)
now = datetime.now(timezone.utc)
start = (now - timedelta(hours=14)).isoformat()
end = now.isoformat()

sleep = api.metric_samples(start, end, "SleepStage")
# Stage values: 0=InBed, 1=Awake, 2=Core, 3=Deep, 4=REM
```

### Check heart rate (recent)

```python
hr = api.metric_samples(
    (now - timedelta(hours=2)).isoformat(),
    now.isoformat(),
    "HeartRate"
)
values = [s['value'] for s in hr if 'value' in s]
avg_hr = sum(values) / len(values) if values else None
```

### Check today's calendar

```python
day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
day_end = day_start + timedelta(hours=24)
events = api.calendar_events(day_start.isoformat(), day_end.isoformat())
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

## Demo Mode

For public demos (VC pitches, livestreams, conferences), enable demo mode to swap in synthetic calendar and location data while keeping real biometrics.

### Activation

```bash
# Environment variable (recommended for persistent config)
export FULCRA_DEMO_MODE=true

# Or pass --demo flag to collect_briefing_data.py
python3 collect_briefing_data.py --demo
```

### What changes in demo mode

| Data Type | Demo Mode | Normal Mode |
|-----------|-----------|-------------|
| Sleep, HR, HRV, Steps | ✅ Real data | ✅ Real data |
| Calendar events | 🔄 Synthetic (rotating schedules) | ✅ Real data |
| Location | 🔄 Synthetic (curated NYC spots) | ✅ Real data |
| Weather | ✅ Real data | ✅ Real data |

### Transparency

- Output JSON includes `"demo_mode": true` at the top level
- Calendar and location objects include `"demo_mode": true`
- When presenting to humans, include a subtle "📍 Demo mode" indicator

### What's safe to share publicly

- ✅ Biometric trends, sleep quality, step counts, HRV — cleared for public
- ✅ Synthetic calendar and location (demo mode) — designed for public display
- ❌ NEVER share real location, real calendar events, or identifying data

## Battle-Tested Utilities

The skill includes production-ready utilities for comprehensive sleep and biometric analysis:

### Annotations API

Track user-logged events and correlate with biometric data:

```python
from fulcra_annotations import fetch_annotations

data = fetch_annotations(days=7)
# Returns structured data:
# - Coffee timing and late consumption warnings
# - Morning pills, evening medications adherence
# - Elemind neurostim headband usage
# - Subjective mood and sleep quality ratings
# - Dream intensity, wake-up counts, nocturia
# - Supplement dosages and timing
```

**Annotation Types:**
- **Moment**: Coffee, pills, Elemind, semaglutide (timestamp events)
- **Scale**: Mood, sleep quality, dream intensity (1-5 ratings)
- **Numeric**: Wake-up count, nocturia frequency, supplement mg
- **Boolean**: Yes/no events (future-proofed)
- **Duration**: Timed activities (future-proofed)

**Key Correlations:**
- Late coffee (after 2 PM) impacts deep sleep percentage
- Elemind usage correlates with improved deep sleep metrics
- Evening medication timing affects sleep onset
- Subjective vs. objective sleep quality mismatches reveal insights

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

### Sleep Briefing Pipeline

Generate comprehensive sleep analysis with cross-referenced data streams:

```python
from fulcra_sleep_briefing import run

result = run()  # Generates JSON + plain text briefing
# Cross-references: sleep stages, HRV, RHR, calendar load,
# exercise timing, coffee/medication logs, subjective ratings
```

**Data Integration:**
- Sleep metrics (stages, efficiency, fragmentation)
- Heart rate variability (HRV) and resting heart rate (RHR) trends
- Overnight heart rate curve (min/max/avg)
- Calendar meeting load (distinguishes real meetings from time blocks)
- Exercise/walk detection from step count and walking speed
- Location data for sleep context
- Coffee timing, Elemind usage, evening medication adherence
- Subjective sleep quality vs. objective metrics

**LLM Integration:** Uses configurable LLM endpoint (OpenClaw gateway by default) to generate human-readable analysis. Sanitized for public use — no personal references.

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
# Data output directory (default: ~/.openclaw/data/fulcra-analysis)
export FULCRA_OUTPUT_DIR=/custom/path

# LLM endpoint for briefing generation (default: OpenClaw gateway)
export LLM_ENDPOINT=http://localhost:8080/v1/chat/completions
export LLM_MODEL=gpt-4
export LLM_API_TOKEN=your_token

# Context directory for biometric theories/baselines
export CONTEXT_DIR=~/.openclaw/memory/topics

# User timezone override (default: from Fulcra API)
export OPENCLAW_TIMEZONE=America/New_York
```

## Deployment Patterns

### Cron Automation

```bash
# Refresh Fulcra token every 12 hours
0 */12 * * * python3 scripts/fulcra_auth.py refresh

# Generate sleep briefing every 2 hours (pre-computed)
0 */2 * * * python3 scripts/fulcra_sleep_briefing.py

# Data staleness check every 4 hours
0 */4 * * * python3 scripts/fulcra_data_watchdog.py || echo "STALE DATA ALERT"
```

### Integration with AI Agents

```python
# Instant sleep response (pre-computed)
with open('data/fulcra-analysis/sleep-briefing.txt') as f:
    briefing = f.read()
    # Already formatted, just send to user

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
