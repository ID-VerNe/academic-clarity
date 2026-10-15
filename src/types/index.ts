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
  /** 仅 /tasks 返回：流水线当前阶段快照（UX-26） */
  stage?: string;
  progress?: number;
  elapsed?: number;
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

/** Phase 3：自定义提取维度（label UNIQUE，id 稳定键） */
export interface ExtractionDimension {
  id: string;
  label: string;
  prompt: string;
  system_prompt?: string;
  enabled: number | boolean;
  created_at?: string;
  updated_at?: string;
}

/** Phase 3：批量提取入队结果 */
export interface BatchRunResult {
  success: boolean;
  queued: number;
  skipped: number;
}

export interface AppConfig {
  DEEPSEEK_API_KEY: string;
  API_BASE: string;
  /** OCR 模型名（生效值，用于配置完整性校验） */
  OCR_MODEL: string;
  WORKSPACE_PATH: string;
  TABLE_STYLE: string;
}
