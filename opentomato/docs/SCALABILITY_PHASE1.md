# 可扩展性改造（Phase 1）

本次改造聚焦业务吞吐与多租户正确性，目标是把系统从“同步原型”提升到“可扩展服务骨架”。

## 已完成

1. 多租户上下文打通（去除核心硬编码）
- `user_id` 已贯穿 `LLM -> Agent -> Tool -> Scheduler`。
- 关键变更：
  - `app/core/agent_tools.py`
  - `app/core/agents/control.py`
  - `app/core/agents/analyst.py`
  - `app/core/scheduler_service.py`

2. 异步对话任务通道
- 新增后台任务服务：`app/core/chat_task_service.py`
- 新增接口：
  - `POST /api/v1/chat/async`：提交任务
  - `GET /api/v1/chat/tasks/{task_id}`：轮询状态与结果
- 若存在 Redis，任务队列和任务状态会落到 Redis，共享于多实例查询。
- 保留 `POST /api/v1/chat` 同步接口用于兼容。

3. 缓存层（Redis 可选 + 本地降级）
- 新增缓存服务：`app/core/cache_service.py`
- 若配置 `REDIS_URL` 或 `REDIS_HOST` 且安装 `redis`，自动使用 Redis。
- 否则回退到进程内 TTL 缓存。
- `/api/v1/status` 与 `get_system_status` 已接入缓存，降低热点查询压力。

4. 调度持久化
- 调度支持持久化 JobStore（`SCHEDULER_JOBSTORE_URL`）。
- 未显式配置时，会优先按 `MYSQL_*` 自动推导 MySQL JobStore。
- 配合 Redis 领导者选举，确保多实例仅一个调度执行者。
- 任务重启后可恢复（相较原 `MemoryJobStore`）。

## 新增环境变量

- `REDIS_URL`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_USERNAME`
- `REDIS_PASSWORD`
- `REDIS_DB`
- `REDIS_USE_SSL`
- `CACHE_PREFIX`
- `CACHE_DEFAULT_TTL_SECONDS`
- `STATUS_CACHE_TTL_SECONDS`
- `CHAT_TASK_WORKERS`
- `CHAT_TASK_QUEUE_SIZE`
- `CHAT_TASK_TTL_SECONDS`
- `CHAT_TASK_REDIS_NAMESPACE`
- `SCHEDULER_JOBSTORE_URL`
- `SCHEDULER_JOBSTORE_DB`
- `SCHEDULER_TIMEZONE`
- `SCHEDULER_MAX_WORKERS`
- `SCHEDULER_COALESCE`
- `SCHEDULER_JOB_MAX_INSTANCES`
- `SCHEDULER_MISFIRE_GRACE_SECONDS`
- `SCHEDULER_LEADER_LOCK_KEY`
- `SCHEDULER_LEADER_LOCK_TTL_SECONDS`
- `SCHEDULER_LEADER_RENEW_INTERVAL_SECONDS`
- `SCHEDULER_LEADER_CHECK_INTERVAL_SECONDS`

## 下一步建议（Phase 2）

1. 将 Redis List 升级为 Redis Streams / RabbitMQ（增强失败重试与投递确认）。
2. 引入 worker 独立部署（API 与推理解耦到不同 deployment）。
3. 增加任务幂等键与重复请求合并。
4. 增加限流和背压策略（按租户/接口）。
