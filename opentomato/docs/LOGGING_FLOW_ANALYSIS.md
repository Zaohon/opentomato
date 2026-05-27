# 日志系统流追踪分析

## 请求链路日志流

当用户发送一条消息时，框架会生成以下 **INFO** 级别的日志（按时间顺序）：

### 📊 完整链路示例

假设用户消息: `"告诉我今天的电价"`，user_id: `"user123"`

```
时间顺序 | 日志来源 | 日志内容示例
-------|--------|--------
1️⃣ API请求 | `app/core/runtime/coordinator.py` | [Runtime] request timing METRIC
2️⃣ 上下文加载 | `app/core/runtime/coordinator.py` | [Runtime] context_loaded request_id=abc123...
3️⃣ Agent入口 | `app/core/runtime/orchestrator.py` | agent_entry step=1 agent=router user_id=user123 query=告诉我今天的电价
4️⃣ 工具准备 | `app/core/agent/base.py` | tool_prepare agent=analyst tool=get_price round=1 user_id=user123 args={"date":"today"}
5️⃣ 工具调用 | `app/core/agent/base.py` | tool.call timing METRIC (agent=analyst tool=get_price)
6️⃣ 工具执行 | `app/core/runtime/pipeline.py` | 在 RuntimeToolObserver 中追踪
7️⃣ 响应准备 | `app/core/runtime/hooks/observability.py` | [Runtime] response_ready request_id=abc123 user=user123 agent=analyst path=route:analyst tool_events=1
8️⃣ 动作日志 | `app/core/runtime/coordinator.py` | [Runtime] action_executed {...}
9️⃣ 最终响应 | `app/core/runtime/coordinator.py` | [Runtime] chat_response user=user123 path=route:analyst length=86 content=今天电价是...
```

---

## 详细日志点分析

### 第1层: API 层 (`app/core/runtime/coordinator.py`)

#### 📍 `run()` 方法 - 请求开始
```python
# 使用 log_timing 记录整个请求耗时
with log_timing(
    logger,
    "runtime.request",
    request_id=request_id,          # 唯一请求ID
    user_id=safe_user_id,
    session_id=resolved_session_id,
):
    # 内部处理...
```
**输出**: `runtime.request timing=123ms request_id=abc123 user_id=user123 session_id=chat_xyz`

#### 📍 `LOAD_CONTEXT` 阶段之后
```python
self.pipeline.run_phase(RuntimePhase.LOAD_CONTEXT, state)

logger.info(
    f"[Runtime] context_loaded request_id={state.request_id} user={state.user_id} "
    f"session={state.session_id} history_msgs={state.metrics['history_msgs']} "
    f"history_chars={state.metrics['history_chars']} "
    f"memory_summary={'loaded' if state.memory_summary_md else 'empty'}"
)
```
**输出**: `[Runtime] context_loaded request_id=abc123 user=user123 session=chat_xyz history_msgs=5 history_chars=256 memory_summary=loaded`

**关键信息**:
- `history_msgs`: 加载的历史消息数
- `history_chars`: 历史消息总字符数
- `memory_summary`: 是否加载到长期记忆

---

### 第2层: 路由层 (`app/core/runtime/orchestrator.py`)

#### 📍 Agent 入口日志
```python
if hop == 0:
    logger.info(
        "agent_entry step=%s agent=%s user_id=%s query=%s",
        hop + 1,
        current_agent_name,          # 通常是 "router"
        ctx.user_id,
        user_input,
    )
```
**输出**: `agent_entry step=1 agent=router user_id=user123 query=告诉我今天的电价`

**关键信息**:
- `step`: 当前步数（1表示首次进入）
- `agent`: 当前处理的智能体

#### 📍 Agent 递进日志（如果发生handoff）
```python
else:
    logger.info(
        "agent_step step=%s agent=%s user_id=%s query=%s",
        hop + 1,
        current_agent_name,          # 例如 "analyst"
        ctx.user_id,
        user_input,
    )

# 同时记录handoff本身
logger.info(
    "agent_handoff from_agent=%s to_agent=%s step=%s user_id=%s reason=%s",
    current_agent_name,
    next_agent_name,
    hop + 1,
    ctx.user_id,
    reason or "",
)
```
**输出**: 
- `agent_step step=2 agent=analyst user_id=user123 query=告诉我今天的电价`
- `agent_handoff from_agent=router to_agent=analyst step=1 user_id=user123 reason=price_query`

---

### 第3层: 工具执行层 (`app/core/agent/base.py`)

#### 📍 工具准备日志
```python
logger.info(
    "tool_prepare agent=%s tool=%s round=%s user_id=%s reason=%s args=%s",
    self.name,                       # agent名称
    func_name,                       # 工具名称，如 "get_price"
    _round + 1,                      # 当前轮次
    ctx.user_id,
    reason,                          # 调用理由
    json.dumps(args, ensure_ascii=False, sort_keys=True),  # 工具参数
)
```
**输出**: `tool_prepare agent=analyst tool=get_price round=1 user_id=user123 reason=获取电价信息 args={"date":"today","city":"all"}`

#### 📍 工具调用耗时
```python
with log_timing(
    logger,
    "tool.call",
    agent=self.name,
    tool=func_name,
    round_index=_round + 1,
    user_id=ctx.user_id,
):
    result_content, tool_action = self._handle_tool_call(func_name, args, ctx)
```
**输出**: `tool.call timing=234ms agent=analyst tool=get_price round_index=1 user_id=user123`

---

### 第4层: 可观测性钩子 (`app/core/runtime/hooks/observability.py`)

#### 📍 响应准备日志
在 `POST_AGENT` 阶段（即将返回响应前）
```python
if phase == RuntimePhase.BEFORE_RESPONSE:
    logger.info(
        f"[Runtime] response_ready request_id={state.request_id} user={state.user_id} "
        f"agent={state.current_agent or 'unknown'} path={state.route_path or 'route:unknown'} "
        f"tool_events={len(state.tool_events)}"
    )
```
**输出**: `[Runtime] response_ready request_id=abc123 user=user123 agent=analyst path=route:analyst tool_events=1`

**关键信息**:
- `path`: 请求路由路径（如 `route:analyst`, `guard:no_api_key`）
- `tool_events`: 本次请求调用的工具数

---

### 第5层: 动作日志 (`app/core/runtime/coordinator.py`)

#### 📍 执行动作记录
```python
if action_log:
    logger.info(f"[Runtime] action_executed {action_log}")
```
**输出**: `[Runtime] action_executed {'tool': 'get_price', 'args': {...}, 'result': {...}}`

---

### 第6层: 最终响应 (`app/core/runtime/coordinator.py`)

#### 📍 `_log_chat_response()` 方法
```python
@staticmethod
def _log_chat_response(user_id: str, response: str, path: str) -> None:
    content = response if isinstance(response, str) else str(response)
    logger.info(
        f"[Runtime] chat_response user={user_id} path={path} "
        f"length={len(content)} content={content}"
    )
```
**输出**: `[Runtime] chat_response user=user123 path=route:analyst length=86 content=今天电价是：晴天0.8元/度，可以计划10点后的充电`

---

## 内存和会话钩子日志

### 会话加载 (`app/core/runtime/hooks/session.py`)

在 `LOAD_CONTEXT` 阶段：
- 记录会话快照加载信息
- `state.metrics["session_recent_turns"]`: 会话中的回合数
- `state.flags["session_summary_loaded"]`: 是否加载了会话摘要

### 内存回忆 (`app/core/runtime/hooks/memory.py`)

在 `PRE_AGENT` 阶段：
- 调用 `MemoryPlugin` 进行内存回忆
- 注入 RAG 上下文
- 记录使用的上下文URI

### 内存保存 (`app/core/memory/service.py`, `app/core/memory/provider.py`)

贯穿整个请求生命周期：
- `[Memory] Storing long-term memory user=user123`
- `[Memory] Loading memory summary from OpenViking user=user123`
- `[Memory] Loaded memory summary user=user123 source=cache`
- `[OpenViking] recall_user_memories start user=user123 limit=10`

---

## 日志级别分布

| 日志级别 | 用途 | 示例 |
|--------|------|------|
| **INFO** | 正常流程跟踪 | agent_entry, tool_prepare, response_ready |
| **TIMING** | 性能指标 | runtime.request (123ms), tool.call (234ms) |
| **WARNING** | 非正常但允许的情况 | agent_handoff_blocked, max_handoffs |
| **ERROR** | 错误情况 | llm_call_failed, invalid_user_id |
| **EXCEPTION** | 异常情况 | try-except 捕获的异常 |

---

## 当前日志系统的问题

### 🔴 问题1: 日志格式不一致
```python
# 存在多种格式混用:
logger.info("agent_entry step=%s agent=%s ...", step, agent)           # %-style
logger.info(f"[Runtime] context_loaded request_id={req_id} ...")       # f-string
logger.info("[ToolsRegistry] loaded count=%s", count)                  # 混合
```

### 🔴 问题2: 上下文信息缺失
某些关键日志缺少：
- `request_id`: 不是所有日志都包含用于关联的请求ID
- 缺少 `soul`（人格）信息
- 缺少 `response_mode` 等execution参数

### 🔴 问题3: 日志冗余
- 多个地方重复记录相同信息（如user_id）
- 工具参数JSON可能很长，污染日志

### 🔴 问题4: 可观测性不足
缺少：
- 内存命中/未命中率
- Agent处理耗时分解（LLM vs 工具调用）
- Token使用统计
- 错误率追踪

---

## 建议的日志系统优化

### 方案1: 统一日志格式
```python
# 所有日志使用结构化格式
logger.info(
    "event",
    extra={
        "request_id": request_id,
        "user_id": user_id,
        "event_type": "agent_entry",
        "agent": agent_name,
        "step": 1,
    }
)
```

### 方案2: 创建日志上下文管理器
```python
class LogContext:
    def __init__(self, request_id, user_id, session_id):
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
    
    def info(self, event, **kwargs):
        logger.info(event, extra={
            "request_id": self.request_id,
            "user_id": self.user_id,
            **kwargs
        })
```

### 方案3: 使用structured logging库
考虑使用 `structlog` 或 `python-json-logger` 以支持JSON格式输出

### 方案4: 日志聚合配置
- 创建 JSON日志输出（便于ELK/Datadog分析）
- 保留文本日志（便于开发调试）
- 分级收集（INFO vs DEBUG）

---

## 日志采集检查清单

部署前应检查：
- [ ] 所有请求都有唯一的 request_id
- [ ] 关键时间点都有耗时记录
- [ ] 错误路径都有适当的日志
- [ ] 敏感信息（密钥、token）不被记录
- [ ] 日志大小不会无限增长
- [ ] 异常情况都能被追踪

---

## 日志查询示例

### 追踪单个请求
```bash
grep "request_id=abc123" logs/*.log
```

### 找出慢请求
```bash
grep "runtime.request timing" logs/*.log | awk -F'timing=' '{print $2}' | sort -rn | head -10
```

### 统计Agent使用频率
```bash
grep "agent_entry" logs/*.log | awk '{print $NF}' | sort | uniq -c
```

### 工具调用分析
```bash
grep "tool_prepare" logs/*.log | awk -F'tool=' '{print $2}' | awk '{print $1}' | sort | uniq -c
```

---

## 性能优化方向

基于当前日志，建议关注：

1. **高耗时的工具** - 通过 `tool.call timing` 识别
2. **频繁的handoff** - 说明路由器准确性低
3. **短请求** - 可能是缓存命中或快速拒绝
4. **内存加载延迟** - `context_loaded` 时的memory_summary字段

