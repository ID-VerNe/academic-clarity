"""
Academic Clarity - Microservices Module
微服务架构相关模块
"""

from .architecture import get_architecture_design, get_service_definitions
from .message_queue import get_queue_manager, MessageQueue
from .distributed_scheduler import get_scheduler, submit_distributed_task

__all__ = [
    "get_architecture_design",
    "get_service_definitions",
    "get_queue_manager",
    "MessageQueue",
    "get_scheduler",
    "submit_distributed_task"
]
