# 🏕️ Multi-Agent Travel Planner (多智能体旅行规划系统)

基于 LangGraph 构建的多智能体（Multi-Agent）旅行规划系统。系统采用 Supervisor 统筹架构，结合高德地图 MCP 工具与多模态感知能力，依托长短双层记忆（STM & LTM）引擎，为用户提供端到端、防幻觉、高度个性化的定制旅行行程规划服务。

## ✨ 核心特性 (Core Features)

- **🧠 多智能体协同架构 (Supervisor Routing)** 摒弃单体大模型的逻辑瓶颈，构建 Supervisor 总控节点，统筹“天气、景点、酒店、行程”四大专家 Agent。通过图状态（Graph State）实现信息的高效流转与并行处理，端到端延迟控制在 20s 内。
- **⏳ 长短记忆双引擎 (LTM & STM)**
  - **短期记忆 (STM)：** 采用滑动窗口与 LLM 动态摘要机制，在 10 轮以上长对话场景中，将单次请求 Token 消耗稳定降低约 80%。
  - **长期记忆 (LTM)：** 基于 FastAPI 后台异步任务，静默提取并沉淀用户泛化偏好（如亲子游、饮食习惯、常住地）至 MySQL，实现跨会话的“拟人化”记忆唤醒。
- **🛡️ 高可用工具链与防幻觉设计** 深度集成高德地图 MCP，自研异步并发限流锁保护 API 稳定性。底层基于 ReAct 架构构建深度思考的专家 Agent，通过严格的系统指令（System Prompt）与工具调用容错机制，有效规避了传统 ReAct 易陷入死循环的痛点；结合 Pydantic 强校验，强制所有规划地点必须提取并绑定真实 POI ID，从根本上杜绝大模型的地理位置幻觉。
- **👁️ 多模态感知解耦** 支持用户上传参考图片（如风景图、游玩场景图）。构建前置视觉感知模块，利用 VLM（视觉语言模型）提取关键线索并降维为纯文本结构化数据，大幅降低主干大模型的 Token 开销与处理压力。
- **⚙️ 全栈工程化规范** 将系统 Prompt、工具权限池与业务约束抽离至 `settings.yaml`，实现逻辑与配置的彻底解耦；基于 `AsyncRedisSaver` 实现图状态的持久化与高可靠断点续传。

## 🏗️ 系统架构 (Architecture)

1. **入口网关层**：FastAPI 提供异步高并发支持，拦截多模态输入并进行降维处理。
2. **意图分析层 (Analyzer)**：提取用户查询要素，结合 MySQL 长期记忆库填补上下文槽位。
3. **多智能体编排层 (LangGraph)**：
   - **Supervisor**：任务分发。
   - **WeatherAgent / AttractionAgent / HotelAgent**：并行调用高德 API 收集信息。
   - **ItineraryAgent**：统筹汇总，生成结构化 JSON 行程。
4. **数据持久层**：Redis 负责会话的 Checkpoint 暂存，MySQL 负责用户画像和对话数据持久化。

## 🚀 快速开始 (Getting Started)

### 1. 环境准备

确保已安装 Python 3.10+，并准备好 Redis 和 MySQL 实例。

克隆仓库并安装依赖：

Bash

```
git clone  https://github.com/goodgqbb/travel_agent.git
cd travel_agent
pip install -r requirements.txt
```

### 2. 环境变量配置

在项目根目录创建 `.env` 文件，填入你的专属密钥：

Code snippet

```
# 大模型配置 (默认使用 Qwen)
API_KEY="your_llm_api_key"

# 高德地图 MCP 配置
AMAP_API_KEY="your_amap_api_key"

# 数据库配置
REDIS_URL="redis://localhost:6379/0"
MYSQL_URL="mysql+aiomysql://user:password@localhost/dbname"
```

### 3. 业务规则配置

系统行为与 Prompt 定义在 `settings.yaml` 中。如需调整各个专家的工具权限或系统指令，请直接修改该文件，无需重启服务或修改代码。

### 4. 启动服务

Bash

```
python main.py
```

## 📂 目录结构 (Project Structure)

Plaintext

```
travel_agent/
├── app/
│   ├── agents/          # Agent 逻辑层 (BaseAgent、四大专家、Supervisor 及视觉感知)
│   ├── core/            # 核心引擎层 (LangGraph 图编排、状态定义 State、全局配置)
│   ├── data/            # 静态数据与资源存放目录
│   ├── memory/          # 记忆管理模块 (Redis 短期会话压缩、MySQL 长期画像盘点)
│   ├── schemas/         # Pydantic 结构化数据模型 (出入参强校验)
│   └── tools/           # 外部工具集 (高德 MCP API 封装、限流锁、本地工具等)
├── config/              # 系统配置目录 (存放 config.yaml 业务规则与系统指令)
├── templates/           # 前端 UI 模板目录 (基于 FastAPI 渲染的界面或组件)
├── testimage/           # 多模态测试目录 (存放用于视觉感知 Agent 测试的本地图片)
├── tests/               # 自动化测试用例目录
├── .env.example         # 环境变量配置模板
├── requirements.txt     # Python 核心依赖清单
└── README.md            # 项目说明文档
```

## 🗺️ 未来规划 (Roadmap)

- [ ] **接入 RAG 知识库**：利用 RedisSearch 引入小红书/马蜂窝本地游记向量库，提供非标准化的隐藏玩法推荐。
- [ ] **前端交互界面**：开发适配该接口的 Chat UI，实现带地图卡片的富文本展示。
