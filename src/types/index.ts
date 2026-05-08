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
}
