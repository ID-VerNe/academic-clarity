"""
Academic Clarity - 单例元类（B-DRY-24 统一 4 处手写单例）

语义：
- 首次 `Cls(...)` 时双检锁（double-checked locking）创建实例，线程安全
  （保留 metrics 原有语义）；
- 之后 `Cls(...)` 恒返回同一实例，且不会重跑 `__init__`；
- 实例创建时机即 `__init__` 执行时机（health 的 `_start_time` 语义不变）。
"""
import threading


class SingletonMeta(type):
    """线程安全单例元类"""

    _instances: dict = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
