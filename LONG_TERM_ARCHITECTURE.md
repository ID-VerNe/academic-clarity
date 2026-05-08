# Academic Clarity - 长期架构优化设计

**文档版本**: 1.0
**创建日期**: 2026-05-08
**目标版本**: v2.0

---

## 一、微服务架构拆分

### 1.1 当前架构问题

当前单体架构的问题：
- 所有功能耦合在一起，部署困难
- 单点故障影响整个系统
- 无法独立扩展各个组件
- 技术栈升级影响面大

### 1.2 推荐微服务拆分

```
┌─────────────────────────────────────────────────────────────────────┐
│                          API Gateway (Nginx/Traefik)                │
│                         Port 80/443 /auth, /route                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  OCR Service  │     │   LLM Service │     │  API Gateway  │
│  (独立部署)    │     │  (独立部署)    │     │  (FastAPI)    │
│  Port 8001    │     │  Port 8002    │     │  Port 8000    │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────┐
                │         Redis / Kafka         │
                │     (消息队列/缓存/会话)        │
                └───────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Database    │     │   MinIO/S3    │     │  Worker Pool  │
│  (PostgreSQL) │     │  (文件存储)    │     │  (Celery)     │
└───────────────┘     └───────────────┘     └───────────────┘
```

### 1.3 服务职责划分

| 服务名称 | 职责 | 技术栈 | 扩展策略 |
|---------|------|--------|---------|
| `api-gateway` | 请求路由、认证限流 | FastAPI + Nginx | 水平扩展 |
| `ocr-service` | PDF处理、OCR识别 | FastAPI + Tesseract | 水平扩展 |
| `llm-service` | AI模型调用、元数据提取 | FastAPI + OpenAI SDK | 水平扩展 |
| `worker-pool` | 异步任务执行 | Celery + Redis | 按任务量扩展 |
| `storage-service` | 文件存储、元数据管理 | FastAPI + MinIO | 水平扩展 |

### 1.4 迁移步骤

1. **第一阶段：基础设施准备**
   - 部署 Docker/Kubernetes 环境
   - 搭建 Redis Cluster
   - 部署 PostgreSQL
   - 配置 API Gateway

2. **第二阶段：服务拆分**
   - 抽取 OCR Service
   - 抽取 LLM Service
   - 抽取 Worker Service

3. **第三阶段：数据迁移**
   - SQLite → PostgreSQL
   - 文件系统 → MinIO
   - 配置中心迁移

---

## 二、消息队列设计 (RabbitMQ/Kafka)

### 2.1 消息队列架构

```
                    ┌─────────────────┐
                    │   OCR Requests   │ (Exchange: ocr.exchange)
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  ocr.queue.1  │   │  ocr.queue.2 │   │  ocr.queue.3 │
│  (Worker 1)   │   │  (Worker 2)   │   │  (Worker N)   │
└───────────────┘   └───────────────┘   └───────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  OCR Results    │ (Exchange: results.exchange)
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Result Handler │ (Webhook/SSE)
                    └─────────────────┘
```

### 2.2 Kafka Topic 设计

| Topic 名称 | 用途 | 分区数 | 保留时间 |
|-----------|------|--------|---------|
| `ocr-requests` | OCR任务请求 | 6 | 7天 |
| `ocr-results` | OCR处理结果 | 6 | 7天 |
| `llm-requests` | LLM任务请求 | 6 | 7天 |
| `llm-results` | LLM处理结果 | 6 | 7天 |
| `task-events` | 任务状态变更 | 3 | 30天 |
| `system-metrics` | 系统指标 | 1 | 7天 |

### 2.3 消息格式 (Avro Schema)

```json
{
  "type": "record",
  "name": "OCRTask",
  "fields": [
    {"name": "task_id", "type": "string"},
    {"name": "doc_id", "type": "long"},
    {"name": "file_path", "type": "string"},
    {"name": "priority", "type": "int"},
    {"name": "retry_count", "type": "int"},
    {"name": "created_at", "type": "long"},
    {"name": "metadata", "type": {"type": "map", "values": "string"}}
  ]
}
```

### 2.4 实现代码模板

```python
# services/rabbitmq_client.py
from typing import Optional, Dict, Any, Callable
import json
import aio_pika
from aio_pika import Message, ExchangeType

class RabbitMQClient:
    def __init__(self, url: str, exchange_name: str):
        self.url = url
        self.exchange_name = exchange_name
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            self.exchange_name,
            ExchangeType.TOPIC,
            durable=True
        )

    async def publish(self, routing_key: str, message: Dict[str, Any]):
        await self.exchange.publish(
            Message(body=json.dumps(message).encode()),
            routing_key=routing_key
        )

    async def consume(self, queue_name: str, callback: Callable):
        queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.bind(self.exchange, routing_key=queue_name)
        await queue.consume(callback)

# 使用示例
async def process_ocr_task(message: aio_pika.IncomingMessage):
    async with message.process():
        data = json.loads(message.body)
        doc_id = data["doc_id"]
        # 处理逻辑
        await rabbitmq.publish("ocr.results", {"doc_id": doc_id, "status": "completed"})

rabbitmq = RabbitMQClient("amqp://user:pass@localhost:5672/", "ocr.exchange")
```

---

## 三、分布式任务调度

### 3.1 分布式架构设计

```
                        ┌─────────────────────────────┐
                        │     Kubernetes Cluster       │
                        │                              │
    ┌───────────────────┼───────────────────────────────┼───────────────────┐
    │                   │                               │                   │
    ▼                   ▼                               ▼                   ▼
┌─────────┐        ┌─────────┐                    ┌─────────┐        ┌─────────┐
│ Master  │◄──────►│ Master  │                    │ Worker  │        │ Worker  │
│ Node    │        │ Node    │                    │ Node 1  │        │ Node 2  │
│ (Leader)│        │ (Standby)                    │         │        │         │
└─────────┘        └─────────┘                    └────┬────┘        └────┬────┘
                                                      │                    │
                                                      └─────────┬──────────┘
                                                                │
                                                    ┌───────────┴───────────┐
                                                    │    Celery Workers      │
                                                    │  ┌────┐ ┌────┐ ┌────┐  │
                                                    │  │ W1 │ │ W2 │ │ W3 │  │
                                                    │  └────┘ └────┘ └────┘  │
                                                    └─────────────────────────┘
```

### 3.2 任务调度策略

```python
# tasks/celery_config.py
from celery import Celery
from celery.schedules import crontab

app = Celery('academic_clarity')

app.conf.update(
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/1',

    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    task_routes={
        'tasks.ocr.*': {'queue': 'ocr'},
        'tasks.llm.*': {'queue': 'llm'},
        'tasks.cleanup.*': {'queue': 'maintenance'},
    },

    beat_schedule={
        'cleanup-old-results': {
            'task': 'tasks.cleanup.cleanup_old_results',
            'schedule': crontab(hour=3, minute=0),
        },
        'health-check': {
            'task': 'tasks.monitoring.health_check',
            'schedule': 300.0,
        },
    },

    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

# tasks/ocr_tasks.py
@app.task(bind=True, max_retries=3, default_retry_delay=60)
def ocr_process_pdf(self, doc_id: int, file_path: str, priority: int = 2):
    try:
        result = perform_ocr(file_path)
        save_result(doc_id, result)

        llm_extract_metadata.delay(
            doc_id,
            result['markdown'],
            priority=max(1, priority - 1)
        )

        return {'status': 'completed', 'doc_id': doc_id}

    except TemporaryError as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except PermanentError as e:
        mark_task_failed(doc_id, str(e))
        raise
```

### 3.3 分布式锁设计

```python
# utils/distributed_lock.py
import redis
import uuid
from contextlib import contextmanager
from typing import Optional

class DistributedLock:
    def __init__(self, redis_client: redis.Redis, lock_name: str, timeout: int = 30):
        self.redis = redis_client
        self.lock_name = f"lock:{lock_name}"
        self.timeout = timeout
        self.token = str(uuid.uuid4())

    def acquire(self, blocking: bool = True, blocking_timeout: int = 10) -> bool:
        end_time = time.time() + blocking_timeout
        while True:
            if self.redis.set(self.lock_name, self.token, nx=True, ex=self.timeout):
                return True
            if not blocking or time.time() >= end_time:
                return False
            time.sleep(0.1)

    def release(self):
        if self.redis.get(self.lock_name) == self.token.encode():
            self.redis.delete(self.lock_name)

    @contextmanager
    def lock(self):
        if self.acquire():
            try:
                yield
            finally:
                self.release()
        else:
            raise TimeoutError(f"Could not acquire lock: {self.lock_name}")
```

### 3.4 故障恢复机制

| 故障类型 | 检测方式 | 恢复策略 |
|---------|---------|---------|
| Worker 宕机 | Heartbeat 超时 | 任务重新入队 |
| 任务超时 | Celery 监控 | 重新调度 |
| 服务不可用 | 健康检查 | 流量切换 |
| 数据丢失 | 定期备份 | 从备份恢复 |
| 网络分区 | Consul 发现 | 降级本地处理 |

---

## 四、实施路线图

### Phase 1: 短期优化 (1-2周)
- ✅ 统一日志系统
- ✅ 健康检查端点
- ✅ Prometheus 指标

### Phase 2: 中期扩展 (1个月)
- ✅ Redis 缓存层
- ✅ WebSocket 实时推送
- ✅ 优先级队列

### Phase 3: 服务拆分 (2-3个月)
- [ ] Docker 容器化
- [ ] API Gateway 部署
- [ ] 服务发现配置
- [ ] 灰度发布

### Phase 4: 消息队列 (3-4个月)
- [ ] RabbitMQ/Kafka 部署
- [ ] 任务队列迁移
- [ ] 事件驱动架构

### Phase 5: 分布式调度 (4-6个月)
- [ ] Kubernetes 迁移
- [ ] Celery 集群部署
- [ ] 故障恢复机制
- [ ] 监控告警系统

---

## 五、技术栈建议

### 当前 → 目标

| 组件 | 当前 | 目标 | 迁移风险 |
|-----|------|------|---------|
| API | FastAPI | FastAPI (微服务) | 低 |
| 数据库 | SQLite | PostgreSQL | 中 |
| 缓存 | 内存/LRU | Redis Cluster | 中 |
| 任务队列 | asyncio.Queue | Celery/RabbitMQ | 高 |
| 文件存储 | 本地文件系统 | MinIO/S3 | 中 |
| 部署 | 单机 | Kubernetes | 高 |
| 监控 | 基础日志 | Prometheus/Grafana | 低 |

---

**文档维护**: 请在每次架构变更后更新此文档
**审查周期**: 每季度审查一次
**版本控制**: Git 跟踪
