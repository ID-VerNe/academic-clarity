"""提取维度管理与批量提取（Phase 3，借鉴 litrev-extract 模式）。

机制映射：维度定义存 DB（替代 litrev YAML config）；断点续跑 =
select_batch_candidates 存在性检查（litrev state.py 等价物）；并发 =
task_hub + 模块级 Semaphore(3) 兜底（替代 litrev RateLimiter）；
error-JSON 转异常（ai_service 单 key 失败路径返回错误 JSON 而非抛错，
不转换会把错误当提取结果落库——Phase 3 质量闸口 R6）。
"""
import asyncio, json, sqlite3, uuid

from services.ai_service import call_json_extraction_api
from services.config_service import ConfigService

_LLM_SEMAPHORE = asyncio.Semaphore(3)   # 批量场景 LLM 并发兜底（R2）


class DimensionError(Exception):
    """维度校验/执行失败（端点转 400/500；worker 内抛出让队列重试）。"""


def validate_dimension(dim: dict) -> dict:
    """集中校验（收集式风格）：label ≤50、prompt ≤8000 非空；
    prompt 含 '{content}' 拒绝——项目约定 prompt + CONTENT 自动拼接。"""
    label = (dim.get('label') or '').strip()
    prompt = (dim.get('prompt') or '').strip()
    if not label or len(label) > 50:
        raise DimensionError('label 必填且 ≤50 字符')
    if not prompt or len(prompt) > 8000:
        raise DimensionError('prompt 必填且 ≤8000 字符')
    if '{content}' in prompt:
        raise DimensionError("prompt 不需要 '{content}'，文档内容会自动附加")
    return {'id': (dim.get('id') or '').strip(), 'label': label, 'prompt': prompt,
            'system_prompt': (dim.get('system_prompt') or '').strip(),
            'enabled': 1 if dim.get('enabled', True) else 0}


def list_dimensions(db) -> list:
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "SELECT * FROM extraction_dimensions ORDER BY created_at, id").fetchall()]


def get_dimension(db, dimension_id) -> dict | None:
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM extraction_dimensions WHERE id = ?",
                           (dimension_id,)).fetchone()
        return dict(row) if row else None


def save_dimension(db, dim: dict) -> dict:
    """upsert：id 空则生成 uuid4().hex[:12]；label 冲突 → DimensionError。"""
    v = validate_dimension(dim)
    if not v['id']:
        v['id'] = uuid.uuid4().hex[:12]
    try:
        with db.safe_write() as cursor:
            cursor.execute('''
                INSERT INTO extraction_dimensions
                    (id, label, prompt, system_prompt, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    label=excluded.label, prompt=excluded.prompt,
                    system_prompt=excluded.system_prompt, enabled=excluded.enabled,
                    updated_at=CURRENT_TIMESTAMP
            ''', (v['id'], v['label'], v['prompt'], v['system_prompt'], v['enabled']))
    except sqlite3.IntegrityError:
        raise DimensionError(f"label '{v['label']}' 已存在")
    return v


def delete_dimension(db, dimension_id) -> bool:
    """只删维度定义；已产生的 metadata 行保留（失去维度关联但不丢数据）。"""
    with db.safe_write() as cursor:
        cursor.execute("DELETE FROM extraction_dimensions WHERE id = ?", (dimension_id,))
        return cursor.rowcount > 0


def select_batch_candidates(db, dimension_id, doc_ids=None, force=False):
    """返回 (to_run, skipped)。跳过：非 completed / 无 markdown / 已有结果
    （force 时忽略已有结果检查）；doc_ids 非空时只在该集合内枚举。"""
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        docs = [dict(r) for r in conn.execute(
            "SELECT id, ocr_status, ocr_markdown FROM documents").fetchall()]
        done = {r[0] for r in conn.execute(
            "SELECT DISTINCT doc_id FROM document_metadata WHERE dimension_id = ?",
            (dimension_id,)).fetchall()}
    to_run, skipped = [], []
    for d in docs:
        if doc_ids and d['id'] not in doc_ids:
            continue
        if d['ocr_status'] != 'completed' or not (d['ocr_markdown'] or '').strip():
            skipped.append(d['id'])
        elif not force and d['id'] in done:
            skipped.append(d['id'])
        else:
            to_run.append(d['id'])
    return to_run, skipped


async def run_dimension_extraction(doc_id: int, dimension_id: str, db):
    """任务队列 worker 入口（签名匹配 task_func(doc_id, *args, db=...)）。"""
    dim = get_dimension(db, dimension_id)
    if not dim or not dim['enabled']:
        raise DimensionError(f'dimension {dimension_id} 不存在或已停用')
    doc = db.get_document(doc_id)
    if not doc or not (doc.get('ocr_markdown') or '').strip():
        raise DimensionError(f'doc {doc_id} 无 OCR 文本')
    cs = ConfigService(db)
    cfg = cs.get_extract_config()
    async with _LLM_SEMAPHORE:
        raw = await call_json_extraction_api(doc['ocr_markdown'], cfg, dim['prompt'])
    data = json.loads(raw)          # 非法 JSON 抛异常 → 队列重试
    if isinstance(data, dict) and 'error' in data:
        raise DimensionError(f"extraction failed: {data['error']}")
    db.add_document_metadata(doc_id, dim['label'], raw, dimension_id=dimension_id)
    return {'doc_id': doc_id, 'dimension_id': dimension_id}


def collect_export_rows(db, dimension_id) -> list:
    """JOIN documents，返回 [{doc_id, filename, title, data(dict), created_at}]。"""
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT m.doc_id, m.content_json, m.created_at, d.filename, d.title
            FROM document_metadata m JOIN documents d ON d.id = m.doc_id
            WHERE m.dimension_id = ? ORDER BY m.doc_id
        ''', (dimension_id,)).fetchall()
    out = []
    for r in rows:
        try:
            data = json.loads(r['content_json'])
        except (json.JSONDecodeError, TypeError):
            data = {}
        out.append({'doc_id': r['doc_id'], 'filename': r['filename'],
                    'title': r['title'], 'data': data, 'created_at': r['created_at']})
    return out
