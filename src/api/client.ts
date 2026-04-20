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

  async getDocuments() {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/documents`);
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

  async chat(docId: number, query: string) {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: docId, query })
    });
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

  async getPdfUrl(filename: string) {
    const baseUrl = await this.getBaseUrl();
    return `${baseUrl}/files/${encodeURIComponent(filename)}`;
  }
}

export const api = new ApiClient();
