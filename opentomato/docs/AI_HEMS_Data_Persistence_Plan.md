# AI-HEMS 数据持久化实施计划 (Phase 2)

本计划旨在引入数据库层，使系统能够持久化存储设备遥测数据、用户策略配置，并赋予 Agent 查询历史数据的能力。

## 1. 技术选型 (Tech Stack)

考虑到目前是单机 Agent 原型，且我们已经使用了 Pydantic (`models.py`)，最佳实践是采用 **SQLModel** (基于 SQLAlchemy + Pydantic)。

- **Database**: **SQLite** (无需部署 Docker，单文件 `hems.db`，易于备份和查看)。
- **ORM**: **SQLModel** (完美复用现有的 Pydantic Models，减少代码重复)。
- **Migration**: Alembic (可选，暂时先用 `SQLModel.metadata.create_all` 自动建表)。

## 2. 实施步骤 (Steps)

### Step 1: 引入依赖
安装 `sqlmodel`。

### Step 2: 定义数据库模型 (`database.py` & `models.py` Refactor)
需要将现有的 Pydantic 模型升级为 SQLModel table 模型。
- **Table 1: `TelemetryRecord`**
    - 字段: `id`, `timestamp`, `pv_power`, `grid_power`, `load_power`, `battery_soc`, `battery_power`
    - 用途: 记录每一时刻的设备状态（历史账单基础）。
- **Table 2: `StrategyRecord`**
    - 字段: `id`, `timestamp`, `mode` (ECO/UPS...), `reason`, `target_soc`
    - 用途: 记录 Agent 每次下发的操作，用于审计和复盘。

### Step 3: 改造模拟器 (`device_simulator.py`)
- **当前**: `get_telemetry()` 只是生成数据并返回。
- **改造后**: `tick()` 方法在生成数据的同时，将其 **写入 SQLite 数据库**。
- **效果**: 即使 Agent 不在线，模拟器也在后台默默记录数据（模拟真实 IoT 设备上报）。

### Step 4: 改造 Agent 工具 (`agent_tools.py`)
- **增强 `get_system_status`**: 不仅读当前内存变量，也可以读 DB 中最新的一条记录。
- **新增 `get_energy_history`**:
    - 允许 LLM 查询过去的数据。
    - Prompt 示例: "昨天我发了多少光伏电？" -> SQL: `SELECT sum(pv_power) FROM telemetry WHERE date = yesterday`.

### Step 5: 验证与测试 (`main.py`)
- 运行模拟器一段时间（生成数据）。
- 重启程序（验证数据不丢失）。
- 向 Agent 提问历史相关问题（验证 Agent 读取 DB 的能力）。

## 3. 预期成果
完成此阶段后，Agent 将能够回答：
- "昨天这个时候电池有多少电？"
- "上一次切换到 ECO 模式是什么时候？"
- "过去一小时我向电网卖了多少电？"
