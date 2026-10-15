import { AppConfig } from '../../types';

export interface FieldSpec {
  key: keyof AppConfig & string;
  label: string;
  hint: string;
  placeholder: string;
  secret?: boolean;
  required?: boolean;
  validate?: (value: string) => string | null;
}

export const FIELDS: FieldSpec[] = [
  {
    key: 'DEEPSEEK_API_KEY',
    label: 'OCR API Key',
    hint: '用于调用 OCR 模型（DeepSeek-OCR / SiliconFlow）',
    placeholder: 'sk-...',
    secret: true,
    required: true,
  },
  {
    key: 'API_BASE',
    label: 'API Base URL',
    hint: 'OCR 服务地址；本地代理可填 http://localhost:37210/v1',
    placeholder: 'https://api.siliconflow.cn/v1',
    required: true,
    validate: (v) => (/^https?:\/\//.test(v) ? null : '必须以 http:// 或 https:// 开头'),
  },
  {
    key: 'OCR_MODEL',
    label: 'OCR 模型名',
    hint: '如 deepseek-ai/DeepSeek-OCR',
    placeholder: 'deepseek-ai/DeepSeek-OCR',
    required: true,
  },
];

export const TABLE_STYLES = [
  { value: 'three-line', label: '三线表（学术论文常用）' },
  { value: 'grid', label: '网格表' },
];
