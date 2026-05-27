# FLS HEMS Agent Backend

`fls_hems_agent` 是面向家庭能源管理场景的 Agent 后端服务。它基于 FastAPI 提供对话、流式响应、语音识别、建议生成、知识库上传和长期记忆能力，并通过 OpenViking 承载多租户记忆与资源检索。

## 项目定位

这个服务不是一个单纯的聊天接口，而是 HEMS 系统里的智能编排层：

- 对外提供统一的 `/api/v1` HTTP API。
- 对内调度多个 Agent，完成路由、分析、控制建议、客服问答和主动建议。
- 通过工具系统连接能源数据、预测服务、OpenViking 记忆和资源库。
- 通过 Soul 性格配置控制回复风格，例如 `果断`、`热情`、`守护`、`共情`。
- 在 Kubernetes 中以 Helm Chart 方式部署，通常由前端 `fls-web` 通过同源 `/api/v1` 调用。

## 当前架构

```text
用户 / Web 前端
   |
   |  /api/v1/chat, /api/v1/chat/stream, /api/v1/resources/upload ...
   v
FastAPI API 层
   |
   v
ChatRuntime 阶段化执行
   |
   +-- load_user_summary      加载用户长期记忆摘要
   +-- load_chat_history      加载短期会话历史
   +-- find_memory            从 OpenViking 检索相关记忆
   +-- capture_memory         捕获本轮可能需要保存的信息
   +-- dispatch_agent         路由并调用具体 Agent
   +-- final_answer           生成最终回复
   +-- save_memory            写入会话与长期记忆
   |
   v
Agent 层
   |
   +-- router_agent           判断请求该交给谁处理
   +-- analyst_agent          能源分析与预测解释
   +-- control_agent          控制策略与安全约束
   +-- support_agent          用户支持、说明、记忆问答
   +-- suggestion_agent       主动建议生成
   |
   v
工具 / 外部系统
   |
   +-- OpenViking             长期记忆、资源库、向量检索
   +-- FeSolar Backend        设备、站点、业务数据
   +-- Forecast Service       光伏预测、天气相关能力
   +-- DashScope / OpenAI API 兼容模型服务
```

## 目录结构

```text
fls_hems_agent/
  app/
    core/
      main.py                 FastAPI 应用入口
      api/                    HTTP API 路由
      runtime/                生命周期、会话、ChatRuntime
      agent/                  Agent 管理、模型调用、Soul 加载
      memory/                 OpenViking 记忆客户端与服务封装
      logging/                统一日志系统
      config/                 配置读取和校验
    agents/                   各 Agent 的系统定义
    skills/                   可注入 Agent 的技能提示词
    souls/                    性格提示词
    tools/                    工具定义与执行逻辑
    fls_agent.yaml            Agent 拓扑、模型、工具和 handoff 配置
  chart/hems-agent-backend/   Helm Chart
  docs/                       接口文档、测试资料、设计说明
  Dockerfile                  后端镜像构建入口
  requirements.txt            Python 依赖
```

## Agent 配置

核心配置在 `app/fls_agent.yaml`。

当前主 Agent 是 `router`，它根据用户请求把任务交给下游 Agent。下游 Agent 可以绑定工具、读取记忆、提交记忆，也可以继续 handoff 给其他 Agent。

当前 Agent 列表：

- `router`：入口路由器，只负责判断任务去向。
- `analyst_agent`：能源数据分析、预测解读、运行状态解释。
- `control_agent`：控制策略、安全约束、设备运行建议。
- `support_agent`：日常问答、用户支持、个人记忆相关回复。
- `suggestion_agent`：主动生成节能、收益、备电等建议。

## 记忆与 OpenViking

后端通过 OpenViking 实现长期记忆和资源检索。当前推荐使用强隔离模式：

- `OPENVIKING_ENABLED=true`
- `OPENVIKING_STRONG_ISOLATION=true`
- 每个业务用户由后端映射到独立 OpenViking account/user/key。
- 会话内容会先写入 OpenViking session，再按策略 commit。
- 长期记忆摘要用于后续对话上下文加载。
- 资源文件通过 `/resources/upload` 接收后进入入库流程，最终可在 OpenViking 资源库中检索。

这样做的目标是让不同用户的个人记忆完全隔离，避免跨用户记忆污染。

## HTTP API

所有业务 API 默认挂在 `/api/v1` 下，健康检查除外。

### 对话

- `POST /api/v1/chat`
- `POST /api/v1/chat/stream`
- `GET /api/v1/chat/history`
- `POST /api/v1/chat/reset`
- `GET /api/v1/souls`

普通对话请求：

```json
{
  "message": "我今天应该怎么用电？",
  "user_id": "001",
  "soul": "果断"
}
```

普通对话响应：

```json
{
  "response": "建议优先在光伏出力较高的时段运行大功率设备，并保留一部分电池电量用于晚高峰。",
  "session_id": "001"
}
```

流式接口使用 SSE，事件类型主要包括：

- `state`：处理中间状态。
- `result`：最终回复。
- `error`：错误信息。
- `done`：流结束。

### 建议生成

- `POST /api/v1/generate_suggestion`
- `POST /api/v1/handle_suggestion`

用于首页或运营位生成主动建议。

### 语音

- `POST /api/v1/voice`

输入 base64 音频，返回识别文本。默认模型由配置控制，当前代码兼容 DashScope ASR。

### 资源上传

- `POST /api/v1/resources/upload`

使用 `multipart/form-data` 上传文件。常用字段：

- `file`：文件本体。
- `uploader`：上传来源，可选。
- `target_uri`：目标资源路径，可选。

### 健康检查

- `GET /healthz`
- `GET /readyz`

Kubernetes liveness/readiness probe 使用这两个接口。

## 日志系统

项目使用统一日志初始化逻辑，入口在 `app/core/logging/`。当前设计是：

- 应用日志、运行时日志、OpenViking 调用日志统一走 Python logging。
- Uvicorn 日志通过 `build_uvicorn_log_config()` 接入统一日志格式。
- 日志展示等级由项目配置中的 `loging_level` / 环境日志配置控制。
- OpenViking 提交、异步 commit、记忆抽取数量会输出业务日志，便于排查“是否真的写入记忆”。

## 本地运行

```powershell
cd fls_hems_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.core.main
```

服务默认监听：

```text
http://127.0.0.1:8000
```

快速验证：

```powershell
curl.exe http://127.0.0.1:8000/healthz
curl.exe -X POST http://127.0.0.1:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"你好\",\"user_id\":\"001\",\"soul\":\"果断\"}"
```

## Docker 与 Kubernetes

构建镜像：

```bash
docker build -t hems-agent-backend:local .
```

运行容器：

```bash
docker run --rm -p 8000:8000 --env-file .env hems-agent-backend:local
```

Helm Chart 位于：

```text
chart/hems-agent-backend/
```

关键 values：

- `image.repository` / `image.tag`：镜像地址和版本。
- `envFromSecret`：生产环境密钥来源。
- `env.OPENVIKING_ENABLED`：是否启用 OpenViking。
- `env.OPENVIKING_STRONG_ISOLATION`：是否启用用户强隔离。
- `ingress.hosts`：对外 API 域名。
- `ingress.annotations.nginx.ingress.kubernetes.io/proxy-body-size`：上传大小限制。
- `probes.livenessPath` / `probes.readinessPath`：健康检查路径。

## 关键配置

常用环境变量：

- `APP_ENV`
- `CORS_ALLOW_ORIGINS`
- `STRICT_EXTERNAL_DEPENDENCIES`
- `DASHSCOPE_API_KEY`
- `OPENVIKING_ENABLED`
- `OPENVIKING_URL`
- `OPENVIKING_STRONG_ISOLATION`
- `OPENVIKING_ROOT_API_KEY`
- `OPENVIKING_API_KEY`
- `OPENVIKING_TIMEOUT_SECONDS`
- `OPENVIKING_RECALL_TIMEOUT_SECONDS`
- `OPENVIKING_SESSION_COMMIT_EVERY_N`
- `OPENVIKING_SESSION_COMMIT_MAX_AGE_SECONDS`
- `INGEST_UPLOAD_MAX_MB`
- `INGEST_ALLOWED_EXTENSIONS`
- `FLS_BACKEND_BASE_URL`
- `FLS_FORECAST_BASE_URL`

不要把真实 `.env`、API Key、Kubernetes kubeconfig 提交到仓库。

## 与前端的关系

`fls-web` 在生产环境中通过 Nginx 同源代理调用本服务：

```text
/api/v1/* -> hems-agent-backend
```

因此前端不需要硬编码后端公网地址。这样可以避免不同环境之间串线，例如上海环境误调用 AWS 环境。

## 开发注意事项

- 修改 Agent 行为优先看 `app/fls_agent.yaml`、`app/agents/`、`app/skills/`、`app/souls/`。
- 修改 HTTP API 优先看 `app/core/api/`。
- 修改运行链路优先看 `app/core/runtime/chat/`。
- 修改记忆逻辑优先看 `app/core/memory/`。
- 修改部署参数优先看 `chart/hems-agent-backend/`。
- 新增日志时尽量使用结构化字段，避免只写自然语言，方便线上检索。
