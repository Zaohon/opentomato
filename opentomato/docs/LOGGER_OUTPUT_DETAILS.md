# 完整的日志流信息列表

当用户发送一条消息时，按时间顺序会产生以下日志：

---

## 📋 完整日志清单（按执行顺序）

### 0️⃣ API 请求接收（INFO级别）
**来源**: `app/core/api/chat.py` → `chat_endpoint()` line 71
```
[API] chat_request user={user_id} soul={soul_name} message_length={content_length} message={message_text}
```
**示例**:
```
[API] chat_request user=user123 soul=professional message_length=18 message=告诉我今天的电价
```
**参数说明**:
- `user`: 请求的用户ID
- `soul`: 选择的人格模式（default/friendly/concise/professional）
- `message_length`: 用户消息的字符数
- `message`: 用户发送的原始消息内容

**何时出现**: 每个chat API请求都会立即产生（最早的日志）

---

### 1️⃣ 请求开始计时（DEBUG级别）
**来源**: `app/core/runtime/coordinator.py` → `log_timing()`
```
[耗时] 名称=runtime.request 状态=成功 毫秒={duration_ms} request_id={request_id} user_id={user_id} session_id={session_id}
```
**示例**:
```
[耗时] 名称=runtime.request 状态=成功 毫秒=542 request_id=abc123xyz user_id=user123 session_id=chat_456def
```
**何时出现**: 当 log_timing 启用时（即 `get_log_timing_enabled()` 返回 true）

---

### 2️⃣ 上下文加载完成（INFO级别）
**来源**: `app/core/runtime/coordinator.py` → `coordinator.run()` line 122
```
[Runtime] context_loaded request_id={request_id} user={user_id} session={session_id} history_msgs={history_count} history_chars={total_chars} memory_summary=loaded
```
**示例**:
```
[Runtime] context_loaded request_id=abc123xyz user=user123 session=chat_456def history_msgs=5 history_chars=823 memory_summary=loaded
```
**参数说明**:
- `history_msgs`: 从数据库加载的历史消息数量
- `history_chars`: 历史消息的总字符数
- `memory_summary`: 是否成功加载了长期记忆摘要（loaded/empty）

---

### 3️⃣ Agent 入口日志（INFO级别，首次）
**来源**: `app/core/runtime/orchestrator.py` → `dispatch()` line 58
```
agent_entry step=1 agent={agent_name} user_id={user_id} query={user_input}
```
**示例**:
```
agent_entry step=1 agent=router user_id=user123 query=告诉我今天的电价
```
**参数说明**:
- `step=1`: 表示这是第一个Agent（路由器）
- `agent`: 当前处理的Agent名称（通常是 router）
- `user_id`: 用户ID
- `query`: 用户原始输入（可能很长）

**注意**: 如果没有发生 handoff，只会产生一条 agent_entry 日志

---

### 4️⃣ Agent 递进日志（INFO级别，如果有handoff）
**来源**: `app/core/runtime/orchestrator.py` → `dispatch()` line 66
```
agent_step step={step_number} agent={agent_name} user_id={user_id} query={user_input}
```
**示例** (假设 router handoff 到 analyst):
```
agent_step step=2 agent=analyst user_id=user123 query=告诉我今天的电价
```
**参数说明**:
- `step=2`: 第二个Agent处理
- `agent`: handoff 后的目标Agent（如 analyst, support 等）

**何时出现**: 只有当前一个Agent决定handoff时才会出现

---

### 5️⃣ Agent Handoff 日志（INFO级别，如果有handoff）
**来源**: `app/core/runtime/orchestrator.py` → `dispatch()` line 89
```
agent_handoff from_agent={source_agent} to_agent={target_agent} step={step} user_id={user_id} reason={reason}
```
**示例**:
```
agent_handoff from_agent=router to_agent=analyst step=1 user_id=user123 reason=price_query
```
**参数说明**:
- `from_agent`: 发起handoff的Agent
- `to_agent`: 接收handoff的目标Agent
- `step`: 当前步数
- `reason`: handoff的理由/原因（可能是空字符串）

**何时出现**: 仅当发生Agent间的handoff时

---

### 6️⃣ 工具准备日志（INFO级别，如果调用了工具）
**来源**: `app/core/agent/base.py` → `run_agentic_loop()` line 148
```
tool_prepare agent={agent_name} tool={tool_name} round={round_number} user_id={user_id} reason={reason} args={json_args}
```
**示例**:
```
tool_prepare agent=analyst tool=get_price round=1 user_id=user123 reason=获取当前电价信息 args={"date":"2026-03-23","city":"all"}
```
**参数说明**:
- `agent`: 调用工具的Agent名称
- `tool`: 工具函数名称（对应 app/tools/ 下的模块）
- `round`: 当前是第几轮工具调用（可能一个Agent会多轮调用）
- `reason`: LLM生成的调用理由
- `args`: 工具的参数（JSON格式，已排序）

**何时出现**: 对应每一次LLM决定调用工具时

**重要**: 如果工具参数很长，这条日志会很冗长

---

### 7️⃣ 工具调用计时（DEBUG级别）
**来源**: `app/core/agent/base.py` → `log_timing()` line 167
```
[耗时] 名称=tool.call 状态=成功 毫秒={duration_ms} agent={agent_name} tool={tool_name} round_index={round} user_id={user_id}
```
**示例**:
```
[耗时] 名称=tool.call 状态=成功 毫秒=234 agent=analyst tool=get_price round_index=1 user_id=user123
```
**参数说明**:
- `毫秒`: 工具执行耗时（毫秒）
- `状态`: 成功或失败（如果异常发生则为失败）

**何时出现**: 每次工具调用后，仅当 log_timing 启用时

---

### 8️⃣ 响应准备日志（INFO级别）
**来源**: `app/core/runtime/hooks/observability.py` → `ObservabilityHook.run()` line 40
```
[Runtime] response_ready request_id={request_id} user={user_id} agent={agent_name} path={route_path} tool_events={tool_count}
```
**示例**:
```
[Runtime] response_ready request_id=abc123xyz user=user123 agent=analyst path=route:analyst tool_events=1
```
**参数说明**:
- `request_id`: 本次请求的唯一ID
- `user`: 用户ID
- `agent`: 最终返回响应的Agent
- `path`: 请求的路由路径（如 route:analyst, route:support, guard:no_api_key 等）
- `tool_events`: 本次请求中调用的工具数量

**路径常见值**:
- `route:router` - 由路由器处理
- `route:analyst` - 由分析器处理
- `route:support` - 由支持Agent处理
- `guard:no_api_key` - 因无API密钥被拒绝
- `guard:missing_user_id` - 因缺少user_id被拒绝
- `guard:invalid_user_id` - 因user_id格式无效被拒绝
- `guard:unknown_agent` - 因未知Agent被拒绝

---

### 9️⃣ 执行动作日志（INFO级别，如果有action_log）
**来源**: `app/core/runtime/coordinator.py` → `chat()` line 201
```
[Runtime] action_executed {action_log_dict}
```
**示例**:
```
[Runtime] action_executed {'get_price': {'status': 'success', 'data': {...}}}
```
**参数说明**:
- `action_log`: 包含所有工具执行结果的字典

**何时出现**: 仅当实际调用了工具时

---

### 🔟 最终响应日志（INFO级别）
**来源**: `app/core/runtime/coordinator.py` → `_log_chat_response()` line 60
```
[Runtime] chat_response user={user_id} path={route_path} length={response_length} content={response_text}
```
**示例**:
```
[Runtime] chat_response user=user123 path=route:analyst length=128 content=根据实时数据，今天的电价：晴天0.8元/度，阴天0.95元/度，建议10点后充电
```
**参数说明**:
- `user`: 用户ID
- `path`: 请求的路由路径
- `length`: 响应文本的字符数
- `content`: 完整的响应文本内容

**重要**: 这条日志包含了LLM的完整回复，可能很长

---

### 1️⃣1️⃣ 请求结束计时（DEBUG级别）
**来源**: `app/core/runtime/coordinator.py` → `log_timing()` 退出
```
[耗时] 名称=runtime.request 状态=成功 毫秒={total_duration_ms} request_id={request_id} user_id={user_id} session_id={session_id}
```
**示例**:
```
[耗时] 名称=runtime.request 状态=成功 毫秒=542 request_id=abc123xyz user_id=user123 session_id=chat_456def
```

**总耗时包括**:
- LLM调用耗时
- 工具执行耗时
- 内存加载耗时
- 日志等开销

---

## 📊 日志汇总统计表

| # | 日志类型 | 日志级别 | 来源模块 | 何时出现 | 示例数据量 |
|----|---------|--------|--------|--------|---------|
| 1 | runtime.request (开始计时) | DEBUG | coordinator | 总是 | 小 |
| 2 | context_loaded | INFO | coordinator | 总是 | 小 |
| 3 | agent_entry | INFO | orchestrator | 总是（第一个Agent） | 中 |
| 4 | agent_step | INFO | orchestrator | 有handoff时 | 中 |
| 5 | agent_handoff | INFO | orchestrator | 有handoff时 | 小 |
| 6 | tool_prepare | INFO | base.py | 调用工具时 | **大** |
| 7 | tool.call (计时) | DEBUG | base.py | 调用工具时 | 小 |
| 8 | response_ready | INFO | observability | 总是 | 小 |
| 9 | action_executed | INFO | coordinator | 调用工具时 | 中 |
| 10 | chat_response | INFO | coordinator | 总是 | **大** |
| 11 | runtime.request (结束计时) | DEBUG | coordinator | 总是 | 小 |

---

## 🎯 按场景分类的日志

### 场景A: 简单查询（无工具调用，无handoff）
```
1. [耗时] 名称=runtime.request 状态=成功 毫秒=... request_id=... user_id=... session_id=...
2. [Runtime] context_loaded request_id=... user=... history_msgs=5 ...
3. agent_entry step=1 agent=router user_id=... query=...
4. [Runtime] response_ready request_id=... user=... agent=router path=route:router tool_events=0
5. [Runtime] chat_response user=... path=route:router length=... content=...
6. [耗时] 名称=runtime.request 状态=成功 毫秒=... request_id=... user_id=... session_id=...
```

### 场景B: 工具查询（有工具调用，可能有handoff）
```
1. [耗时] 名称=runtime.request 状态=成功 毫秒=... request_id=... 
2. [Runtime] context_loaded request_id=... 
3. agent_entry step=1 agent=router ...
4. agent_handoff from_agent=router to_agent=analyst ...
5. agent_step step=2 agent=analyst ...
6. tool_prepare agent=analyst tool=get_price round=1 ...
7. [耗时] 名称=tool.call 状态=成功 毫秒=... agent=analyst tool=get_price ...
8. [Runtime] response_ready request_id=... agent=analyst path=route:analyst tool_events=1
9. [Runtime] action_executed {...}
10. [Runtime] chat_response user=... path=route:analyst length=... content=...
11. [耗时] 名称=runtime.request 状态=成功 毫秒=...
```

### 场景C: 错误情况（无API密钥）
```
1. [耗时] 名称=runtime.request 状态=成功 毫秒=...
2. [Runtime] chat_response user=unknown path=guard:no_api_key length=42 content=[Error] No API Key provided. Cannot query LLM.
3. [耗时] 名称=runtime.request 状态=成功 毫秒=...
```

---

## ⚠️ 日志中的敏感信息注意

当前日志中包含的敏感或可能很长的数据：

| 字段 | 风险级别 | 说明 |
|-----|--------|------|
| user_id | 🟡 中 | 包含用户标识 |
| query | 🔴 高 | 包含用户问题（可能是隐私信息） |
| content (chat_response) | 🔴 高 | 包含LLM的完整回复 |
| args (tool_prepare) | 🟡 中 | 包含工具参数（可能含敏感数据） |
| request_id | 🟢 低 | 仅是追踪ID |

---

## 📈 日志量估计

对于一个简单的非工具调用请求：
- 日志数量: 4-6 条 INFO + 2 条 DEBUG
- 日志大小: 约 500-1500 字节

对于一个工具调用请求：
- 日志数量: 9-11 条 INFO + 4 条 DEBUG
- 日志大小: 约 2000-5000 字节（因为包含工具参数和结果）

对于高频用户（每分钟100个请求）：
- 日志生成速度: 约 100-500 KB/分钟
- 日志保留大小（7天）: 约 700MB - 3.5GB

