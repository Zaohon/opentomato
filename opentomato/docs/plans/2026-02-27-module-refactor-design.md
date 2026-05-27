# Module Refactor Design (Approved)

## Scope

Refactor four tracks in one migration, with direct path migration and no compatibility wrappers:

1. Split `openviking_provider.py` into internal modules.
2. Unify API dependency injection style to `Depends(...)` only.
3. Split API routes by domain.
4. Migrate overloaded `core/` responsibilities into `agent/`, `memory/`, and `services/`.

## Decisions

- Migration strategy: **direct import migration**, no fallback aliases.
- Runtime behavior: preserve existing API surface and endpoint paths.
- Safety: preserve existing service initialization and `app.state` lifecycle in `main.py`.

## Target Layout

- `app/agent/*`: LLM orchestration, agents, tool execution, guardrails.
- `app/memory/*`: cache + fast memory + long-memory orchestration.
- `app/services/*`: profile/persona config/scheduler/chat task domain services.
- `app/infrastructure/openviking/*`: client/session/content/provider layering.
- `app/api/{chat,memory,status,scheduler,router}.py`: route split by bounded context.

## API/DI Rules

- Route handlers must use dependency providers from `app/core/dependencies.py`.
- Route layer must not use `request.app.state` direct reads.
- Shared route helper logic is centralized in `app/api/common.py`.

## Risk Controls

- Preserve old service state field names in `main.py` to avoid lifecycle regressions.
- Compile check over `app` and `tests` after migration.
- Run representative unit tests for guardrails, memory, persona overlay, and control fail-closed logic.

## Verification Plan

- `python3 -m compileall app tests`
- `python3 -m unittest tests.test_guardrails tests.test_fast_memory_service tests.test_shared_persona_overlay tests.test_control_fail_closed`
