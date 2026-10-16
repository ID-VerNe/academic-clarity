/**
 * Unified API Client for Academic Clarity
 * Handles port discovery, URL construction, and error handling.
 */
import { ExtractionDimension, BatchRunResult } from '../types';

class ApiClient {
  private async getBaseUrl() {
    const port = await (window as any).api.getPythonPort();
    return `http://127.0.0.1:${port}`;
  }

  /** 传输层：解析 baseUrl 并发起请求（不解析响应体，供各语义通道复用） */
  private async fetchRaw(path: string, init?: RequestInit): Promise<Response> {
    const baseUrl = await this.getBaseUrl();
    return fetch(`${baseUrl}${path}`, init);
  }

  /**
   * 软通道：直接解析 JSON 返回。
   * 与重构前绝大多数方法一致——不检查 res.ok，HTTP 错误由调用方按响应体处理。
   */
  private async request<T = any>(path: string, init?: RequestInit): Promise<T> {
    const res = await this.fetchRaw(path, init);
    return res.json();
  }

  /**
   * 严格通道：先解析 JSON，非 2xx 时抛错（带后端 detail）。
   * 语义与重构前的 saveDimension 逐字一致。
   */
  private async requestStrict<T = any>(path: string, init?: RequestInit): Promise<T> {
    const res = await this.fetchRaw(path, init);
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
    return data;
  }

  async syncWorkspace() {
    return this.request('/workspace/sync', { method: 'POST' });
  }

  async getConfigs() {
    return this.request('/configs');
  }

  async setConfig(key: string, value: string) {
    // 与重构前一致：不解析响应体（调用方只关心请求是否抛错）
    await this.fetchRaw(`/configs?key=${key}&value=${encodeURIComponent(value)}`, { method: 'POST' });
  }

  /** 后端存活探测（页脚状态灯 / 连接反馈） */
  async health() {
    return this.request('/health');
  }

  async getDocuments() {
    return this.request('/documents');
  }

  async getActiveTasks() {
    return this.request('/tasks');
  }

  /** 取消排队中/运行中的任务（UX-26） */
  async cancelTask(docId: number) {
    return this.request(`/tasks/${docId}/cancel`, { method: 'POST' });
  }

  async uploadDocument(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/documents/add', { method: 'POST', body: formData });
  }

  async deleteDocument(id: number) {
    return this.request(`/documents/${id}`, { method: 'DELETE' });
  }

  async chat(docId: number, query: string, quotes?: string[]) {
    return this.request('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: docId, query, quotes }),
    });
  }

  // ── Phase 2：know 知识层 ──────────────────────────────

  /** 跨库检索 claims（FTS + LIKE 兜底；q 限 200 字符内） */
  async searchKnowledge(q: string, limit = 10) {
    return this.request(`/knowledge/search?q=${encodeURIComponent(q)}&limit=${limit}`);
  }

  /** 把一篇已完成 OCR + Basic Insight 的文档摄入知识库（幂等） */
  async ingestKnowledge(docId: number) {
    return this.request(`/knowledge/ingest/${docId}`, { method: 'POST' });
  }

  // ── Phase 3：提取维度 / 批量 / 导出 ────────────────────

  /** 维度列表 */
  async getDimensions() {
    return this.request('/extraction/dimensions');
  }

  /** 新建/更新维度（400 校验失败 → throw 带 detail） */
  async saveDimension(dim: Partial<ExtractionDimension>) {
    return this.requestStrict('/extraction/dimensions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dim),
    });
  }

  async deleteDimension(id: string) {
    return this.request(`/extraction/dimensions/${encodeURIComponent(id)}`, { method: 'DELETE' });
  }

  /** 批量提取入队（docIds 空 = 全部候选；force 重跑已有结果） */
  async runBatch(dimensionId: string, docIds?: number[], force = false): Promise<BatchRunResult> {
    return this.request('/extraction/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dimension_id: dimensionId, doc_ids: docIds || [], force }),
    });
  }

  /** 导出维度结果为 Blob（组件用 createObjectURL 触发下载）；失败 throw（既有文案） */
  async exportDimension(dimensionId: string, format: 'csv' | 'md') {
    const res = await this.fetchRaw(
      `/documents/export?dimension_id=${encodeURIComponent(dimensionId)}&format=${format}`);
    if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`);
    return res.blob();
  }

  async getMetadata(docId: number) {
    return this.request(`/documents/${docId}/metadata`);
  }

  async extractMetadata(docId: number, label: string, prompt: string) {
    return this.request(`/documents/${docId}/metadata/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, prompt }),
    });
  }

  async deleteMetadata(metadataId: number) {
    return this.request(`/metadata/${metadataId}`, { method: 'DELETE' });
  }

  async reprocessDocument(docId: number) {
    return this.request(`/documents/${docId}/reprocess`, { method: 'POST' });
  }

  async verifyDoi(docId: number) {
    return this.request(`/documents/${docId}/doi/verify`, { method: 'POST' });
  }

  async getBibtex(docId: number) {
    return this.request(`/documents/${docId}/bibtex`);
  }

  async getPdfUrl(filename: string) {
    const baseUrl = await this.getBaseUrl();
    return `${baseUrl}/files/${encodeURIComponent(filename)}`;
  }

  /** 下载 PDF 二进制（PdfViewer 用 Object URL 渲染）；非 2xx 抛 `HTTP {status}`（与原裸 fetch 行为一致） */
  async getPdfBlob(filename: string): Promise<Blob> {
    const res = await this.fetchRaw(`/files/${encodeURIComponent(filename)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.blob();
  }
}

export const api = new ApiClient();
