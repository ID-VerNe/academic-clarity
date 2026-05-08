"""
Academic Clarity - Message Queue Abstraction
支持 RabbitMQ 和 Kafka 的消息队列抽象层
"""

import os
import json
import asyncio
import time
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from threading import Lock
from collections import defaultdict

try:
    from backend.constants import TaskConfig
except ImportError:
    class TaskConfig:
        DEFAULT_CONCURRENCY = 10

class QueueType(str, Enum):
    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    WORK_QUEUE = "work_queue"

@dataclass
class Message:
    id: str
    body: Any
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3

    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "body": self.body,
            "headers": self.headers,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count
        })

    @classmethod
    def from_json(cls, data: str) -> 'Message':
        parsed = json.loads(data)
        return cls(**parsed)

class MessageHandler(ABC):
    @abstractmethod
    async def handle(self, message: Message) -> bool:
        pass

class QueueConsumer:
    def __init__(self, queue_name: str, handler: MessageHandler):
        self.queue_name = queue_name
        self.handler = handler
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, message_queue: 'MessageQueue'):
        self._running = True
        self._task = asyncio.create_task(self._consume_loop(message_queue))

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _consume_loop(self, message_queue: 'MessageQueue'):
        while self._running:
            try:
                message = await message_queue.get(self.queue_name)
                if message:
                    success = await self.handler.handle(message)
                    if success:
                        await message_queue.ack(message)
                    else:
                        if message.retry_count < message.max_retries:
                            await message_queue.nack(message)
                        else:
                            await message_queue.reject(message)
                else:
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[QueueConsumer] Error: {e}")
                await asyncio.sleep(1)

class InMemoryQueue(MessageQueue):
    """内存消息队列（无外部依赖）"""

    def __init__(self):
        super().__init__()
        self._queues: Dict[str, List[Message]] = defaultdict(list)
        self._waiting: Dict[str, asyncio.Event] = {}
        self._lock = Lock()

    async def publish(self, queue_name: str, message: Message, queue_type: QueueType = QueueType.DIRECT):
        with self._lock:
            self._queues[queue_name].append(message)
            if queue_name in self._waiting:
                self._waiting[queue_name].set()

    async def get(self, queue_name: str, timeout: float = 1.0) -> Optional[Message]:
        while True:
            with self._lock:
                if self._queues[queue_name]:
                    return self._queues[queue_name].pop(0)

                event = self._waiting.get(queue_name)
                if event is None:
                    event = asyncio.Event()
                    self._waiting[queue_name] = event

            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
                event.clear()
            except asyncio.TimeoutError:
                return None

    async def ack(self, message: Message):
        pass

    async def nack(self, message: Message):
        message.retry_count += 1
        await asyncio.sleep(2 ** message.retry_count)
        with self._lock:
            self._queues["retry"].append(message)

    async def reject(self, message: Message):
        with self._lock:
            self._queues["dead_letter"].append(message)

class RabbitMQQueue(MessageQueue):
    """RabbitMQ 实现"""

    def __init__(self, url: str = "amqp://guest:guest@localhost:5672/"):
        self._url = url
        self._connection = None
        self._channel = None
        self._available = False
        self._lock = Lock()
        asyncio.create_task(self._connect())

    async def _connect(self):
        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=10)
            self._available = True
        except ImportError:
            print("[MessageQueue] aio-pika not installed, using in-memory fallback")
            self._available = False
        except Exception as e:
            print(f"[MessageQueue] RabbitMQ connection failed: {e}")
            self._available = False

    async def publish(self, queue_name: str, message: Message, queue_type: QueueType = QueueType.DIRECT):
        if not self._available:
            self._fallback_queue.publish(queue_name, message, queue_type)
            return

        try:
            import aio_pika
            exchange = await self._channel.declare_exchange(
                queue_name,
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )

            await self._channel.declare_queue(queue_name, durable=True)

            await exchange.publish(
                aio_pika.Message(
                    body=message.to_json().encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=queue_name
            )
        except Exception as e:
            print(f"[MessageQueue] Publish error: {e}")
            self._fallback_queue.publish(queue_name, message, queue_type)

    async def get(self, queue_name: str, timeout: float = 1.0) -> Optional[Message]:
        if not self._available:
            return await self._fallback_queue.get(queue_name, timeout)

        try:
            queue = await self._channel.declare_queue(queue_name, durable=True)
            message = await queue.get(timeout=timeout)
            if message:
                return Message.from_json(message.body.decode())
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            print(f"[MessageQueue] Get error: {e}")
        return None

    async def ack(self, message: Message):
        pass

    async def nack(self, message: Message):
        pass

    async def reject(self, message: Message):
        pass

class KafkaQueue(MessageQueue):
    """Kafka 实现"""

    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self._bootstrap_servers = bootstrap_servers
        self._producer = None
        self._consumer = None
        self._available = False
        self._lock = Lock()
        asyncio.create_task(self._connect())

    async def _connect(self):
        try:
            from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
            self._producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers)
            await self._producer.start()
            self._available = True
        except ImportError:
            print("[MessageQueue] aiokafka not installed, using in-memory fallback")
            self._available = False
        except Exception as e:
            print(f"[MessageQueue] Kafka connection failed: {e}")
            self._available = False

    async def publish(self, queue_name: str, message: Message, queue_type: QueueType = QueueType.DIRECT):
        if not self._available:
            self._fallback_queue.publish(queue_name, message, queue_type)
            return

        try:
            await self._producer.send_and_wait(
                queue_name,
                message.to_json().encode(),
                key=message.id.encode()
            )
        except Exception as e:
            print(f"[MessageQueue] Kafka publish error: {e}")
            self._fallback_queue.publish(queue_name, message, queue_type)

    async def get(self, queue_name: str, timeout: float = 1.0) -> Optional[Message]:
        if not self._available:
            return await self._fallback_queue.get(queue_name, timeout)
        return None

    async def ack(self, message: Message):
        pass

    async def nack(self, message: Message):
        pass

    async def reject(self, message: Message):
        pass

class MessageQueue(ABC):
    _fallback_queue: InMemoryQueue = InMemoryQueue()

    @abstractmethod
    async def publish(self, queue_name: str, message: Message, queue_type: QueueType = QueueType.DIRECT):
        pass

    @abstractmethod
    async def get(self, queue_name: str, timeout: float = 1.0) -> Optional[Message]:
        pass

    @abstractmethod
    async def ack(self, message: Message):
        pass

    @abstractmethod
    async def nack(self, message: Message):
        pass

    @abstractmethod
    async def reject(self, message: Message):
        pass

class QueueManager:
    """统一的消息队列管理器"""

    def __init__(self):
        self._queues: Dict[str, MessageQueue] = {}
        self._consumers: List[QueueConsumer] = []
        self._running = False

        self._setup_default_queues()

    def _setup_default_queues(self):
        queue_type = os.environ.get("MESSAGE_QUEUE_TYPE", "memory")

        if queue_type == "rabbitmq":
            url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
            self._queues["default"] = RabbitMQQueue(url)
        elif queue_type == "kafka":
            servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
            self._queues["default"] = KafkaQueue(servers)
        else:
            self._queues["default"] = InMemoryQueue()

    def get_queue(self, name: str = "default") -> MessageQueue:
        return self._queues.get(name, self._queues["default"])

    async def publish_task(self, task_type: str, task_data: Dict):
        message = Message(
            id=f"{task_type}_{int(time.time() * 1000)}",
            body=task_data,
            headers={"task_type": task_type}
        )
        await self.get_queue().publish(f"tasks.{task_type}", message)

    async def subscribe(self, task_type: str, handler: MessageHandler):
        queue_name = f"tasks.{task_type}"
        consumer = QueueConsumer(queue_name, handler)
        await consumer.start(self.get_queue())
        self._consumers.append(consumer)

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False
        for consumer in self._consumers:
            await consumer.stop()

    def get_stats(self) -> Dict:
        return {
            "queues": list(self._queues.keys()),
            "consumers": len(self._consumers),
            "running": self._running
        }

queue_manager = QueueManager()

def get_queue_manager() -> QueueManager:
    return queue_manager
