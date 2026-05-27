# PV / Load Forecast Design (HEMS Agent)

## Scope
- Periodically run PV and load forecasts.
- Store forecast points in InfluxDB.
- Store forecast run metadata (audit/trace) in MySQL.
- Provide a `get_pv_forecast` tool integrated into AnalystAgent.
- Add a minimal SafetyGuard patch (execution-layer guard) to prevent bypass.

## Storage Decision
- **InfluxDB**: Store time-series forecast points (PV and load).
- **MySQL**: Store forecast run metadata only (audit/trace). This is lightweight and enables
  debugging, status tracking, and model version traceability without scanning InfluxDB.

## Implementation Order (Agreed)
1. Forecast scheduler + forecast service + InfluxDB write for forecast points.
2. Analyst tool `get_pv_forecast` integration.
3. Minimal SafetyGuard patch in `AgentTools.set_energy_strategy` to prevent bypass.
4. Full SafetyGuard rule expansion later.

## Decisions (Aligned with FLS Backend)
1. Measurement name: `energy_forecast` (time-series naming consistent with `energy_flow` and Influx usage).
2. Tags/fields:\n
   - Tags: `device_sn`, `user_id`, `forecast_type`, `model_version`, `horizon_hours`, `interval_minutes`, `run_id`\n
   - Fields: `pv_power`, `load_power` (aligned with `EnergyFields.FIELD_PV_POWER` and `FIELD_LOAD_POWER`).
3. Timestamps: store forecast points in **UTC** in InfluxDB. Use MySQL `timezone` field to preserve\n
   the user/station timezone context for traceability.\n
4. Minimal SafetyGuard patch uses `get_system_status_strict` and fails closed on any error.

## InfluxDB Forecast Points
- Measurement: `energy_forecast` (or `energy_prediction` if preferred)
- Tags:
  - `device_sn`
  - `user_id`
  - `forecast_type` (`pv` | `load` | `both`)
  - `model_version`
  - `horizon_hours`
  - `interval_minutes`
  - `run_id`
- Fields:
  - `pv_power` (W)
  - `load_power` (W)
  - Optional: `p50`, `p90` for uncertainty
- Timestamp: forecasted time for each point stored in UTC (ISO-8601 / epoch)

## MySQL Forecast Run Metadata (Minimum Audit)
Table name: `hems_forecast_runs`

```sql
CREATE TABLE IF NOT EXISTS hems_forecast_runs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  device_sn VARCHAR(64) DEFAULT NULL,

  forecast_type VARCHAR(16) NOT NULL,        -- pv | load | both
  horizon_hours INT NOT NULL,
  interval_minutes INT NOT NULL,
  history_days INT DEFAULT NULL,

  model_version VARCHAR(64) NOT NULL,
  trigger_source VARCHAR(32) NOT NULL,       -- scheduler | manual | api
  status VARCHAR(16) NOT NULL,               -- queued | running | succeeded | failed

  influx_bucket VARCHAR(64) DEFAULT NULL,
  influx_measurement VARCHAR(64) DEFAULT NULL,
  influx_tags JSON DEFAULT NULL,
  point_count INT DEFAULT 0,

  timezone VARCHAR(64) DEFAULT NULL,
  started_at DATETIME DEFAULT NULL,
  completed_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  error_message TEXT,
  metrics_json JSON DEFAULT NULL,

  UNIQUE KEY uk_forecast_run_id (run_id),
  KEY idx_forecast_user_time (user_id, device_sn, created_at),
  KEY idx_forecast_status_time (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Scheduler Design
- Use existing APScheduler service.
- Job frequency: every 60 minutes (configurable).
- Each run creates a `run_id` and writes:
  - `queued` -> `running` -> `succeeded` or `failed` in MySQL.
  - forecast points in InfluxDB.

Suggested env vars:
- `FORECAST_JOB_FREQUENCY_MINUTES=60`
- `FORECAST_HORIZON_HOURS=24`
- `FORECAST_INTERVAL_MINUTES=60`
- `FORECAST_HISTORY_DAYS=7`

## Forecast Service (MVP)
- Inputs:
  - user profile (PV capacity, timezone)
  - historical PV/load from InfluxDB
  - weather (existing MarketService or external API)
- Outputs:
  - time-series points for next horizon
- MVP methods:
  - PV: median of last N days per time bucket, scaled by weather factor
  - Load: median of last N days per time bucket, optional weekday/weekend factor

## Agent Tools Integration
- Add `get_pv_forecast` tool in `AgentTools`.
- Return latest forecast from InfluxDB; if missing or stale, generate and persist.
- Update AnalystAgent tool list and system prompt.

## Safety Guard (Minimal Patch Now)
- Enforce guardrails inside `AgentTools.set_energy_strategy` to prevent bypass
  from scheduler or external calls.
- Use existing `SafetyGuard.validate_strategy` with strict telemetry read
  (`get_system_status_strict`) and fail-closed on errors.

## Safety Guard (Enhanced Design)
Goal: make control actions deterministic, auditable, and safe even if the LLM output
is malformed or overly aggressive.

### Layered Enforcement (defense-in-depth)
1. **Intent Layer (LLM/Agent):** only produces a structured intent (mode + optional params).
2. **Policy Layer (SafetyGuard):** deterministic rule checks, no external calls.
3. **Execution Layer (AgentTools):** final gate; only executes if SafetyGuard passes.
4. **Device Layer (MQTT/API):** physical control; must never be reached without a guard pass.

### Core Rules (Deterministic)
- Telemetry freshness: block if last telemetry timestamp older than `N` minutes.
- Device status: allow **only UPS** when `OFFLINE/FAULT`.
- Grid availability: block grid-dependent modes if grid unavailable.
- SOC bounds: reject if target SOC < 10% or > 95% (configurable).
- EV dependency: FAST mode requires EV connected.
- Cooling-off: reject mode switches within `M` minutes (debounce).

### Audit & Traceability
- Every control attempt writes a decision log entry with:
  - `user_id`, `device_sn`, `requested_mode`, `decision=allow|deny`
  - `reason`, `telemetry_snapshot`, `timestamp`, `trace_id`
- Failed actions surface a user-facing explanation and keep a server-side trace.

### Config & Overrides
- Configurable thresholds via env:
  - `SAFETY_TELEMETRY_STALE_MINUTES`
  - `SAFETY_SOC_MIN`, `SAFETY_SOC_MAX`
  - `SAFETY_MODE_DEBOUNCE_MINUTES`
- Admin override (optional): requires explicit `override_token` and logs override reason.

### Minimal MVP Implementation (recommended next)
- Add telemetry freshness + SOC range + OFFLINE/FAULT block rules.
- Add structured audit log (stdout or DB table).
- Keep LLM response deterministic by surfacing guard decision summary.

### Future Enhancements
- Device-specific policies (per model, per site).
- Rate-limit control actions per user/device.
- Integrate with alerting (Slack/Email) on repeated unsafe attempts.

## Execution Plan (Step-by-Step)
1. Forecast Chain (Scheduler + Service + Influx write)
   - Add ForecastService (MVP: historical median + weather factor)
   - Add scheduler job to generate and write `energy_forecast`
   - Write run metadata to MySQL
2. Analyst Tool Integration
   - Add `get_pv_forecast` to `AgentTools`
   - Update AnalystAgent tools and prompt
3. Minimal Safety Patch
   - Add guardrail check inside `AgentTools.set_energy_strategy`

## Verification & Self-Test (Per Step)
1. Forecast Chain
   - Trigger one forecast run (manual or scheduled)
   - Query InfluxDB for latest `energy_forecast` points
   - Verify tags/fields: `device_sn`, `user_id`, `pv_power`, `load_power`
   - Verify timestamps are UTC
2. Analyst Tool
   - Call `get_pv_forecast` directly, validate JSON shape and point count
   - Ask AnalystAgent for PV forecast, ensure tool is invoked and response is sensible
3. Minimal Safety Patch
   - Force `get_system_status_strict` to fail and confirm action is blocked
   - Confirm normal execution still succeeds when telemetry is valid
