"""跨测试共享夹具数据（TEX / CJK 语料）。

迁移自 tests/integration 与 tests/system 中重复的内联常量。
"""

import json

# 最小可转换 tex 文档（含 title / abstract / 两节正文）
TEX_FIXTURE = (
    "\\documentclass{article}\n"
    "\\title{Real Title}\n"
    "\\begin{document}\n"
    "\\begin{abstract}\nWe prove things.\n\\end{abstract}\n"
    "\\section{Introduction}\nThis is the introduction body.\n"
    "\\section{Method}\nWe use a method.\n"
    "\\end{document}\n"
)

# 中文旗舰语料：OCR 正文含「交易」段 + 对应 Basic Insight（LLM 转述）
CJK_OCR_MD = """# P2P Energy Trading Survey

## Abstract
P2P 交易瓶颈在于各 agent 需顺序更新账本。
We review market designs for peer-to-peer energy trading.

## METHOD
We compare centralized and decentralized clearing.
"""

CJK_INSIGHT = json.dumps({
    "title": "P2P Energy Trading Survey",
    "authors": "Wei Zhou",
    "journal_or_conference": "Applied Energy",
    "date": "2023",
    "abstract": "本文综述 P2P 能源交易的市场机制与瓶颈。",
    "keywords": ["P2P trading", "energy market"],
    "summary": ["Novelty: taxonomy", "Method: comparison"],
    "doi": "",
})
