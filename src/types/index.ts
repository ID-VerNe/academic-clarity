export type View = 'dashboard' | 'reader';

export type OCRStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface OCRStructuredBlock {
  type: 'title' | 'subtitle' | 'text';
  text: string;
}

export interface OCRStructuredContent {
  version: number;
  blocks: OCRStructuredBlock[];
}

export interface Document {
  id: number;
  filename: string;
  title: string;
  authors: string;
  ocr_status: OCRStatus;
  ocr_markdown?: string;
  ocr_structured_json?: OCRStructuredContent;
  metadata_json?: string;
  basic_insight_json?: string; // 聚合的 Basic Insight
  added_at: string;
}

export interface AppConfig {
  DEEPSEEK_API_KEY: string;
  API_BASE: string;
  WORKSPACE_PATH: string;
  TABLE_STYLE: string;
  USE_MULTI_KEY: boolean;
  OCR_MULTI_KEY: boolean;
  LLM_MULTI_KEY: boolean;
}

export interface KeyConfig {
  api_key: string;
  api_base?: string;
  model_name?: string;
  max_concurrent?: number;
  rpm_limit?: number;
  tpm_limit?: number;
  enabled?: boolean;
}

export interface KeyStats {
  api_key: string;
  api_base: string;
  model_name: string;
  active_requests: number;
  max_concurrent: number;
  rpm_limit: number;
  rpm_used: number;
  tpm_limit: number;
  tpm_used: number;
  is_healthy: boolean;
  consecutive_errors: number;
}

export interface KeyPoolStats {
  enabled: boolean;
  keys: KeyStats[];
}

export interface MultiKeyStats {
  ocr: KeyPoolStats;
  llm: KeyPoolStats;
}
