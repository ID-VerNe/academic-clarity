# Academic Clarity — UX 审计报告

| 项目 | 内容 |
|---|---|
| 审计对象 | Academic Clarity 桌面应用（Electron + React 19 + Vite；后端 FastAPI） |
| 审计范围 | `src/` 全部 21 个 UI 组件、`electron/main.ts`、`index.html`、`src/index.css` 及关键交互链路 |
| 审计日期 | 2026-10-15 |
| 审计方法 | 启发式评估（Heuristic Evaluation）：完整源码静态走查；所有结论附 `文件:行号`，可复现 |
| 审计框架 | Krug《Don't Make Me Think》三定律 + Trunk Test；Nielsen 10 项可用性启发式；0–4 严重度分级 |
| **总分** | **3 / 10**（3–5 档：存在灾难级问题且快速诊断大面积未通过） |

> 方法说明：本报告基于代码快照的静态审计，未运行实机。标注「建议实机复核」的条目（UX-01 / 03 / 07 / 08）属高影响结论，建议实机验证后进入修复排期。

---

## 0. 执行摘要

### 0.1 一句话结论

**核心链路（导入 → OCR → 阅读 → 对话）可以跑通，基础信息架构清晰；但「死控件、静默失败、反馈缺失、语言术语混乱」四类问题系统性地侵蚀信任，其中阅读器全局禁用文本选择直接阻断了学术工具最核心的复制引用工作流。**

### 0.2 问题统计

| 严重度 | 数量 | 说明 |
|---|---|---|
| 4 灾难级 | 1 | 阻断核心任务完成 |
| 3 重大级 | 7 | 显著任务失败 / 信任受损 |
| 2 次要级 | 31 | 造成延误或挫败 |
| 1 修饰级 | 10 | 低影响，顺手可修 |
| **合计** | **49** | |

### 0.3 Top 8 问题速览

| # | ID | 问题 | 严重度 | 位置 |
|---|---|---|---|---|
| 1 | UX-01 | Reader 根容器 `select-none`，全阅读器无法选中/复制文本 | 4 | `Reader.tsx:128` |
| 2 | UX-02 | Header 全局搜索框是死控件，输入无任何响应 | 3 | `Header.tsx:36-43` |
| 3 | UX-03 | Dashboard「Sync」点击后列表不刷新，静默无效 | 3 | `Dashboard.tsx:77-84` |
| 4 | UX-04 | 死控件群：Bell / Eye / Bookmark / AI Analyze 均无 handler | 3 | 多处 |
| 5 | UX-05 | 左栏「Structure」是硬编码假导航，点击无反应 | 3 | `Reader.tsx:144-162` |
| 6 | UX-06 | 全应用静默失败：上传/同步/删除/保存错误只进 console | 3 | `App.tsx:28-115` |
| 7 | UX-07 | 聊天消息换行折叠，LLM 长回答变「文字墙」 | 3 | `ChatSidebar.tsx:166-176` |
| 8 | UX-08 | 多 Key 编辑流陷阱：现有 Key 显示 "not set" 且保存必失败 | 3 | `SettingsModal.tsx:193-211` |

### 0.4 做得好的地方（保留并强化）

- 状态视觉体系：颜色 + 边框 + 顶部动效条 + 图例，一眼可辨文档处理状态。
- 「Active Processing Pipeline」处理中面板 2s 轮询，长任务有基本可见性。
- PDF 加载/失败/重试三态齐全；Settings 表单内联校验（红框 + 具体文案）符合 Nielsen #9。
- 三栏可拖拽布局、分栏比例可调，专业工具感强。
- DOI 验证、BibTeX 复制有即时状态反馈（徽章 / "BibTeX copied"）。
- 侧栏开关、发送、Quote 开关、维度行操作等已有 `aria-label` 覆盖。
- JSON 递归渲染有深度限制（max 5），符合项目规范。

### 0.5 距离 10/10 的路径（修复清单）

1. 移除 Reader `select-none`，恢复文本选择与复制（UX-01）
2. 接通或移除全部死控件：Header 搜索、Bell、Eye、Bookmark、AI Analyze、Structure 导航（UX-02/04/05）
3. Sync 后刷新文档列表 + 引入全局 toast 反馈体系（UX-03/06）
4. 修复聊天渲染：换行保留、IME 回车、自动滚动（UX-07/17/20）
5. 统一语言（中文）与术语（UX-09/10）
6. 修复多 Key 编辑流（UX-08）
7. PDF 本地 worker + 基础阅读控制（UX-23/24）
8. 首启引导：未配置 Key 时的空库引导（UX-32）

---

## 1. 评分方法与快速诊断结果

### 1.1 快速诊断（Quick Diagnostic）

| # | 问题 | 通过？ | 触发的最高严重度 | 说明 |
|---|---|---|---|---|
| 1 | 能否立刻说出这是哪个应用/页面？ | ✓ | — | Logo + 页面标题清晰（但窗口标题错误，见 UX-34） |
| 2 | 主操作是否明显？ | ✗ | 3 | Reader 主 CTA「AI Analyze」是死控件；卡片操作 hover 才可见 |
| 3 | 导航是否清晰？ | ✗ | 3 | Structure 假导航；三处名称指同一页（Library/Dashboard/Research Library） |
| 4 | 能否找到搜索？ | ✗ | 3 | Header 搜索是死的；Reader 页内无搜索 |
| 5 | 系统是否展示正在发生什么？ | ✗ | 3 | 同步不刷新、无 toast、假「Core Active」、假「Synthesizing...」 |
| 6 | 错误信息是否有帮助？ | ✗ | 3 | 错误只进 console；聊天错误无指引；claims 错误渲染成「无结果」 |
| 7 | 能否撤销或返回？ | ✗ | 2 | 无撤销；原生 confirm；提取任务无取消 |
| 8 | 不用 hover 是否可用？ | ✗ | 2 | 卡片操作 hover-only；图标按钮仅靠 title 提示 |
| 9 | 交互元素是否都有标签？ | ✗ | 2 | Bell / Eye / Bookmark / Sync 等无 aria-label |
| 10 | 是否有让人停下来「嗯？」的地方？ | ✗ | 4 | `select-none`、假导航、死按钮、中英混杂 |

### 1.2 评分推导

- 10 行诊断 **9 行未通过**，含 1 个灾难级（#10）与多个重大级（#2/3/4/5/6）。
- 按扣分法：`10 − Σ(行权重)` 将落入 ≤2 档；考虑核心链路（导入→OCR→阅读→对话）实际可跑通、基础视觉体系良好，**取 3–5 档上界，即 3/10**。
- 修复 P0 + P1 后复测，预期可回到 6–8 档。

---

## 2. 灾难级与重大级问题详述（S4 / S3）

### UX-01【S4】Reader 全局禁用文本选择，复制被阻断

- **现象**：`Reader.tsx:128` 根容器使用 `select-none`；全项目无任何 `select-text` 覆盖（已 grep 验证）。Markdown 正文、PDF 文本层、聊天消息全部无法选中。
- **矛盾证据**：同文件 `:205` 的 Markdown 容器带 `selection:bg-indigo-100`，说明作者本意是允许选择的——这是 bug 而非设计。
- **影响**：学术工具最核心工作流（复制引文、摘录、比对）完全不可用；配合引用模式（Quote Mode）与知识库功能形成逻辑闭环断裂。
- **启发式**：用户控制与自由（Nielsen #3）；认知（Krug #1）。
- **修复**：删除根容器 `select-none`；对拖拽区域（侧栏手柄、工具栏按钮）单独加 `select-none`；实机复核。

### UX-02【S3】Header 全局搜索是死控件

- **现象**：`Header.tsx:36-43` 的 "Search library..." 输入框无 `value`、无 `onChange`、无 `onKeyDown`——输入任何内容都无响应。
- **影响**：违反「可见性」与「诚实」原则；用户在 Reader 页唯一的搜索入口是假的，会直接得出结论「这应用搜不了」。
- **修复**：二选一——接入真实搜索（跳到 Dashboard 并注入 query），或移除该输入框，避免重复入口（Dashboard 已有可用搜索）。

### UX-03【S3】Dashboard「Sync」点击后列表不刷新

- **现象**：`Dashboard.tsx:77-84` 的 `handleSync` 只调 `api.syncWorkspace()`，不触发 `App` 层的 `refreshTrigger`；`App.tsx:69-75` 的轮询仅在存在 processing/pending 文档时激活。同步发现的新文件不会出现在列表里。
- **对比**：同页 `onReprocess`（`App.tsx:99-106`）会正确刷新——行为不一致加剧困惑。
- **影响**：用户点同步 → 图标转一圈 → 列表无变化 → 反复点击或认为功能坏了。
- **修复**：同步成功后调用上层刷新（提升 `handleSync` 到 App 或传入 `onRefresh` 回调）；完成后给出 toast「已同步，发现 N 个新文件」。

### UX-04【S3】死控件群：Bell / Eye / Bookmark / AI Analyze

| 控件 | 位置 | 现象 |
|---|---|---|
| 通知铃铛 | `Header.tsx:44-46` | 无 `onClick` |
| 卡片预览 Eye | `Dashboard.tsx:530-532` | 无 `onClick`（整卡可点击，此按钮纯装饰） |
| 书签 Bookmark | `ReaderToolbar.tsx:57-59` | 无 `onClick` |
| AI Analyze | `ReaderToolbar.tsx:63-66` | 无 `onClick`，且是全屏最显眼的靛蓝主 CTA |

- **影响**：主 CTA 失效最伤——用户点击「AI Analyze」毫无反应，会对整个应用失去信心（Krug 善意蓄水池快速流失）。
- **修复**：未实现的先隐藏或置 `disabled` + 「即将推出」提示；AI Analyze 可先接线到右侧聊天（聚焦输入框）。

### UX-05【S3】左栏「Structure」是硬编码假导航

- **现象**：`Reader.tsx:144-162` 的 Abstract / 1. Introduction / 2. Methodology / 3. Analysis / References 为写死文案，无 `onClick`、不随文档变化、且「Abstract」恒为高亮态。
- **影响**：出现在读者注意力最强的左侧栏，承诺「文档结构导航」却不兑现；与真实文档内容无关，误导性极强。
- **修复**：短期——从 `doc.ocr_structured_json.blocks` 动态生成标题树并滚动定位；或先折叠/移除该栏，不要展示假数据。

### UX-06【S3】全应用静默失败，无用户级反馈

- **现象**：`App.tsx:28-30/38-40/82-84/94-96/112-114`、`Dashboard.tsx:69/82/95/113` 等全部 `catch` 只 `console.error`。上传失败、删除失败、同步失败、配置保存失败在 UI 上完全不可见。
- **影响**：用户不知道操作是否成功，只能盲目重试；失败与「没反应」无法区分，直接摧毁信任（Nielsen #1/#9）。
- **修复**：引入全局 toast 组件（成功/失败/进行中）；所有 catch 至少给出一句用户可读的错误 + 下一步建议。

### UX-07【S3】聊天消息换行被折叠

- **现象**：`ChatSidebar.tsx:166-176` 消息气泡直接渲染 `{msg.content}`，无 `whitespace-pre-wrap`（已 grep 验证全项目无此样式）。LLM 输出的多段回答、列表、公式块全部塌缩成一段。
- **影响**：核心功能可读性严重下降，AI 回答越长越难读。
- **修复**：气泡容器加 `whitespace-pre-wrap`（或渲染 Markdown）；建议实机复核。

### UX-08【S3】多 Key 编辑流陷阱

- **现象**：`SettingsModal.tsx:193-211` `loadKeysToEdit` 把已有 Key 的 `api_key` 一律置空；`:253` 渲染为 "not set"；而 `:71-73` 校验要求 `api_key` 必填。
- **后果链**：点「Add Key」→ 全部现有 Key 变成空密钥表单 → 「Save Keys」校验失败（"API Key is required"）→ 用户被迫重输所有密钥，或困惑放弃。
- **附带**：`:202` 把 `is_healthy`（健康状态）映射到 `enabled`（启用开关），语义混用；不健康的 Key 会被静默呈现为「禁用」。
- **修复**：区分「新增」与「编辑」模式；编辑模式回填脱敏占位符，后端按「空 = 不修改」处理；`enabled` 独立于健康度展示。

---

## 3. 逐屏审计

### 3.1 全局框架（App / Header / Footer / Electron）

| ID | 严重度 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| UX-09 | 2 | 语言混杂：同一界面中英夹杂（如「验证 DOI」「复制 BibTeX」「已摄入 N 篇文档」 vs 全英文界面） | `Dashboard.tsx:379,428-431`；`MetadataPanel.tsx:178,185`；`DimensionManager.tsx:52,64,75,118-119`；`Reader.tsx:108` | 目标用户为中文研究者，建议统一中文（或完整 i18n），UI 文案集中管理 |
| UX-10 | 2 | 术语不一致：同一页面四种叫法（Library / Dashboard / Research Library / Intelligence Dashboard）；状态「OCR Only」vs 徽章「OCR READY」 | `ReaderToolbar.tsx:26`；`Dashboard.tsx:182,348,363,488` | 定一份术语表：如「文献库」+「状态：完成 / 仅OCR / 处理中 / 失败」 |
| UX-15 | 2 | 删除用原生 `confirm()`，英文文案，无撤销 | `App.tsx:89-97`（英文）vs `DimensionManager.tsx:59`（中文） | 应用内确认弹窗 + 删除后 Undo toast；两处语言统一 |
| UX-32 | 2 | 无首启引导：未配置 API Key 时导入 PDF 必然失败，但界面不提示去哪配置 | 全局 | 首启空库展示 3 步引导（选工作区 → 配置 Key → 导入）；失败卡片给「去设置」按钮 |
| UX-38 | 2 | 无 Error Boundary，组件异常即白屏 | `App.tsx` 顶层 | 加 ErrorBoundary + 兜底 UI（重启/返回） |
| UX-39 | 2 | 上传中按钮无 disabled 视觉（仅 `!isUploading &&` 判断）；失败静默 | `Dashboard.tsx:201-207`；`App.tsx:77-87` | 上传中置灰 + 进度；失败 toast |
| UX-37 | 2 | 图标按钮缺 `aria-label`/title：Bell、Eye、Bookmark、Sync、Switch Workspace | `Header.tsx:44`；`Dashboard.tsx:185,192,530` | 补齐 aria-label 与 title |
| UX-28 | 2 | 8–10px 极小字号大量用于关键信息（状态徽章、日期、图例、章节标签） | 全项目（`text-[8px]`~`text-[10px]` 40+ 处） | 关键信息 ≥ 12px；仅装饰性文字可保留小字号 |
| UX-34 | 2 | 窗口/任务栏标题仍是模板默认值 "My Google AI Studio App" | `index.html:6` | 改为 "Academic Clarity" |
| UX-36 | 2 | 页脚「Core Active」绿灯硬编码，后端挂了也显示正常 | `Dashboard.tsx:549-558` | 接线真实健康检查（如 `/health`），或移除 |
| UX-40 | 1 | Inter 字体 import 被注释，字体栈回退系统字体 | `index.css:1` | 恢复字体加载或移除声明 |
| UX-45 | 1 | 头像「AC」无功能无意义 | `Header.tsx:54-56` | 移除或改为版本号入口 |
| UX-48 | 1 | 副标题营销语 "Unified view of your research intelligence..." | `Dashboard.tsx:198` | 精简或删除（Krug 第三定律） |

### 3.2 Dashboard

| ID | 严重度 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| UX-03 | 3 | Sync 不刷新列表 | `Dashboard.tsx:77-84` | 见上文详述 |
| UX-04 | 3 | Eye 按钮死控件 | `Dashboard.tsx:530-532` | 接通或移除 |
| UX-11 | 2 | 状态图例与真实状态不一致：processing 是靛蓝但图例只有绿/黄/红；「OCR Only」对应徽章「OCR READY」；Pending 与 Fail 合并 | `Dashboard.tsx:358-368` vs `479-489` | 图例补全四态并统一文案 |
| UX-12 | 2 | 空库状态文案错误：无筛选时也显示 "No intelligence matches your current filter."，且无导入引导 | `Dashboard.tsx:443-457` | 区分「空库」（引导导入）与「筛选无结果」（给重置按钮） |
| UX-13 | 2 | 搜索 placeholder 承诺 "or insights" 但仅匹配 title/authors | `Dashboard.tsx:225` vs `140-141` | 兑现承诺（检索 insight 字段）或改文案 |
| UX-14 | 2 | "Acquired" 字段混用出版日期（insight.date）与导入时间（added_at），语义不明 | `Dashboard.tsx:524-527` | 拆为 "Published" / "Added" 两行或二选一 |
| UX-16 | 2 | claims 检索失败被渲染成「无结果」（catch 里 `setClaimsResults([])` + `setClaimsSearched(true)`） | `Dashboard.tsx:94-97` | 区分错误态与空态，错误时给重试按钮 |
| UX-26 | 2 | 处理中面板无阶段（OCR/洞察/知识摄入）、无进度、无取消 | `Dashboard.tsx:305-338` | 每任务显示当前阶段 + 预计等待；提供取消 |
| UX-27 | 2 | 卡片操作 hover 才可见（`opacity-0 group-hover:opacity-100`） | `Dashboard.tsx:530-539` | 常显或收入「⋯」菜单；键盘/触屏可用 |
| UX-35 | 2 | 无排序、无分页/虚拟化、无拖拽上传 | `Dashboard.tsx` | 加排序（时间/标题）+ 拖拽导入；大库考虑虚拟滚动 |
| UX-17 | 2 | 搜索框 Enter 未检查 IME 组合态，中文输入法选词回车会误触发 | `Dashboard.tsx:285` | 加 `!e.nativeEvent.isComposing` 判断 |
| UX-44 | 1 | 页脚 "N Visible Intelligence" 在 claims 模式口径混乱（显示论文数而非 claim 数） | `Dashboard.tsx:556` | 按模式显示对应计数 |

### 3.3 Reader（结构 / 工具栏 / PDF / Markdown / 聊天 / 元数据）

| ID | 严重度 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| UX-01 | 4 | `select-none` 阻断全阅读器文本选择 | `Reader.tsx:128` | 见上文详述 |
| UX-05 | 3 | Structure 假导航 | `Reader.tsx:144-162` | 见上文详述 |
| UX-04 | 3 | Bookmark / AI Analyze 死控件 | `ReaderToolbar.tsx:57-66` | 见上文详述 |
| UX-07 | 3 | 聊天换行折叠 | `ChatSidebar.tsx:166-176` | 见上文详述 |
| UX-17 | 2 | 聊天输入 Enter 未处理 IME 组合态 | `ChatSidebar.tsx:206` | 同 Dashboard 修复 |
| UX-18 | 2 | 聊天错误文案无行动指引（"Error: Connection failed."），无重试 | `Reader.tsx:118-121` | 改为「连接失败，请检查后端服务后重试」+ 重试按钮 |
| UX-19 | 2 | 对话不持久：返回 Dashboard 即丢失；无「清空/新对话」 | `Reader.tsx:34-35` | 会话按 doc 持久化（localStorage/DB）；加清空按钮 |
| UX-20 | 2 | 新消息无自动滚动，回复出现在视野外 | `ChatSidebar.tsx:159-187` | 消息更新后 `scrollIntoView` |
| UX-21 | 2 | Quote Mode 开关语义不清：无解释文案、title 为中文、后果（全文 vs 引文）不直观 | `ChatSidebar.tsx:190-201` | 开关旁加一行说明；首次开启时解释 |
| UX-22 | 2 | 空闲时显示 "Synthesizing..." 空态，误导为进行中 | `ChatSidebar.tsx:149-154` | 改为「暂无洞察，点击 + 提取」 |
| UX-23 | 2 | PDF 无缩放/页码/跳页/页内查找；阅读位置不保存 | `PdfViewer.tsx` | 至少加缩放 + 页码指示；记录上次阅读页 |
| UX-24 | 2 | PDF.js worker 走 unpkg CDN，离线/内网不可用 | `PdfViewer.tsx:8` | worker 打包进本地资源 |
| UX-25 | 2 | Markdown 空态指引 "initialize DeepSeek-OCR" 无操作入口 | `MarkdownViewer.tsx:44-56` | 附「去设置配置」按钮 / 「重新处理」按钮 |
| UX-47 | 1 | "Streaming PDF Bytes..." / "Rendering high-fidelity pages..." 开发者文案 | `PdfViewer.tsx:84,98` | 改为「正在加载 PDF…」 |
| UX-43 | 1 | 安全横幅 "Standard sanitization applied" 面向开发者而非用户 | `MarkdownViewer.tsx:67-72` | 移除或改为用户可理解的提示 |
| UX-41 | 1 | 左右侧栏折叠箭头语义相反（左栏展开时 rotate-180，右栏收起时 rotate-180） | `Reader.tsx:141` vs `ChatSidebar.tsx:91` | 统一箭头方向语义 |
| UX-42 | 1 | 拖拽手柄默认不可见、无键盘支持、无双击复位 | `Reader.tsx:164-171,193-200` | 常显细线 + hover 加粗；双击复位 50% |
| UX-46 | 1 | 元数据与聊天两个滚动区嵌套，滚轮易迷失 | `ChatSidebar.tsx:114` | 改为标签页或可折叠单区 |
| — | 2 | （产品缺口）无划词引用/复制引文能力，与 Quote Mode、知识库叙事脱节 | 全局 | 选择文本 → 浮动「引用/复制」工具条 |

### 3.4 Settings（Basic / OCR Keys / LLM Keys / Dimensions）

| ID | 严重度 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| UX-08 | 3 | 多 Key 编辑流陷阱 | `SettingsModal.tsx:193-211` | 见上文详述 |
| UX-29 | 2 | Basic tab 失焦即静默保存：无「已保存」反馈；误清空字段会静默清掉密钥 | `SettingsModal.tsx:486-503` | 显式保存按钮 + 保存反馈；空值二次确认 |
| UX-30 | 2 | `enabled` 与 `is_healthy` 语义混用 | `SettingsModal.tsx:202` | 拆分展示：启用开关 / 健康徽章 |
| UX-31 | 2 | 关闭弹窗丢失未保存编辑、无提醒；无 ESC 关闭、无焦点圈定 | `SettingsModal.tsx:423-456` | ESC 关闭 + 焦点陷阱 + 未保存提醒 |
| UX-33 | 2 | 「New Dimension」（Settings，仅定义）与「New Intelligence Dimension」（聊天栏，立即执行提取）同名不同义 | `DimensionManager.tsx:113` vs `ChatSidebar.tsx:96-103,122` | 重命名区分：如「管理维度」/「立即提取」 |
| UX-49 | 1 | 维度行 5 个操作全图标 + tooltip，导出无成功反馈 | `DimensionManager.tsx:199-241` | 保留常用 2 个常显，其余收菜单；导出加 toast |
| UX-09 | 2 | 维度管理文案中文、Settings 其余英文 | `DimensionManager.tsx:52,118-119` | 同 UX-09 统一 |

---

## 4. Trunk Test（随机落点定位测试）

| 问题 | 能回答？ | 依据 |
|---|---|---|
| 这是什么网站/应用？ | ✓ | Logo "Academic Clarity"（窗口标题错误，见 UX-34） |
| 我在哪个页面？ | ✓ | Dashboard 标题 / Reader「Active Document」+ 文档名 |
| 主要板块有哪些？ | ✗ | Header 无导航；Reader 内 Structure 是假导航（UX-05） |
| 本页有哪些操作？ | ✗ | Reader 最显眼 CTA「AI Analyze」是死的（UX-04） |
| 我在层级中的位置？ | ✓ | Reader 有「← Library」返回 + 标题 |
| 如何搜索？ | ✗ | Header 搜索是死的；Reader 页内无搜索（UX-02） |

结论：6 项中 3 项失败，其中 2 项直接由死控件造成。

---

## 5. 核心任务走查（Task-Based Walkthrough）

### 任务 A：导入一篇 PDF 并完成处理

| 步骤 | 预期 | 实际 | 问题 |
|---|---|---|---|
| 1. 打开应用 | 显示同步中状态 | 静默后台同步 | UX-32 |
| 2. 点「Import PDF / LaTeX」上传 | 有进度、失败有提示 | 仅按钮转圈；失败静默 | UX-39/06 |
| 3. 等待 OCR | 可见阶段与进度 | 「AI is digesting content...」无细节 | UX-26 |
| 4. 完成后预览卡片 | 点 Eye 快速预览 | Eye 无反应 | UX-04 |

### 任务 B：阅读并提问

| 步骤 | 预期 | 实际 | 问题 |
|---|---|---|---|
| 1. 打开文档 | 分栏阅读 | ✓ 正常 | — |
| 2. 复制一段正文 | 可选中、可复制 | 无法选中任何文本 | UX-01 |
| 3. 用左栏跳转章节 | 滚动到对应章节 | 点击无反应（假导航） | UX-05 |
| 4. 提问（中文输入） | 回车发送完整问题 | 输入法选词回车误发送 | UX-17 |
| 5. 阅读 AI 回答 | 多段可读 | 换行塌缩成一段 | UX-07 |
| 6. 点「AI Analyze」 | 得到分析 | 无反应 | UX-04 |

### 任务 C：建立知识库并检索

| 步骤 | 预期 | 实际 | 问题 |
|---|---|---|---|
| 1. 切到 Knowledge Claims | 说明与入口 | ✓（中文文案但可用） | UX-09 |
| 2. 摄入文档 | 有进度反馈 | 按钮转圈，无进度 | UX-26 |
| 3. 搜索 | 结果或明确错误 | 后端失败时显示「无结果」 | UX-16 |
| 4. 打开结果引用 | 复制引文 | 进入 Reader 后仍无法选中 | UX-01 |

### 任务 D：配置多 API Key

| 步骤 | 预期 | 实际 | 问题 |
|---|---|---|---|
| 1. 查看已有 Key | 显示脱敏密钥与状态 | 显示 "not set" | UX-08 |
| 2. 点「Add Key」新增 | 仅新增行可编辑 | 全部 Key 变空表单 | UX-08 |
| 3. 保存 | 成功 | 校验失败（现有 Key 必填） | UX-08 |
| 4. Basic tab 改 Key 后离开 | 明确保存状态 | 失焦静默保存、无反馈 | UX-29 |

---

## 6. 修复路线图

### P0 — 立即（本周）

| 项 | 内容 | 工作量 |
|---|---|---|
| UX-01 | 移除 `select-none`，恢复复制 | 5 分钟 |
| UX-04 | 死控件：隐藏或接通（Bell/Eye/Bookmark/AI Analyze） | 1–2 小时 |
| UX-02 | Header 搜索接线或移除 | 1 小时 |
| UX-03 | Sync 后刷新列表 | 30 分钟 |
| UX-07 | 聊天加 `whitespace-pre-wrap` | 5 分钟 |
| UX-17 | IME 回车修复（两处） | 15 分钟 |
| UX-34 | 修正窗口标题 | 1 分钟 |

### P1 — 短期（2 周内）

- UX-06：全局 toast 反馈体系（覆盖上传/删除/同步/保存/导出）
- UX-05：Structure 动态生成或移除
- UX-08：多 Key 编辑流重构（新增/编辑分离、空值=不修改）
- UX-09/10：统一语言与术语表
- UX-16/18/20：错误态与聊天体验修复
- UX-23/24：PDF 本地 worker + 缩放/页码

### P2 — 中期（1–2 个月）

- UX-32：首启引导向导
- UX-12/11/14/26：Dashboard 信息架构修正（空态、图例、日期语义、任务面板）
- UX-19/21/22：聊天会话持久化与文案重写
- UX-27/29/31：hover 可达性、设置保存模型、弹窗可访问性
- UX-35：排序、拖拽上传、虚拟滚动

### P3 — 低优先级

- UX-28：字号体系整理（关键信息 ≥12px）
- UX-40/41/42/43/44/45/46/47/48/49：修饰级问题批量清理

### Quick Wins（低投入高回报）

| 问题 | 修复 | 工作量 |
|---|---|---|
| UX-01 | 删一个 class | 5 分钟 |
| UX-07 | 加一个 class | 5 分钟 |
| UX-34 | 改一行标题 | 1 分钟 |
| UX-17 | 加 isComposing 判断 | 15 分钟 |
| UX-03 | 同步后调 onRefresh | 30 分钟 |
| UX-22 | 改一句空态文案 | 5 分钟 |

---

## 7. 复测建议

1. 完成 P0 后按第 1.1 节诊断表复测（预期 9✗ → 4✗ 以内）。
2. 建议按 Krug $0 可用性测试协议，找 3 名目标用户（研究生）各跑一遍任务 A–D，观察卡点是否与本文一致。
3. 高影响结论（UX-01/03/07/08）先做实机复核再关闭。

---

## 8. 修复记录（2026-10-15）

> 本报告 49 项问题已**全部修复**；同时按需求彻底移除了应用内的「多 Key 轮询方案」（轮询职责移交外部本地代理）。

### 8.1 验证结果（全量门禁）

| 门禁 | 命令 | 结果 |
|---|---|---|
| 前端 UI 测试 | `pnpm test`（Vitest） | **9 文件 / 91 用例 全通过** |
| 前端类型检查 | `pnpm lint`（tsc --noEmit） | **0 错误** |
| 后端 + 集成 + 安全 + 系统 | `scripts/run_tests.bat` | **34 / 34 任务通过**（420s） |

### 8.2 关键修复对照

| 编号 | 问题 | 修复落点 |
|---|---|---|
| UX-01 | `select-none` 阻断复制 | `Reader.tsx` 根容器移除，仅工具栏/目录/手柄局部保留 |
| UX-02 | Header 搜索死控件 | `searchQuery` 提升为全局受控，覆盖标题/文件名/作者/期刊/年份/洞察 |
| UX-03 | Sync 不刷新 | `App.tsx` `handleSync` 完成后 `fetchData`，含 `isSyncing` 状态 |
| UX-04 | 死控件群 | 删除 Bell / AC 头像 / Eye / Bookmark；AI Analyze 接线为「AI 分析」 |
| UX-05 | Structure 假导航 | `buildOutline(doc)` 由 `ocr_structured_json.blocks` / markdown 标题动态生成，可点击定位，含空态 |
| UX-06 | 全应用静默失败 | 新增 Toast 单例（`ui/Toast.tsx` + `<ToastHost/>`），上传/同步/删除/保存/导出/DOI/批量 全部接入 |
| UX-07 | 聊天换行折叠 | `whitespace-pre-wrap break-words` |
| UX-08 | 多 Key 编辑流陷阱 | **方案整体移除**（见 8.3） |
| UX-09/10 | 语言与术语混杂 | 全量中文文案；统一「文献库」等术语 |
| UX-11 | 状态图例不一致 | `STATUS_META` 五态统一图例与徽章（完成/仅 OCR/处理中/排队中/失败） |
| UX-12 | 空态文案错误 | 拆为三种真实空态：骨架屏 / 空库三步引导 / 筛选无结果 |
| UX-13 | 搜索承诺未兑现 | 检索范围扩展到洞察字段，并显式说明「检索范围」 |
| UX-14 | Acquired 语义不明 | 日期拆为「发表 / 导入」两行 |
| UX-15 | 原生 confirm | `ConfirmDialog`（`role=alertdialog`、ESC 关闭、初始焦点在「取消」） |
| UX-16 | claims 失败伪装成无结果 | 独立错误态 + 重试入口 |
| UX-17 | IME 回车误触发 | 两处 `onKeyDown` 均加 `!e.nativeEvent.isComposing` |
| UX-18 | 聊天错误无指引 | 可操作文案 + 问题回填输入框 |
| UX-19 | 对话不持久 | `localStorage` 持久化 `ac:chat:{docId}`（上限 60 条）+ 清空对话 |
| UX-20 | 无自动滚动 | `bottomRef.current?.scrollIntoView` |
| UX-21 | Quote Mode 语义不清 | 开关旁说明文案 + `aria-pressed` + 占位符切换 |
| UX-22 | 空态误导 | 改为「针对本文档提问」+ 示例问题 |
| UX-23 | PDF 无缩放/页码/位置 | 工具栏（上/下一页、跳页、缩放 50–250%、适应宽度）+ 阅读位置持久化 |
| UX-24 | worker 走 CDN | `pdfjs-dist/.../pdf.worker.min.mjs?url` 本地打包 |
| UX-25 | 空态无入口 | 「重新处理」「去设置」按钮；AI 分析展开右栏并聚焦 |
| UX-26 | 任务无阶段/进度/取消 | 后端 `progress_tracker` 阶段上报 + `/tasks` 合并 `stage/progress/elapsed` + `POST /tasks/{id}/cancel`；前端队列卡片显示阶段、进度条、已用时、取消 |
| UX-27 | 操作 hover 才可见 | 卡片操作常显 + `aria-label` |
| UX-28 | 极小字号 | 关键信息字号提升至 ≥11–12px |
| UX-29 | 失焦静默保存 | 显式「保存」按钮 + 「未保存」脏标记 + 逐字段校验 + 空值确认 |
| UX-30 | enabled/health 语义混用 | 随多 Key 移除而消失（单 Key 直呼，无健康池概念） |
| UX-31 | 弹窗丢失编辑 | ESC 关闭 + Tab 焦点圈定 + 焦点归还 + 未保存二次确认 |
| UX-32 | 无首启引导 | 空库三步引导 + 配置不完整横幅「去设置」+ `GET /configs` 返回生效值（含 `OCR_MODEL`） |
| UX-33 | 同名不同义 | 设置侧「新建维度 / 批量运行」与阅读器侧「立即提取（仅本文档）」并加差异说明 |
| UX-34 | 窗口标题模板值 | `index.html` 改为 Academic Clarity |
| UX-35 | 无排序/拖拽 | 排序（导入时间/标题/年份）+ 拖拽导入（扩展名白名单） |
| UX-36 | 页脚绿灯硬编码 | 30s 健康轮询接线真实状态，恢复后自动重取数据 |
| UX-37 | 图标按钮无标签 | 全量补齐 `aria-label` / `title` |
| UX-38 | 无 Error Boundary | `ErrorBoundary` 包裹 `<App/>`，兜底 UI 可恢复 |
| UX-39 | 上传态不明确 | 上传中禁用 + 文案「导入中…」+ 失败 toast |
| UX-40 | 字体声明悬空 | `index.css` 明确离线友好字体栈（含 CJK 回退） |
| UX-41 | 折叠箭头语义相反 | 统一为：收起 ChevronLeft / 展开 ChevronRight |
| UX-42 | 拖拽手柄不可见 | 常显细线 + hover 加粗 + `role="separator"` + 双击复位 |
| UX-43 | 开发者安全横幅 | 改为用户可读文案 + ShieldCheck |
| UX-44 | 页脚口径混乱 | 按模式显示真实计数（文献 / claims） |
| UX-45 | 无意义头像 | 移除 |
| UX-46 | 嵌套滚动区 | 改为「对话 / 洞察」双 Tab |
| UX-47 | 开发者加载文案 | 改为「正在加载 PDF…」「正在渲染页面…」「PDF 加载失败」+ 重新加载 |
| UX-48 | 营销副标题 | 移除 |
| UX-49 | 维度行图标堆叠/导出无反馈 | 常用操作常显，导出/删除收进「更多操作」菜单；全部操作接 toast |

### 8.3 多 Key 轮询方案移除清单

| 层 | 移除内容 |
|---|---|
| 后端 | `core/api_key_manager.py` 整文件；`ServiceKeyPool` / `MultiServiceKeyManager` / `KeyState` / `KeyConfig` / `KeyPoolConfig` / `_use_multi_key`；`CacheConfig.KEYPOOL_TTL` / `KeyPoolCache`；`log_key_pool()`；`api_key_usage` / `api_key_health` 指标；`EventType.KEY_POOL_UPDATE` / `send_key_pool_update()` |
| 后端（改） | `ConfigService` 单 Key 化，统一返回生效值（DB → `config.py` 默认值回退）；`ai_service` 三处调用改为单 Key 直呼 LiteLLM `completion()` |
| 前端 | Settings 的 `OCR Keys` / `LLM Keys` 两个 Tab；`getMultiKeyStats` / `updateOcrKeys` / `updateLlmKeys`；`AppConfig` 收敛为 5 字段 |
| 测试 | `test_extraction_service.py` 的池耗尽用例改为「任意 API 异常必须向上传播供队列重试」 |

### 8.4 测试基建修复（Windows 盘符大小写）

`vitest` 进程 cwd 的盘符为小写（`c:\...`）时，`node_modules` 中 pnpm 符号链接经 realpath 解析为规范大写（`C:\...`），同一份 `react.development.js` 被 ESM / CJS 两条路径各加载一次 → React 双实例，表现为 `Cannot read properties of null (reading 'useState')` / `Invalid hook call`。

修复：`vitest.config.ts` 在加载时把 cwd 盘符规范化为大写并显式设置 `test.root`（非 Windows 环境自动跳过）。修复后前端用例由 22 失败 → **91/91 全通过**。

---

*审计报告结束。第 0–7 节基于 2026-10-15 修复前代码快照；第 8 节为同日修复闭环记录。*
