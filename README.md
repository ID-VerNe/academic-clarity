# Academic Clarity

一个支持 AI 驱动的学术文献处理系统，具备 OCR 识别、元数据提取和智能对话功能。

## 功能特性

- **PDF OCR 识别**: 使用 DeepSeek-OCR 将学术论文转换为结构化 Markdown
- **智能元数据提取**: 自动提取标题、作者、期刊、DOI、摘要等信息
- **多维度知识图谱**: 支持多种元数据集的动态扩展
- **高并发任务处理**: 10-Worker 并行任务队列，支持失败自动重试
- **实时进度展示**: 红/黄/绿三色直观展示文献处理进度

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React 19 + TypeScript + Vite | 现代前端框架 |
| 后端 | Python 3 + FastAPI | 高性能 API 服务 |
| 数据库 | SQLite (WAL 模式) | 轻量级数据库 |
| OCR | DeepSeek-OCR (SiliconFlow) | 专业文档识别 |
| 任务调度 | asyncio.Queue | 10-Worker 并发处理 |

## 快速开始

### 前置依赖

- Node.js 20+
- Python 3.10+
- pnpm (推荐)

### 安装与运行

```bash
# 1. 安装前端依赖
pnpm install

# 2. 创建配置文件
cp backend/config.py.example backend/config.py
# 编辑 backend/config.py，填入你的 API Key

# 3. 启动后端服务
python backend/server.py

# 4. 启动前端开发服务器（新终端）
pnpm run dev
```

或者使用批处理脚本：

```bash
# 启动应用
scripts/run_app.bat

# 运行测试
scripts/run_tests.bat
```

## 配置说明

### API 配置

在 `backend/config.py` 中配置以下参数：

```python
# DeepSeek OCR (通过 SiliconFlow)
DEEPSEEK_API_KEY = "sk-..."
API_BASE = "https://api.siliconflow.cn/v1"
OCR_MODEL = "openai/deepseek-ai/DeepSeek-OCR"

# 本地 LLM (用于元数据提取和对话)
LLM_API_KEY = "sk-copilot-sdk-default"
LLM_API_BASE = "http://localhost:37210/v1"
LLM_MODEL = "gpt-4.1"
```

### 配置优先级

1. **数据库设置** - 通过应用界面动态配置
2. **config.py 文件** - 本地配置文件
3. **硬编码默认值** - 代码中的保底值

## 项目结构

```
academic-clarity/
├── backend/                 # 后端服务
│   ├── core/               # 核心组件
│   │   └── task_manager.py # 任务队列管理器
│   ├── services/           # 业务服务
│   │   ├── ai_service.py   # AI 服务调用
│   │   ├── config_service.py # 配置管理
│   │   ├── ocr_service.py  # OCR 处理服务
│   │   └── workspace_service.py # 工作空间管理
│   ├── utils/              # 工具函数
│   ├── vendor/             # 第三方依赖
│   ├── server.py           # FastAPI 入口
│   └── config.py.example   # 配置模板
├── electron/               # Electron 主进程
├── src/                    # 前端源代码
│   ├── api/                # API 客户端
│   ├── components/         # React 组件
│   │   ├── Dashboard.tsx   # 仪表盘
│   │   ├── Reader.tsx      # 阅读器
│   │   └── reader/         # 阅读器子组件
│   ├── hooks/              # 自定义 Hooks
│   └── types/              # TypeScript 类型定义
├── tests/                  # 测试用例
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   ├── security/           # 安全审计
│   └── system/             # 系统测试
├── scripts/                # 运行脚本
│   ├── run_app.bat
│   └── run_tests.bat
└── agents.md               # 代理配置文档
```

## 测试

项目采用分层测试策略：

| 层级 | 工具 | 命令 |
|------|------|------|
| 单元测试 | Python unittest | `python tests/unit/test_database.py` |
| 安全测试 | 自定义审计 | `python tests/security/test_final_audit.py` |
| 集成测试 | 真实 API | `python tests/system/test_real_world.py` |
| 构建测试 | Vite/TSC | `pnpm build` |

运行全部测试：

```bash
scripts/run_tests.bat
```

## 开发规范

- **测试优先**: 所有新功能必须有对应的测试用例
- **配置中心化**: 使用 `ConfigService` 管理配置
- **单一职责**: 每个文件不超过 200 行
- **并行测试**: 测试必须支持并行运行（使用 UUID 临时数据）

## 许可证

MIT License

---

**项目地址**: [https://github.com/ID-VerNe/academic-clarity](https://github.com/ID-VerNe/academic-clarity)