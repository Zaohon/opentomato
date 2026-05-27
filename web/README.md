# FLS Web

`fls-web` 是 FLS HEMS 智能能源系统的前端应用。它基于 React、Vite 和 TypeScript 构建，提供家庭能源看板、AI 对话、知识库入口、批量问题集测试和运行状态展示。

## 项目定位

这个项目是用户与 Agent 后端交互的 Web 门户：

- 展示家庭能源系统的概览、设备状态、收益和历史曲线。
- 提供 AI 聊天面板，支持 Soul 性格选择、流式响应、语音输入和历史上下文。
- 提供批量问题集测试工具，用于并发验证 Agent 回复质量。
- 提供知识库管理入口，跳转到 OpenViking Web Studio。
- 在生产环境中通过 Nginx 反向代理后端 API，避免前端硬编码环境地址。

## 当前架构

```text
浏览器
   |
   v
React / Vite 单页应用
   |
   +-- App.tsx                         页面路由与主看板状态
   +-- components/AiChatPanel.tsx      AI 对话面板
   +-- components/BatchQuestionTestPanel.tsx
   +-- components/KnowledgeUploadPage.tsx
   +-- components/IsoHouse.tsx         首页能源可视化
   +-- services/agentService.ts        Agent API 封装
   +-- services/pvService.ts           光伏预测服务封装
   |
   v
Nginx / Vite Proxy
   |
   +-- /api/v1/*  -> hems-agent-backend
   +-- /ov/*      -> openviking:1933
   +-- /web-studio -> OpenViking Web Studio 入口
```

## 目录结构

```text
fls-web/
  App.tsx                       应用主入口和页面状态
  index.tsx                     React 挂载入口
  index.css                     全局样式
  types.ts                      前端共享类型
  components/
    AiChatPanel.tsx             对话、语音、Soul 选择、流式消息
    BatchQuestionTestPanel.tsx  批量问题集测试
    KnowledgeUploadPage.tsx     知识库上传入口页
    IsoHouse.tsx                3D/等距家庭能源示意图
    Charts.tsx                  图表组件
    SettingsPanel.tsx           设置面板
  services/
    agentService.ts             `/api/v1` 调用封装
    pvService.ts                `/api/eas` 光伏预测调用封装
  chart/fls-web/                Helm Chart
  nginx.conf                    HTTP Nginx 模板
  nginx.ssl.conf                HTTPS Nginx 模板
  docker-entrypoint.d/          容器启动时选择 Nginx 配置
  Dockerfile                    多阶段构建镜像
```

## 主要功能

### 能源看板

首页展示家庭能源系统状态，包括：

- 光伏、负载、电池、电网、EV 等关键指标。
- 经济模式、备电模式、FeSolar AI 模式。
- 当日功率曲线和历史趋势。
- 系统健康状态 `/api/v1/system-info`。

### AI 聊天

聊天面板通过 `services/agentService.ts` 调用 Agent 后端：

- `GET /api/v1/souls`：加载可选性格。
- `POST /api/v1/chat/stream`：流式对话。
- `GET /api/v1/chat/history`：加载历史。
- `POST /api/v1/chat/reset`：清空会话并触发记忆提交。
- `POST /api/v1/voice`：语音转文字。

前端统一把用户编号标准化为三位数字，例如 `1` -> `001`。

### Soul 性格

Soul 由后端提供，前端只负责展示和传参。当前批量测试默认使用 `果断`，也支持在第一行统一选择其他性格。

常见性格：

- `果断`：直接、高效、行动导向。
- `热情`：积极、鼓励、表达充分。
- `守护`：稳妥、谨慎、重视安全。
- `共情`：温和、理解、关注感受。

### 批量问题集测试

`BatchQuestionTestPanel` 用于上传 Excel 问题集并并发调用 Agent：

- 支持下载示例问题集。
- 支持上传 `.xlsx` / `.xls`。
- 默认 10 个测试用户并发轮询。
- 支持统一选择一个 Soul。
- 输出每题状态、耗时、答案和错误。
- 支持下载测试报告。

### 知识库管理

知识库管理入口导向：

```text
/web-studio
```

OpenViking API 通过同源路径代理：

```text
/ov/* -> openviking:1933
```

这样上海、AWS、本地环境都可以用各自的 Ingress/Nginx 配置连接自己的 OpenViking，避免跨环境访问。

## API 路由

### 本地开发

`vite.config.ts` 配置了开发代理：

```text
/api/v1 -> http://localhost:8000
/api/eas -> http://1961664646385841.cn-shanghai.pai-eas.aliyuncs.com
```

所以本地启动后，前端仍然使用同源路径：

```text
http://localhost:3000/api/v1/...
```

### 容器部署

Nginx 模板使用环境变量控制上游：

- `AGENT_API_UPSTREAM`，默认 `http://hems-agent-backend`
- `OPENVIKING_API_UPSTREAM`，默认 `http://openviking:1933`

容器启动时会检查 `/etc/nginx/tls/tls.crt` 和 `/etc/nginx/tls/tls.key`：

- 如果存在证书，使用 HTTPS Nginx 配置。
- 如果不存在证书，使用 HTTP Nginx 配置。

## 本地运行

安装依赖：

```powershell
cd fls-web
npm install
```

启动开发服务：

```powershell
npm run dev
```

默认地址：

```text
http://localhost:3000
```

构建生产包：

```powershell
npm run build
```

本地预览：

```powershell
npm run preview
```

## Docker 与 Kubernetes

构建镜像：

```bash
docker build -t fls-web:local .
```

运行容器：

```bash
docker run --rm -p 8080:80 \
  -e AGENT_API_UPSTREAM=http://host.docker.internal:8000 \
  -e OPENVIKING_API_UPSTREAM=http://host.docker.internal:1933 \
  fls-web:local
```

Helm Chart 位于：

```text
chart/fls-web/
```

关键 values：

- `image.repository` / `image.tag`：前端镜像。
- `backend.apiUpstream`：Agent 后端上游。
- `backend.openvikingApiUpstream`：OpenViking API 上游。
- `ingress.hosts`：前端访问域名。
- `tls.enabled` / `tls.secretName`：是否启用 HTTPS。
- `resources`：Pod CPU/内存资源。
- `probes.path`：健康检查路径，默认 `/healthz`。

## 与后端的关系

前端不直接维护业务记忆、Agent 状态或 OpenViking 多租户逻辑。职责边界是：

- Web 负责页面、交互、上传、流式展示和测试工具。
- Agent 后端负责模型调用、Agent 编排、记忆读写、资源入库。
- OpenViking 负责长期记忆、资源库、向量检索和 Web Studio。

推荐所有环境都使用同源路径：

```text
Web -> /api/v1 -> Agent Backend
Web -> /ov     -> OpenViking API
Web -> /web-studio -> OpenViking Web Studio
```

不要在前端代码里硬编码 `agent-aws-dev`、`agent-dev` 这类环境域名，否则容易出现上海环境误连 AWS 环境的问题。

## 开发注意事项

- 修改对话调用逻辑看 `services/agentService.ts`。
- 修改聊天 UI 看 `components/AiChatPanel.tsx`。
- 修改批量测试看 `components/BatchQuestionTestPanel.tsx`。
- 修改知识库入口看 `App.tsx` 和 `components/KnowledgeUploadPage.tsx`。
- 修改部署代理看 `nginx.conf`、`nginx.ssl.conf` 和 `chart/fls-web/values*.yaml`。
- 不要提交 `.env`、真实 API Key、kubeconfig 或临时测试文件。
