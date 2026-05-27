# AI-HEMS 企业级记忆增强实施计划 (Phase 3)

> 说明（2026-02）：本方案中 DashVector 相关实现已在当前代码库移除，此文档保留为历史设计记录。

本计划旨在构建一个 **高可用、可扩展的 RAG (检索增强生成) 系统**，赋予 Agent "长期记忆" 和 "领域知识"，使其能够服务 1 万+ 用户并提供个性化建议。

## 1. 核心目标 (Objectives)
1.  **个性化记忆 (User Memory)**: 记住用户的非结构化偏好、生活习惯（如"周五回家"）、历史指令模式。
2.  **领域知识 (Domain Knowledge)**: 准确回答设备故障代码、电价政策、节能技巧（基于官方文档，而非幻觉）。
3.  **企业级标准**:
    - **高可用**: 使用阿里云托管服务 (DashVector)，而非本地文件。
    - **安全性**: 严格的数据隔离（User A 只能搜到 User A 的记忆）。
    - **低延迟**: 毫秒级向量检索。

## 2. 技术选型 (Enterprise Stack)

| 组件 | 选型 | 理由 |
| :--- | :--- | :--- |
| **RAG 框架** | **LlamaIndex** | 业界最成熟的数据框架，支持结构化/非结构化混合检索，易于扩展。 |
| **向量数据库** | **DashVector (阿里云)** | 全托管、Serverless、高性能，与阿里云生态（百炼/RDS）无缝集成。 |
| **Embedding** | **DashScope (text-embedding-v3)** | 通义千问同源向量模型，中文理解能力强，性价比高。 |
| **LLM** | **Qwen-Plus (百炼)** | 已接入，保持一致性。 |

## 3. 架构设计 (Memory Architecture)

### 3.1 记忆分层
- **短期记忆 (Short-term)**: 对话历史 (Chat History)。存储在 Redis 或内存中（当前 MVP 在内存）。
- **长期记忆 (Long-term)**:
    - **Fact Memory**: 结构化数据（如"设备ID", "费率套餐"） -> **MySQL** (已完成)。
    - **Semantic Memory**: 非结构化偏好（如"不喜欢半夜充电"） -> **DashVector (User Collection)**。
- **知识库 (Knowledge Base)**:
    - **Device Docs**: PDF/Markdown 说明书 -> **DashVector (Knowledge Collection)**。

### 3.2 数据流 (Data Flow)
1.  **写入 (Write)**: 用户说 "我周五通常回老家" -> Embedding -> 存入 DashVector (Metadata: `user_id=1001`).
2.  **检索 (Retrieve)**: 用户问 "明天要帮我预留电量吗？" -> Query "user_1001 travel plan" -> DashVector Top-K -> LLM Context.

## 4. 实施步骤 (Implementation Roadmap)

### Step 1: 基础设施准备
- 开通阿里云 DashVector 服务。
- 获取 API Key 和 Endpoint。
- 安装 `llama-index` 与向量检索 SDK（已停用）。

### Step 2: 向量存储适配 (`vector_store.py`)
- 封装 `DashVectorStore` 类。
- 实现 `add_document(text, metadata)` 和 `query(text, filter)` 方法。
- **关键点**: 必须支持 Metadata Filter (`user_id`)，确保多租户数据隔离。

### Step 3: 记忆服务层 (`memory_service.py`)
- **User Profile Manager**:
    - 自动提取对话中的"事实"（Fact Extraction）。
    - 将事实存入向量库。
- **RAG Engine**:
    - 构建 LlamaIndex 的 `QueryEngine`。
    - 集成 System Prompt。

### Step 4: 知识库导入 (Knowledge Ingestion)
- 创建 `scripts/ingest_docs.py`。
- 读取本地 `docs/` 目录下的设备说明书（Markdown/PDF）。
- 切片 (Chunking) -> Embedding -> 存入 DashVector `knowledge` Partition。

### Step 5: 集成与测试 (`main.py` & `llm_service.py`)
- 修改 `chat()` 流程：
    1.  User Input -> RAG Retrieve (User Profile + Knowledge).
    2.  Prompt = System + Retrieved Context + User Input.
    3.  LLM Generation.
- **验证**:
    - 告诉 Agent "我有一辆特斯拉"。
    - 重启。
    - 问 "我的车是什么牌子？"。

## 5. 风险控制
- **Token 消耗**: RAG 会显著增加 Prompt 长度。需优化 Top-K (建议 K=3) 和 Chunk Size。
- **隐私**: 确保 User A 的 Embedding 绝对不会被 User B 检索到（严格测试 Filter）。
