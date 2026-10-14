# Vendor 源码登记表

第三方源码逐字拷贝自 `C:/Users/VerNe/Downloads/Documents/paper-tools`（用户本人仓库，无显式 license 声明；对外公开发布前需补充）。
**规则：`backend/vendor/` 只进不出，一个字节都不改；升级 = 整包替换 + 更新本表 + 跑全部测试。**

| 包 | 来源路径 | 来源 commit | 日期 | 备注 |
|---|---|---|---|---|
| tex2txt | paper-tools/tex2txt/src/tex2txt/ | 176ac7b1ec7ddc52cc05ada7a84b08c072bb6339 | 2026-10-14 | Phase 0；拷贝 5 个库模块（__init__/processor/resolver/transforms/environment），排除 cli.py/gui.py/__main__.py（`__main__.py` import 即执行 CLI）；源仓库工作区有未提交改动（DeepSeek-OCR/uv.lock、scihub/uv.lock、know/uv.lock），但均不影响本包 .py 文件，磁盘状态即 commit 状态 |
| pdf_doi_toolkit | paper-tools/pdf-doi-toolkit/pdf_doi_toolkit/ | 176ac7b1ec7ddc52cc05ada7a84b08c072bb6339 | 2026-10-14 | Phase 1；拷贝 11 个库模块（__init__/cache/config/crossref/fuzzy/matcher/scanner/sciencedirect/title_extractor/utils/xmol），排除 CLI 入口 main.py；磁盘状态即 commit 状态（同上次登记说明） |
| know | paper-tools/know/ | 176ac7b1ec7ddc52cc05ada7a84b08c072bb6339 | 2026-10-14 | Phase 2；拷贝 5 个库模块（know/anchors/derive/identity/config），排除 CLI 相关 pyproject.toml/uv.lock/tests/；零第三方依赖（仅 stdlib）。fixtures（10 文件）另存 tests/unit/fixtures/know/（测试资产，非 vendor）。sha256 基线见 tests/unit/test_vendor_know_integrity.py |
