"""FastAPI 路由包（B-SRP-01，拆分自 server.py 的单文件装配）。

各模块暴露 `router`（APIRouter），由 server.py 按原注册顺序 include_router：
system → tasks → documents → knowledge → extraction。
"""
