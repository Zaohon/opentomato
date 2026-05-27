# AI Control Safety Guardrails (Action Audit Layer)
# Designed to enforce Fail-Closed deterministic behavior before MQTT dispatch

## 1. Overview and Philosophy
The Energy Management System (HEMS) bridges non-deterministic LLM agents with physical hardware. Therefore, **all control decisions MUST pass through a deterministic "fail-closed" SafetyGuard interception layer**.
Goal: Prevent "AI Hallucinations" from causing battery damage, grid overloading, equipment wear, or backend schema exceptions.

## 2. Interception Context (`AgentTools.set_energy_strategy`)
- **Pre-Flight Check**: Extract current physical sensor data strictly using `AgentTools.get_system_status_strict()`.
- **Validation Execution**: Execute `SafetyGuard.validate_strategy(ai_params, physical_telemetry)`.
- **Environment-Aware Strategy**:
  - **Mock/Dev**: `Unsafe` -> Allow execution but **log warning** and return diagnostic reason.
  - **Prod/Hardware**: `Unsafe` -> Block transmission immediately, and return diagnostic reason.

## 3. The Comprehensive Security Architecture (3 Dimensions)

### A. Parameter Boundary & Ontology Locks (Anti-Hallucination)
Validate the AI's math and data structures before evaluating the physical state.
1. **Target SOC Limit**: `target_soc` MUST be numeric, integer, and adhere to `0 <= target_soc <= 100`. (Optionally tighten lower bound to 20% for forced grid charging).
2. **Time Window Geometry**: `start_time` and `end_time` MUST be proper `HH:MM` formats **only if provided**. The window sequence must be logically forward-moving and not overlapping with other commanded windows.



### B. Telemetry Freshness & Connectivity Lock (Data Integrity)
Never blind-fly a system based on stale telemetry caching.
1. **Timestamp Decay Check**: `latest_telemetry` timestamp MUST NOT cross a **10-minute (600s)** staleness threshold against the current UTC clock.
2. **Device Baseline Status**: Device `status` MUST be `online`. If `warning`, `fault`, or `offline`, uniformly reject all commands EXCEPT an emergency regression to `Backup Only`.

### C. Physical Asset Protection (Battery Health)
Ensure the AI does not push the lithium cells beyond acceptable bounds.
1. **Deep Discharge Block**: If local physical `SOC < 10%`, strictly forbid any mode intended for grid export or aggressive self-consumption (`Solar Export`, `Self-Powered`).
2. **Over-Charge / Saturation Block**: If physical `SOC >= 98%`, reject any command focused on forced grid purchasing/charging (`Time-Based Control` targeting high SOC).



## 4. Expected Output Flow
If any of the above checks trip, the function returns a rigid format:
`Tuple(False, "Safety Hazard: Battery SoC is 8%. Cannot execute Self-Powered discharge.")`
- Immediate block on MQTT invocation.
- The string serves as RL/Prompt feedback for the Agent to rethink its plan.

## 5. Mock vs Prod Behavior
- **Mock/Dev**: SafetyGuard returns warnings for telemetry freshness/status rules; execution continues for validation and UI flows.
- **Prod/Hardware**: SafetyGuard enforces hard blocks on telemetry freshness/status rules.
