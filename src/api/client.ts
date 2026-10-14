/**
 * Unified API Client for Academic Clarity
 * Handles port discovery, URL construction, and error handling.
 */

class ApiClient {
  private async getBaseUrl() {
    const port = await (window as any).api.getPythonPort();
    return `http://127.0.0.1:${port}`;
  }

  async syncWorkspace() {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/workspace/sync`, { method: 'POST' });
    return res.json();
  }

  async getConfigs() {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/configs`);
    return res.json();
  }

  async setConfig(key: string, value: string) {
    const baseUrl = await this.getBaseUrl();
    await fetch(`${baseUrl}/configs?key=${key}&value=${encodeURIComponent(value)}`, { method: 'POST' });
  }

  async getMultiKeyStats() {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/configs/multi-keys`);
    return res.json();
  }

  async updateOcrKeys(keysJson: string) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/configs/multi-keys/ocr?ocr_keys=${encodeURIComponent(keysJson)}`, { method: 'POST' });
    return res.json();
  }

  async updateLlmKeys(keysJson: string) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/configs/multi-keys/llm?llm_keys=${encodeURIComponent(keysJson)}`, { method: 'POST' });
    return res.json();
  }

  async getDocuments() {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents`);
    return res.json();
  }

  async getActiveTasks() {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/tasks`);
    return res.json();
  }

  async uploadDocument(file: File) {
    const baseUrl = await this.getBaseUrl();
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${baseUrl}/documents/add`, { method: 'POST', body: formData });
    return res.json();
  }

  async deleteDocument(id: number) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents/${id}`, { method: 'DELETE' });
    return res.json();
  }

  async chat(docId: number, query: string, quotes?: string[]) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: docId, query, quotes })
    });
    return res.json();
  }

  // ── Phase 2：know 知识层 ──────────────────────────────

  /** 跨库检索 claims（FTS + LIKE 兜底；q 限 200 字符内） */
  async searchKnowledge(q: string, limit = 10) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/knowledge/search?q=${encodeURIComponent(q)}&limit=${limit}`);
    return res.json();
  }

  /** 把一篇已完成 OCR + Basic Insight 的文档摄入知识库（幂等） */
  async ingestKnowledge(docId: number) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/knowledge/ingest/${docId}`, { method: 'POST' });
    return res.json();
  }

  /** 知识库论文列表（含 claim 计数） */
  async getKnowledgePapers() {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/knowledge/papers`);
    return res.json();
  }

  /** 单篇论文的全部 claims */
  async getKnowledgeClaims(paperId: string) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/knowledge/papers/${encodeURIComponent(paperId)}/claims`);
    return res.json();
  }

  async getMetadata(docId: number) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents/${docId}/metadata`);
    return res.json();
  }

  async extractMetadata(docId: number, label: string, prompt: string) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents/${docId}/metadata/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label, prompt })
    });
    return res.json();
  }

  async deleteMetadata(metadataId: number) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/metadata/${metadataId}`, { method: 'DELETE' });
    return res.json();
  }

  async reprocessDocument(docId: number) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents/${docId}/reprocess`, { method: 'POST' });
    return res.json();
  }

  async verifyDoi(docId: number) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents/${docId}/doi/verify`, { method: 'POST' });
    return res.json();
  }

  async getBibtex(docId: number) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents/${docId}/bibtex`);
    return res.json();
  }

  async getPdfUrl(filename: string) {
    const baseUrl = await this.getBaseUrl();
    return `${baseUrl}/files/${encodeURIComponent(filename)}`;
  }
}

export const api = new ApiClient();
