# 否决组件论证 + 共享基础设施方案

**日期**: 2026-10-14
**定位**: 《plans/integrate-paper-tools.md》（下称"总方案"）的配套文档。总方案定"做什么"，本文定"为什么不做"与"Phase 0-3 共用的地基"。
**读者**: 后续各阶段实施者（人或 agent）。所有结论可按文中 `路径:行号` 复核。
**核查方式**: 只读检查（读源码 + 只读 git 信息）；未运行项目测试、未起服务、未做任何 git 写操作、未改项目源码。

---

## 1. 文档目的与使用方式

- 本文两部分互相独立：
  - **§2 否决组件论证**：每项 = 核查方法 → 事实证据（路径:行号）→ 结论 → 重新评估触发条件。是可复现的核查记录，不是观点。
  - **§3-§10 共享基础设施**：所有阶段都必须遵守的公共规范（vendor、DB 迁移、网络、测试、分支、文档、风险总表、实施顺序）。
- 使用规则：
  1. 想"顺手把某个组件也 vendor 进来"前，先读 §2 对应小节；触发条件未满足不做。
  2. 每开一个新 feature 分支，先过 §10 实施顺序检查清单。
  3. 本文与 `agents.md` 冲突时，以 agents.md 为准并回改本文。

---

## 2. 否决组件论证

### 2.1 paper-prep — agent skill 而非库；流水线已被现有能力覆盖

**核查方法**：通读 `paper-prep/SKILL.md`、`scripts/doi_pipeline.py`、`scripts/paper_prep/` 全部模块；grep `tex2txt` 验证 LaTeX 覆盖。

**事实证据**：

| 待验证命题 | 证据 |
|---|---|
| 是 Claude Code agent skill | SKILL.md:2-6 frontmatter（`version: 1.2.0`，`requires: [python, uv]`）；SKILL.md:11"你（AI）是调度器，不是执行者"——为 AI 编排设计，无库 API；SKILL.md:29 + 206-213：经 `mklink /J` junction 安装到 `~/.claude/skills/paper-prep`，链接断则 scripts/ 丢失 |
| 依赖 uv 运行时 | SKILL.md:19/98/107 全部用法为 `uv run python ...`；python_embed 无 pip/uv（总方案 §1 已核实） |
| 流水线步骤 | doi_pipeline.py:105 `["ocr","match","verify","report","bibtex","rename"]` |
| OCR 步骤不在本包 | step_ocr.py:14 调 `pdf_doi_toolkit.TitleExtractor`；后者 title_extractor.py:5-6 注明"subprocess 调用 [DeepSeek-OCR] CLI，而不是直接 import" |
| match/verify/bibtex 即 pdf-doi-toolkit | doi_pipeline.py:32 直接 import `pdf_doi_toolkit`——核心能力就是 Phase 1 要 vendor 的包 |
| rename 步骤无对应需求 | 面向"乱码命名 PDF 文件夹"的文件重命名（SKILL.md:36-47）；本项目元数据入 DB、文件存 workspace |
| 与 tex2txt 的关系 | grep `tex2txt` 于 paper-prep/ 全目录：**0 命中**。总方案 §2"其流水线 = tex2txt + pdf-doi-toolkit 组合"表述不准确（实际不含 tex2txt），但不影响结论 |
| 可复用部分评估 | `llm_verifier.py:54`（`from openai import OpenAI`）——openai 2.26.0 在 python_embed 在位，技术可跑，但其双通道标题验证逻辑 Phase 1 的 doi_service 将以 fuzzy+作者验证重写，重复建设；`verify.py` 三方比对思想可参考、不复制 |
| 安全反向证据 | `paper_prep/__init__.py:35-40`：导入即把 `ssl._create_default_https_context` 全局替换为不校验证书版本——进程级副作用，会污染本项目全部 HTTPS 调用 |

**结论**：❌ 不集成。它是"AI 调度器 + CLI"形态的 skill：uv 运行时、junction 安装、导入即全局关 SSL 三个特性都与本项目嵌入式 Python + FastAPI 架构冲突。六个步骤中 OCR=本项目已有 SiliconFlow 流水线，match/verify/bibtex=pdf-doi-toolkit（Phase 1），rename=DB 驱动架构下无需求。

**重新评估触发条件**：无。若未来要"双通道 LLM 标题验证"，按 doi_service 需求重写（借鉴思想，不搬代码）。

### 2.2 scihub — 版权与学术伦理风险，一票否决

**核查方法**：读 `scihub/scihub.py`、`README.md`、`link.txt`、`pyproject.toml`；核对 python_embed 依赖。

**事实证据**：

| 项 | 证据 |
|---|---|
| 功能 | README.md:1-3"Download academic papers from Sci-Hub by DOI"；scihub.py:49-58 `SciHub` 类按 DOI 从镜像下载 PDF |
| 镜像机制 | link.txt 内置 sci-hub.al/.ee/.in/.mk/.ru/.sg/.su/.tf/.vg 等；scihub.py:128-148 全部失败时暴力扫描 1352 个 `sci-hub.{xx}` TLD；scihub.py:57 伪造浏览器 User-Agent |
| 依赖缺口 | pyproject.toml 依赖 `requests` + `beautifulsoup4`；实测 python_embed **无** beautifulsoup4/bs4，且无 pip/uv 可补 |
| 法律定位 | Sci-Hub 存储未授权付费论文全文；doi.txt 中已存 10.1039/D0TC00002G 等真实受版权保护论文 DOI |

**结论**：❌ 不集成，且无"可复用部分"——镜像发现、验证码规避逻辑无正当用途。本项目是 GPLv3 分发的桌面应用，内置该功能等于把侵权能力产品化；用户（博士生）的学术伦理与法律风险远大于便利。合法替代：Unpaywall / OpenAlex / Semantic Scholar 开放 API。§5 网络白名单仅 `api.crossref.org`，不扩展到任何 Sci-Hub 域名。

**重新评估触发条件**：无（法律风险不随时间消失）。全文获取需求走机构订阅或 OA API。

### 2.3 llm_wiki — Tauri/Rust 未构建检出；用户自己的决策记录已判"推迟"

**核查方法**：检查目录结构与构建产物；读用户决策记录 `.plan/knowledge-layer-master-plan.md` §2 与附录 B。

**事实证据**：

| 项 | 证据 |
|---|---|
| 技术形态 | `src-tauri/Cargo.toml:10` `rust-version = "1.88"`，:26 `tauri = 2`；package.json 含 `@tauri-apps/*`、React、mcp-server——完整 Tauri 桌面应用 |
| 未构建源码检出 | 目录下**无** `node_modules`、**无** `src-tauri/target`（均已实测为空）；安装需 Node 依赖 + Rust 1.88+ + protoc |
| 用户决策（第一轮） | knowledge-layer-master-plan.md:38-42："**现在不引入 LLM Wiki。不是拒绝，是推迟**"；理由：真正约束是人的注意力/维护成本 + 安装可靠性（异国栈 + 抖动网络），非算力 |
| 附录 B | knowledge-layer-master-plan.md:339-341："源码检出，未构建……**仅供借鉴模式参考，不安装其 Tauri/Rust 应用（第一轮结论：推迟）**" |
| 模式已被提取 | master-plan:224-231：llm_wiki 的存储模式（frontmatter 契约、log.md 仅代码追加、`cite://` 锚点、FTS5 tokenizer 修复——trigram 对 2 字符 CJK 返 0 行的 config 级 bug，master-plan:53）已全部落地到 paper-tools 的 `know` 包；Phase 2 vendor 的是 `know`，不是 llm_wiki |

**结论**：❌ 不集成组件本身。其目标能力（概念级、agent 可查询知识层）已以 `know` 包（Python，stdlib+pyyaml+sqlite3，与 python_embed 兼容）形态存在；llm_wiki 本体是第二个需独立工具链长期维护的桌面应用，与"单一产品"目标冲突。

**重新评估触发条件**（须全部满足）：① Phase 2 know 层真实使用中被证明能力不足；② 网络环境稳定到能可靠拉取 Node/Rust 依赖；③ 用户愿意长期维护第二个应用。任一不满足即维持否决。

### 2.4 DeepSeek-OCR（paper-tools 内副本）— 前提更正：不是本地 GPU 模型，而是 SiliconFlow API 的重复封装

**核查方法**：统计目录构成；读 pyproject.toml/README.md/settings.json；find 模型权重文件；核对 python_embed 依赖。

**事实证据**：

| 项 | 证据 |
|---|---|
| 真实形态 | pyproject.toml:4"DeepSeek-OCR **API 本地封装**：PDF/EPUB 转 Markdown，**无需本地 GPU**"；README.md:3 同；settings.json 指向 `https://api.siliconflow.cn/v1/chat/completions` |
| 体量构成 | 目录共 82MB，其中 `.venv`（uv 虚拟环境）占绝大部分；4 个源码 .py 合计约 41KB；uv.lock 84KB。**无任何模型权重**（find `*.safetensors/*.bin/*.pt/*.gguf`：0 命中）；依赖为 beautifulsoup4/ebooklib/html2text/pillow/pymupdf/requests/tqdm，无 torch/transformers |
| 依赖缺口 | 实测 python_embed 无 beautifulsoup4、ebooklib、html2text |
| 与本项目重叠 | `backend/services/ai_service.py:90-149` 已实现同一 SiliconFlow DeepSeek-OCR 调用且更强：多 key 池（`core/api_key_manager.py`）、task_hub 并发、ConfigService 集中配置、进度入 DB |
| 对总方案的更正 | 总方案 §2 标注其依赖为"GPU/模型权重"——**该前提不成立**。结论不变但理由更强：不是"太重"，而是"功能重复且集成度更弱"（文件式 settings.json vs ConfigService，无 key 池） |

**结论**：❌ 不集成。唯一可借鉴点：README.md 自述的"指数退避重试 + 不可重试错误（Key 无效/余额不足）快速失败"策略，已抽象进 §5 重试规范。

**重新评估触发条件**：本项目 litellm OCR 链路出现 SiliconFlow 侧不兼容，且其引擎有本项目缺失的页面解析/EPUB 能力时，按"适配器包裹"评估（而非 vendor 整包）。

### 2.5 knowledge-base/ — 只有 markdown 归档 + sqlite 索引，无 PDF 源文件

**核查方法**：ls 目录；读 schema.md/catalog.md/log.md；统计 papers/。

**事实证据**：

| 项 | 证据 |
|---|---|
| 内容构成 | `papers/` 84 个 `.md`（每篇：frontmatter + claims + cite:// 锚点表）；`concepts/` 仅 1 个（fdia.md）；`catalog.md`（代码生成，"papers: 84"）；`log.md`（仅代码追加的摄取日志）；`index.sqlite`（查询底座，可重建）；`schema.md`（agent 查询协议） |
| 无 PDF | 全目录无任何 PDF/源文献文件 |
| 锚点悬空 | claims 的 `cite://{paper}/{anchor}` 指向的 OCR 段落文本在 paper-tools 语料目录（master-plan:144），不在本目录也不在本项目 workspace |

**结论**：❌ 不作为语料集成。无 PDF 意味着无法重新 OCR、无法进入本项目 `ocr_markdown → Basic Insight → 知识层` 流水线、锚点无法在本项目内解析。**可选未来用途**：Phase 2 完成后作为知识层 UI 演示种子数据（只用其 markdown，不依赖锚点可解析）。

**重新评估触发条件**：Phase 2 知识层上线且需要演示数据；或用户将 paper-tools 语料 PDF 纳入本项目 workspace。

### 2.6 phase0-lab/ 与 outputs/ — 研究实验与报告草稿，非生产工具

**核查方法**：ls 两目录；读报告文件头。

**事实证据**：

| 项 | 证据 |
|---|---|
| phase0-lab/ | 一次性实验脚本：analyze_ocr_diff.py、phase05_final.py、backfill_run.py、corpusB_verify.py 等；报告 PHASE0_REPORT.md / PHASE05_REPORT.md / PHASE2_REPORT.md / PHASE10_REPORT.md / KNOW_EVIDENCE.md；labs/（两次 OCR 原始输出）、prompts_v2/、src/ |
| outputs/ | 两轮 multi-lens-research 产物：direction-judge/（8 个 .md，第一轮"是否引入 LLM Wiki"）、tech-architecture/（8 个 .md，第二轮存储架构） |
| 无生产入口 | 无 CLI、无服务、无库 API；脚本含硬编码个人语料路径（如 master-plan:9 测试床路径） |

**结论**：❌ 不集成。但其**证据价值**必须在 Phase 2 引用：① 同 PDF 两次 OCR 段落漂移 <5%（PHASE0，master-plan:77-91）→ 支撑 sha1-8 锚点方案；② evidence_quote 真实命中率 90.5%/96.1%（master-plan:297-299）→ 支撑 claims 质量预期。两条已写入 §9 风险表依据列。

**重新评估触发条件**：无（研究报告不会变成生产工具）。Phase 2 锚点稳定性出问题时可回读 PHASE0_REPORT.md 的实验方法重测。

---

## 3. vendor/ 管理策略

适用于 Phase 0（tex2txt）、Phase 1（pdf_doi_toolkit）、Phase 2（know）三批；Phase 3 不 vendor。

### 3.1 逐字拷贝原则
1. **禁改**：vendor/ 下文件一个字节都不改（agents.md 红线）。适配逻辑全部放 `backend/services/*_service.py`（每文件 ≤200 行）。
2. **不放构建/配置文件**：不拷 pyproject.toml、uv.lock、.python-version、settings.json、llm.ini。python_embed 无 pip/uv，依赖以"零三方依赖或 python_embed 已有"为准（tex2txt/pdf_doi_toolkit 零依赖；know 需 pyyaml 6.0.3，实测在位）。
3. **清 __pycache__**：拷贝后删除所有 `__pycache__/`（paper-tools 各目录自带运行时残留，如 DeepSeek-OCR/__pycache__）。
4. **目录形态**：`backend/vendor/tex2txt/`、`backend/vendor/pdf_doi_toolkit/`、`backend/vendor/know/`（与总方案 §3 一致）。

### 3.2 来源版本记录（升级 = 整包替换）
paper-tools 是 git 仓库。每个 vendor 批次必须在 `backend/vendor/VENDOR.md` 登记：

```markdown
| 包 | 来源路径 | 来源 commit | 日期 | 备注 |
|---|---|---|---|---|
| tex2txt | paper-tools/tex2txt/src/tex2txt/ | <full-sha> | 2026-10-14 | Phase 0 |
```

记录方法（只读命令）：
```bash
git -C "C:/Users/VerNe/Downloads/Documents/paper-tools" rev-parse HEAD
```
本次核查时 paper-tools HEAD = `176ac7b1ec7ddc52cc05ada7a84b08c072bb6339`（2026-09-02，feat(know): corpus B extraction…），且工作区**有未提交改动**（DeepSeek-OCR/uv.lock、scihub/uv.lock 被修改，know/uv.lock 未跟踪）。登记规则：工作区干净→直接记 commit；不干净→记 commit + 注明"按当时磁盘状态拷贝"。

**升级流程**：paper-tools 更新 → 整包覆盖重拷 → 更新 VENDOR.md → 跑全部测试。禁止在 vendor/ 内打补丁；"只差一行"的修改也必须走适配层。

### 3.3 sys.path 注入方式
沿用 `backend/server.py:20-21` 既有模式：
```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
```
vendor 包置于 `backend/vendor/` 下即可被 `backend/` 内模块导入。若包名与目录名不一致（如 `backend/vendor/pdf_doi_toolkit/pdf_doi_toolkit/`），只在适配器顶部把该子目录加入 sys.path——写法参考 `paper-prep/scripts/paper_prep/__init__.py:28-30`，但**不得**复制其 SSL 补丁（§2.1）。测试内的路径发现见 §6.2。

### 3.4 许可与合规
paper-tools 无显式 license 文件（本次核查未见）。均为用户本人仓库，实际风险低；VENDOR.md 注明"来源为用户本人 paper-tools 仓库，无显式 license；对外公开发布前需补声明"。

---

## 4. DB 迁移模式

### 4.1 现状（已核实）
`backend/database.py:39-73` `init_db()` 只有 `CREATE TABLE IF NOT EXISTS`（configs / documents / document_metadata 三表），**无任何 ALTER TABLE 迁移机制**。旧 workspace 的 `library.db` 由旧代码创建；新代码加列后直接打开不报错，但新列不存在会导致 INSERT/UPDATE 失败。WAL 已启用（database.py:19-22）。

### 4.2 安全迁移代码骨架（database.py，init_db 内调用）
```python
def _ensure_columns(cursor, table: str, columns: dict) -> None:
    """幂等加列：columns = {列名: 列定义SQL}。已存在则跳过。"""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    for name, ddl in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

# init_db() 内，CREATE TABLE 之后：
_ensure_columns(cursor, "documents", {
    "doi": "TEXT",
    "bibtex": "TEXT",
    "doi_source": "TEXT",        # 'crossref' | 'llm' | NULL
})
```
规则：
1. **只加列、不删不改类型**：ADD COLUMN 安全；改类型/删列一律新建表 + 拷数据，且单独评审。
2. **幂等**：每次 init 都跑，新旧 workspace 同走一条代码路径，无手工升级步骤。
3. **NOT NULL 列必须带 DEFAULT**，否则旧行阻塞。
4. Phase 2 的 `{workspace}/knowledge/index.sqlite` 是独立库（总方案 §4 Phase 2），不进 library.db 迁移链，避免双库 schema 耦合。

### 4.3 迁移单测要求（Phase 1 落地时写入 tests/unit/test_database.py）
沿用该文件既有 UUID + tearDown 删 `-wal`/`-shm` 写法（test_database.py:22,26-34）：
```python
def test_migration_adds_columns_to_legacy_db(self):
    # 1. 用旧 schema 手工建库（documents 仅原 11 列，插一行旧数据）
    # 2. Database(legacy_path)               # 触发 init_db 迁移
    # 3. 断言 PRAGMA table_info(documents) 含 doi/bibtex/doi_source
    # 4. 断言旧行数据仍在、新列为 NULL（不丢数据）
    # 5. 再次 Database(path)                 # 幂等：不抛异常、列不重复
```

---

## 5. 网络调用策略（Phase 1 起强制执行）

### 5.1 硬规则
| 项 | 规则 | 依据 |
|---|---|---|
| 域名白名单 | 仅 `api.crossref.org`（含 content-negotiation）；任何其他域名（含全部 Sci-Hub 镜像）禁止 | 总方案 §5；§2.2 |
| timeout | 连接 5s / 读取 10s。对齐 `backend/constants.py:31-34`（CONNECT_TIMEOUT=5.0、REQUEST_TIMEOUT=30.0；CrossRef 取更严值） | constants.py |
| 重试 | 最多 1 次 + 指数退避（0.5s→1s）；仅 5xx/超时重试，4xx 不重试 | 借鉴 DeepSeek-OCR README"不可重试错误快速失败"；总方案 §4 Phase 1 |
| mailto | CrossRef 礼貌池参数走 ConfigService（key=`CROSSREF_MAILTO`），禁硬编码 | agents.md §5 |
| 离线降级 | 校验失败不阻塞流水线：返回 `status='unverified'` + 原 llm_doi，`doi_source='llm'`，日志 WARN，UI 标注"未校验" | 总方案 §4 Phase 1 |
| HTTPS | 禁止任何 `ssl._create_unverified_context` 全局替换（`paper_prep/__init__.py:35-40` 反面教材）；python_embed 有 certifi（实测在位） | §2.1 |

### 5.2 代码骨架（backend/services/doi_service.py）
```python
ALLOWED_HOSTS = {"api.crossref.org"}

def _guarded_get(url: str, timeout: float = 10.0, retries: int = 1):
    host = urllib.parse.urlparse(url).hostname or ""
    if host not in ALLOWED_HOSTS:
        raise SSRFBlockedError(f"host not allowed: {host}")     # security 测试覆盖
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": f"academic-clarity/1.0 (mailto:{mailto})"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500:
                break                                             # 4xx 不重试
            time.sleep(0.5 * (2 ** attempt))
    raise NetworkUnavailableError(str(last))                      # 调用方降级
```
用 urllib 而非 requests：`pdf-doi-toolkit/crossref.py:111-112` 即 urllib + timeout，stdlib 零依赖，与 vendor 策略一致。

### 5.3 代理陷阱通用规则（提炼自 paper-prep/SKILL.md:80）
**教训原文**：`.claude/settings.json` 全局注入 `OPENAI_API_KEY=PROXY_MANAGED` + 对 deepseek/glm 返回 403 的 proxy；子进程继承后"任何依赖 `OPENAI_*` 的配置默认就连错端点，且静默降级不报错"。

通用规则（写入 agents.md）：
1. **服务配置只从 ConfigService（DB）读**，不用环境变量兜底，杜绝"环境里恰好有同名变量"。
2. 必须起子进程时，传**净化后的 env 白名单**，不整份继承 `os.environ`。
3. 网络失败必须**显式上报**（unverified 状态 + 日志），禁止静默降级——静默是这次事故中最贵的部分。
4. 专名变量（`LLM_*` 式）与通用名（`OPENAI_*`）分离；通用名在任何宿主环境都视为不可信。

---

## 6. 测试规范落地

### 6.1 四层目录职责（agents.md §3；本次核实现有布局）
```
tests/
├── unit/          # 原子逻辑：DB CRUD、文本清洗、适配器单测（mock HTTP）
├── integration/   # 跨模块 API/流水线（TestClient + mock OCR）
├── security/      # 路径穿越、SQL 注入、zip-slip、SSRF 白名单
├── system/        # 真实环境（真实 API，串行跑，可标记可选）
└── ocr_lab/       # 调试脚本（debug_ocr.py；不以 test_ 开头，不进收集）
```
收集器 `tests/run_all_tests.py`：:69-72 递归收集 `tests/**/test_*.py`；:75-76 与 :106-112 把 `test_real_world.py` 摘出串行跑；:86 进程池 `cpu_count()+2` 并行；:49-58 结束清理 `test_db_*`/`test_workspace_*`/`test_audit_*`/`test_ws_api_*` 残留。入口 `scripts/run_tests.bat` → `python_embed/python.exe tests/run_all_tests.py`。

### 6.2 必须模仿的现有写法（已读原文）
1. **动态 backend 路径发现**（tests/unit/test_database.py:9-16；tests/integration/test_api_upload_flow.py:18-25 同款）：
```python
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current: break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)
```
新测试文件必须自带这段，不允许相对路径写死。
2. **UUID 隔离**：
   - DB：`self.db_path = f"test_db_{uuid.uuid4().hex}.db"`（test_database.py:22）；tearDown 连 `-wal`/`-shm` 一起删（:26-34）。
   - workspace：`test_ws = ...f"test_ws_api_{uuid.uuid4().hex}"`（test_api_upload_flow.py:10-12），导入 server 前注入 `sys.argv = [sys.argv[0], "38392", test_ws]`（:15）。
3. **异步任务等待**：mock 后台任务用轮询 helper，不用定长 sleep（test_api_upload_flow.py:45-51 `_wait_for_call`）。

### 6.3 并行安全禁忌（新测试硬红线）
- ❌ 固定路径：禁写 `library.db`、`workspace_default`、`./tmp` 等共享路径；临时物一律带 UUID。
- ❌ 固定端口：禁 `uvicorn.run` 或 bind 真实 socket（test_api_upload_flow.py:15 的 "38392" 只是 argv 占位，TestClient 不起真实端口——后来者不要"完善"成真起服务）。
- ❌ 跨测试共享模块级可变状态（如往 `key_manager` 注册真实 key）。
- ✅ 真实网络用例只进 `tests/system/` 且保持串行；mock 不了的失败分支（CrossRef 404/超时）在 unit 层 mock urllib 覆盖。
- ✅ know 测试移植（Phase 2，84 个）必须改路径发现逻辑符合 §6.2，并含 CJK 2 字符查询用例（总方案 §4 Phase 2 验收项）。

### 6.4 各阶段新增测试清单（与总方案 §6 对应）
| 阶段 | 文件 | 要点 |
|---|---|---|
| 0 | unit/test_tex_service.py；integration/test_tex_upload_flow.py；security/test_final_audit.py 追加 | 循环 `\input`、缺文件、编码；上传→轮询→断言含 `#` 标题；**zip-slip**（`../` 条目必须拒绝） |
| 1 | unit/test_doi_service.py；unit/test_database.py 追加迁移；system/ 可选真实用例 | mock urllib 的 404/超时/白名单外域名分支；§4.3 迁移单测 |
| 2 | unit/test_know_*.py（移植 84）；integration/test_knowledge_api.py | CJK 2 字符查询不返空；cite:// 锚点可解析 |
| 3 | unit/test_extraction_dimensions.py；integration/test_export.py | 维度 CRUD；导出 CSV/Markdown |

---

## 7. 分支与合并策略

1. **命名**：`feature/tex-ingest`、`feature/doi-verify`、`feature/knowledge-layer`、`feature/extraction-framework`（同总方案 §4）；修复用 `fix/<简述>`。
2. **main 保护**（agents.md §1）：禁止直接提交 main，一律 feature 分支开发。
3. **合并门槛**：`scripts/run_tests.bat` 全绿（TSC Lint + Vitest + 全部 Python 层）+ §8 文档清单已更新。任一红即不合。
4. **独立可回滚**：每阶段的 vendor、DB 迁移（只加列）、前端按钮均为加法；回退 = revert 该阶段一次 merge。禁止跨阶段合并成一次。
5. **提交粒度**：vendor 拷贝单独一个 commit（便于按 VENDOR.md 溯源）；适配器、路由、前端、测试各自独立 commit。

---

## 8. 文档更新清单

| 文件 | 何时 | 更新什么 |
|---|---|---|
| README.md §项目结构（:82-116） | 每阶段 | Phase 0/1/2：`backend/vendor/`（:95 占位已存在）补实际子项 tex2txt/pdf_doi_toolkit/know；`backend/services/` 补 tex_service.py/doi_service.py/knowledge_service.py；`tests/` 补新增文件；§配置说明补 `CROSSREF_MAILTO` |
| agents.md | Phase 0 之前（§10 步骤 1） | §5 增补：vendor/ 禁改与升级规则、§5.3 代理陷阱四条、DB 只加列迁移规则；§3 补"ocr_lab 不进测试收集" |
| backend/vendor/VENDOR.md | 每阶段 | §3.2 来源登记表 |
| plans/integrate-paper-tools.md | 不回流 | 总方案保持权威；本文与其冲突时以总方案为准并修本文 |

---

## 9. 跨阶段风险总表（Phase 0-3 共享）

| # | 风险 | 影响阶段 | 概率 | 对策 | 依据 |
|---|---|---|---|---|---|
| R1 | vendor 漂移：paper-tools 继续演进，副本过期或分叉 | 0/1/2 | 高 | VENDOR.md 记 commit；升级=整包替换+全测试；禁 vendor 内打补丁 | §3.2；HEAD 176ac7b |
| R2 | python_embed 缺依赖 | 0/1/2 | 中（Phase 2 起） | Phase 0/1 零依赖；know 依赖 pyyaml 6.0.3 实测在位；无 pip/uv **无法补救**——"顺带 vendor 带依赖的包"请求先查 site-packages（已实测无 bs4/ebooklib/html2text） | §3.1 |
| R3 | DB 双存储不一致：library.db.documents.doi 与 knowledge/index.sqlite.papers.doi 各写各的 | 2 | 中 | 单一写入方 = knowledge_service；library.db 只存展示值；ingest 时以 documents 为源拉齐 | 总方案 §4 Phase 2 |
| R4 | CrossRef 网络失败/被墙/超时 | 1 | 中 | 白名单 + timeout + 1 次重试 + 离线降级 unverified；system 用例标可选 | §5 |
| R5 | zip-slip（arXiv 源码包解压） | 0 | 中 | realpath 前缀校验 + security 测试专项 | 总方案 §5 |
| R6 | FTS5 对 2 字符 CJK 返空 | 2 | 高（已实测存在） | know 内置 LIKE 兜底；作为 Phase 2 验收门槛，未过不上线 | master-plan:53,214-219 |
| R7 | OCR 锚点漂移导致 claim 失联 | 2 | 低-中 | 实测漂移 <5%；sha1-8 主锚 + difflib 回退 + heading_path 上下文 | master-plan:77-91 |
| R8 | paper-prep 式全局 SSL 补丁被无意带入 | 0/1/2 | 低 | vendor 前 diff 检查 `ssl._create_unverified`；纳入 code review 清单 | §2.1、§5.1 |
| R9 | 适配器超 200 行膨胀 | 0/1/2 | 中 | 每阶段 review 行数；超限拆模块（适配器只做协议转换） | agents.md §5 |

---

## 10. 共享基础设施的实施顺序

**Phase 0 之前（一次性；可独立 commit 或并入 feature/tex-ingest 首个 commit）**：
1. agents.md 增补 §8 表所列三条规则（vendor/、代理陷阱、DB 迁移）。
2. 建 `backend/vendor/` 目录 + `VENDOR.md` 表头（包/来源路径/commit/日期/备注五列）。
3. README.md §项目结构确认 vendor/ 占位（:95 已在，无需改）。

**Phase 0 之中**：
4. 按 §3.1-3.3 拷 tex2txt（8 个 .py；删 __pycache__；不带 pyproject）→ 登记 VENDOR.md → 写 tex_service.py（≤200 行）。
5. §4.2 `_ensure_columns` 骨架：Phase 0 或 Phase 1 首次用列时落地，二选一，**不在两阶段之间半吊子**。
6. 按 §6.2/6.3 写新测试（UUID 隔离 + 动态路径发现 + zip-slip）。

**Phase 1 之中**：
7. 拷 pdf_doi_toolkit（10 个 .py）并登记；doi_service.py 落地 §5.2 骨架；`documents` 加 doi/bibtex/doi_source 列 + §4.3 迁移单测；前端按钮走 `src/api/client.ts`（agents.md §5）。

**Phase 2 之中**：
8. 拷 know（5 个 .py）并登记；knowledge_service.py；移植 84 个 know 测试（改路径发现）；`{workspace}/knowledge/index.sqlite` 独立库 + R3 一致性约定写进 knowledge_service docstring。

**Phase 3 之中**：
9. 无 vendor；按 R9 控制适配器行数；收尾时全量过 §8 文档清单 + §9 风险表逐项销项。

**每阶段合并前**：`scripts/run_tests.bat` 全绿 → 按 §8 更新文档 → 合 main → 打 tag（如 `phase0-tex-ingest`）作为回滚锚点。
