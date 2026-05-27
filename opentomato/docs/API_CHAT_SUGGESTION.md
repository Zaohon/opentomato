# API 说明文档（Chat + Suggestion）

本文档说明以下 3 个接口：
- `POST /api/v1/chat`
- `POST /api/v1/generate_suggestion`
- `POST /api/v1/handle_suggestion`

## 1. Chat 接口

### 1.1 基本信息
- 方法：`POST`
- 路径：`/api/v1/chat`
- 说明：发起一次非流式对话，返回最终文本回复和会话 ID。

### 1.2 请求体
```json
{
  "message": "今天用电建议是什么？",
  "user_id": "u_1001",
  "history": [
    {
      "role": "user",
      "content": "昨天的建议我看了"
    },
    {
      "role": "assistant",
      "content": "好的，我继续跟进。"
    }
  ],
  "soul": "default"
}
```

字段说明：
- `message` `string` 必填，用户本轮输入。
- `user_id` `string` 必填，用户标识（会进行规范化校验）。
- `history` `array` 选填，历史消息列表，元素结构：
  - `role` `string`，通常为 `user` 或 `assistant`
  - `content` `string`
- `soul` `string` 选填，人格名称；不传则使用默认人格。

### 1.3 响应体
```json
{
  "response": "建议你将高耗能设备错峰到晚间低价时段。",
  "session_id": "chat_9dbf5f8a8e7e4be1a8fd2d6d8f5d2f1c"
}
```

字段说明：
- `response` `string`，Agent 最终回复文本。
- `session_id` `string`，本次对话会话 ID。

### 1.4 示例 cURL
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message":"今天用电建议是什么？",
    "user_id":"u_1001",
    "soul":"default"
  }'
```

---

## 2. Generate Suggestion 接口（Mock）

### 2.1 基本信息
- 方法：`POST`
- 路径：`/api/v1/generate_suggestion`
- 说明：根据 `user_id` 返回一条示例建议，当前为 mock，不走真实业务链路。

### 2.2 请求体
```json
{
  "user_id": "u_1001"
}
```

字段说明：
- `user_id` `string` 必填，用户标识（会进行规范化校验）。

### 2.3 响应体
```json
{
  "user_id": "u_1001",
  "brief": "【示例建议】建议今晚 22:30 后开启储能优先模式，降低尖峰时段购电成本。",
  "detail": "【示例详情】这是一个 mock 建议，不涉及真实设备控制或业务链路。你可以在前端把这段 detail 作为卡片内容展示，并配置“接受/忽略”按钮。"
}
```

字段说明：
- `user_id` `string`，规范化后的用户 ID。
- `brief` `string`，建议摘要。
- `detail` `string`，建议详情文本。

### 2.4 示例 cURL
```bash
curl -X POST "http://localhost:8000/api/v1/generate_suggestion" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"u_1001"
  }'
```

---

## 3. Handle Suggestion 接口（Mock）

### 3.1 基本信息
- 方法：`POST`
- 路径：`/api/v1/handle_suggestion`
- 说明：接收一段建议详情并返回示例处理结果，当前为 mock，不做真实执行业务。

### 3.2 请求体
```json
{
  "detail_message": "用户点击了接受建议",
  "user_id": "u_1001"
}
```

字段说明：
- `detail_message` `string` 必填，要处理的建议详情文本。
- `user_id` `string` 选填，用户标识（传入时会进行规范化校验）。

### 3.3 响应体
```json
{
  "ok": true,
  "message": "suggestion handled (mock)",
  "echo_detail": "用户点击了接受建议",
  "user_id": "u_1001"
}
```

字段说明：
- `ok` `boolean`，处理是否成功（mock 固定为 `true`）。
- `message` `string`，处理结果说明。
- `echo_detail` `string`，回显入参 `detail_message`。
- `user_id` `string`，规范化后的用户 ID（未传则为空字符串）。

### 3.4 示例 cURL
```bash
curl -X POST "http://localhost:8000/api/v1/handle_suggestion" \
  -H "Content-Type: application/json" \
  -d '{
    "detail_message":"用户点击了接受建议",
    "user_id":"u_1001"
  }'
```

---

## 4. 错误码说明（通用）

- `400 Bad Request`
  - 参数缺失或格式不合法（例如 `user_id` 非法、`detail_message` 为空）。
- `500 Internal Server Error`
  - 服务内部异常。

## 5. 备注

- `generate_suggestion` 和 `handle_suggestion` 当前均为示例接口（mock），用于联调和前端演示。
- 如果后续接入真实建议引擎，建议保持响应字段兼容，避免影响前端渲染逻辑。
