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
  doi?: string | null;
  doi_source?: 'llm' | 'crossref' | 'unverified' | null;
  bibtex?: string | null;
  added_at: string;
}

export interface DoiVerification {
  status: 'verified' | 'corrected' | 'mismatch' | 'unverified';
  doi: string | null;
  score: number;
  source: 'llm' | 'crossref' | 'unverified';
  cr_author?: string | null;
  cr_title?: string | null;
  note?: string;
}

/** know 知识层：一条 claim（T1 段落级逐字 / T2 章节级转述，锚永可解析） */
export interface KnowledgeClaim {
  claim_id: number;
  concept: string;
  quote: string;
  anchor: string;        // OCR markdown 中的逐字锚文本
  heading_path: string;
  conflicting: number;
  prompt_id: string;     // basic-insight-v1（T1）/ ~section（T2）
  paper_id?: string;     // doc:{doc_id}（search 端点返回）
  doc_id?: number | null;  // search 端点回填（claims 表本身不存 doc_id）
  title?: string | null;   // search 端点回填论文标题
  doi?: string | null;     // search 端点回填
}

/** know 知识层：一篇论文的 claim 汇总（GET /knowledge/papers） */
export interface KnowledgePaper {
  paper_id: string;      // 固定 doc:{doc_id}
  title: string | null;
  doi: string | null;
  identity_status: string;
  claim_count: number;
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
