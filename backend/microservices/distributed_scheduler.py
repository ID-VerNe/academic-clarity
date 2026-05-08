"""
Academic Clarity - Distributed Task Scheduler
分布式任务调度器，支持多节点、负载均衡、故障转移
"""

import os
import asyncio
import json
import time
import hashlib
import random
from typing import Dict, Any, Optional, Set, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from collections import defaultdict
import uuid

try:
    from backend.constants import TaskConfig
except ImportError:
    class TaskConfig:
        DEFAULT_CONCURRENCY = 10

class TaskState(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class NodeStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"

@dataclass
class DistributedTask:
    task_id: str
    task_type: str
    payload: Dict
    priority: int = 2
    state: TaskState = TaskState.PENDING
    created_at: float = field(default_factory=time.time)
    assigned_at: float = None
    started_at: float = None
    completed_at: float = None
    assigned_node: str = None
    retries: int = 0
    max_retries: int = 3
    result: Any = None
    error: str = None
    dependencies: Set[str] = field(default_factory=set)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority,
            "state": self.state.value if isinstance(self.state, Enum) else self.state,
            "created_at": self.created_at,
            "assigned_at": self.assigned_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "assigned_node": self.assigned_node,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "result": self.result,
            "error": self.error,
            "dependencies": list(self.dependencies),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DistributedTask':
        data = dict(data)
        data["state"] = TaskState(data.get("state", "pending"))
        return cls(**data)

@dataclass
class WorkerNode:
    node_id: str
    host: str
    port: int
    status: NodeStatus = NodeStatus.IDLE
    current_tasks: int = 0
    max_tasks: int = 5
    load_factor: float = 0.0
    last_heartbeat: float = field(default_factory=time.time)
    capabilities: Set[str] = field(default_factory=set)
    region: str = "default"
    metadata: Dict = field(default_factory=dict)

    def update_heartbeat(self):
        self.last_heartbeat = time.time()

    def is_alive(self, timeout: float = 30.0) -> bool:
        return time.time() - self.last_heartbeat < timeout

    def get_score(self) -> float:
        if not self.is_alive():
            return 0.0
        return (self.max_tasks - self.current_tasks) / self.max_tasks * (1.0 - self.load_factor)

class DistributedTaskScheduler:
    """分布式任务调度器"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._node_id = os.environ.get("NODE_ID", f"node_{uuid.uuid4().hex[:8]}")
        self._host = os.environ.get("HOST", "localhost")
        self._port = int(os.environ.get("PORT", "8000"))

        self._tasks: Dict[str, DistributedTask] = {}
        self._nodes: Dict[str, WorkerNode] = {}
        self._task_queue: List[str] = []
        self._running_tasks: Dict[str, str] = {}

        self._handlers: Dict[str, Callable] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._running = False

        self._task_lock = Lock()
        self._node_lock = Lock()

    def register_handler(self, task_type: str, handler: Callable):
        self._handlers[task_type] = handler

    async def start(self):
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        self._register_node()

    async def stop(self):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
        self._unregister_node()

    def _register_node(self):
        node = WorkerNode(
            node_id=self._node_id,
            host=self._host,
            port=self._port,
            status=NodeStatus.IDLE,
            capabilities=set(self._handlers.keys())
        )
        with self._node_lock:
            self._nodes[self._node_id] = node

    def _unregister_node(self):
        with self._node_lock:
            if self._node_id in self._nodes:
                del self._nodes[self._node_id]

    async def _heartbeat_loop(self):
        while self._running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(10)
            except Exception as e:
                print(f"[Scheduler] Heartbeat error: {e}")

    async def _send_heartbeat(self):
        node = self._nodes.get(self._node_id)
        if node:
            node.update_heartbeat()
            node.current_tasks = len([t for t in self._tasks.values() if t.state == TaskState.RUNNING and t.assigned_node == self._node_id])
            node.status = NodeStatus.BUSY if node.current_tasks > 0 else NodeStatus.IDLE

    async def _dispatch_loop(self):
        while self._running:
            try:
                await self._dispatch_tasks()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[Scheduler] Dispatch error: {e}")

    def submit_task(
        self,
        task_type: str,
        payload: Dict,
        priority: int = 2,
        dependencies: Set[str] = None,
        max_retries: int = 3,
        metadata: Dict = None
    ) -> str:
        task_id = f"{task_type}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"

        task = DistributedTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            dependencies=dependencies or set(),
            max_retries=max_retries,
            metadata=metadata or {}
        )

        with self._task_lock:
            self._tasks[task_id] = task
            heapq.heappush(self._task_queue, (task.priority, task.created_at, task_id))

        return task_id

    async def _dispatch_tasks(self):
        with self._task_lock:
            available_tasks = []
            while self._task_queue:
                priority, created_at, task_id = heapq.heappop(self._task_queue)
                task = self._tasks.get(task_id)
                if task and task.state == TaskState.PENDING:
                    if self._check_dependencies(task):
                        available_tasks.append(task)
                elif task is None:
                    continue
                else:
                    heapq.heappush(self._task_queue, (priority, created_at, task_id))
                    break

        for task in available_tasks:
            node = self._select_node(task)
            if node:
                await self._assign_task(task, node)
            else:
                with self._task_lock:
                    heapq.heappush(self._task_queue, (task.priority, task.created_at, task.task_id))
                break

    def _check_dependencies(self, task: DistributedTask) -> bool:
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep and dep.state != TaskState.COMPLETED:
                return False
        return True

    def _select_node(self, task: DistributedTask) -> Optional[WorkerNode]:
        with self._node_lock:
            available = [
                node for node in self._nodes.values()
                if node.is_alive() and node.current_tasks < node.max_tasks
                and task.task_type in node.capabilities
            ]
            if not available:
                return None
            return max(available, key=lambda n: n.get_score())

    async def _assign_task(self, task: DistributedTask, node: WorkerNode):
        task.state = TaskState.ASSIGNED
        task.assigned_at = time.time()
        task.assigned_node = node.node_id

        node.current_tasks += 1

        if node.node_id == self._node_id:
            await self._execute_local(task)
        else:
            await self._send_remote_task(task, node)

    async def _execute_local(self, task: DistributedTask):
        handler = self._handlers.get(task.task_type)
        if not handler:
            task.state = TaskState.FAILED
            task.error = f"No handler for task type: {task.task_type}"
            return

        task.state = TaskState.RUNNING
        task.started_at = time.time()

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(task.payload)
            else:
                result = handler(task.payload)

            task.state = TaskState.COMPLETED
            task.result = result
            task.completed_at = time.time()
        except Exception as e:
            task.state = TaskState.FAILED
            task.error = str(e)
            task.retries += 1

            if task.retries < task.max_retries:
                task.state = TaskState.PENDING
                with self._task_lock:
                    heapq.heappush(self._task_queue, (task.priority, task.created_at, task.task_id))

        node = self._nodes.get(self._node_id)
        if node:
            node.current_tasks = max(0, node.current_tasks - 1)

    async def _send_remote_task(self, task: DistributedTask, node: WorkerNode):
        pass

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        task = self._tasks.get(task_id)
        if task:
            return task.to_dict()
        return None

    def get_node_status(self, node_id: str = None) -> Dict:
        if node_id:
            node = self._nodes.get(node_id)
            if node:
                return {
                    "node_id": node.node_id,
                    "status": node.status.value,
                    "current_tasks": node.current_tasks,
                    "max_tasks": node.max_tasks,
                    "is_alive": node.is_alive(),
                    "last_heartbeat": node.last_heartbeat,
                    "capabilities": list(node.capabilities)
                }
            return None

        with self._node_lock:
            return {
                "nodes": [
                    {
                        "node_id": n.node_id,
                        "status": n.status.value,
                        "current_tasks": n.current_tasks,
                        "max_tasks": n.max_tasks,
                        "is_alive": n.is_alive()
                    }
                    for n in self._nodes.values()
                ],
                "total_nodes": len(self._nodes),
                "alive_nodes": sum(1 for n in self._nodes.values() if n.is_alive())
            }

    def get_stats(self) -> Dict:
        with self._task_lock:
            tasks_by_state = defaultdict(int)
            for task in self._tasks.values():
                tasks_by_state[task.state.value] += 1

        return {
            "total_tasks": len(self._tasks),
            "pending_tasks": tasks_by_state.get("pending", 0),
            "running_tasks": tasks_by_state.get("running", 0),
            "completed_tasks": tasks_by_state.get("completed", 0),
            "failed_tasks": tasks_by_state.get("failed", 0),
            "queued_tasks": len(self._task_queue),
            "nodes": len(self._nodes),
            "node_id": self._node_id
        }

import heapq
scheduler = DistributedTaskScheduler()

def get_scheduler() -> DistributedTaskScheduler:
    return scheduler

def submit_distributed_task(
    task_type: str,
    payload: Dict,
    priority: int = 2,
    dependencies: Set[str] = None
) -> str:
    return scheduler.submit_task(task_type, payload, priority, dependencies)
