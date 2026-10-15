import React, { useState } from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { Dashboard } from '../Dashboard';
import { Document, AppConfig } from '../../types';
import { api } from '../../api/client';

// 说明：本文件不是测试文件，仅提供 3 个 Dashboard 测试文件共享的夹具与 helper。
// vi.mock('../api/client') 需在各测试文件内声明（vitest mock 按文件隔离），
// 这里导入的 api 在测试文件中会自动拿到 mock 版本。

export const mockConfig: AppConfig = {
  DEEPSEEK_API_KEY: 'sk-test',
  API_BASE: 'http://localhost:37210/v1',
  OCR_MODEL: 'deepseek-ai/DeepSeek-OCR',
  WORKSPACE_PATH: '/papers',
  TABLE_STYLE: 'three-line',
};

export const mockDocs: Document[] = [
  {
    id: 1,
    filename: 'paper1.pdf',
    title: 'Alpha Research',
    authors: 'Alice',
    ocr_status: 'completed',
    ocr_markdown: 'Content 1',
    basic_insight_json: JSON.stringify({ journal_or_conference: 'Nature', date: '2023' }),
    added_at: '2024-01-02T00:00:00Z',
  },
  {
    id: 2,
    filename: 'paper2.pdf',
    title: 'Beta Science',
    authors: 'Bob',
    ocr_status: 'completed',
    ocr_markdown: 'Content 2',
    basic_insight_json: JSON.stringify({ journal_or_conference: 'Science', date: '2024' }),
    added_at: '2024-03-04T00:00:00Z',
  },
];

export type DashboardProps = React.ComponentProps<typeof Dashboard>;

export const baseProps = (): DashboardProps => ({
  docs: mockDocs,
  onSelectDoc: vi.fn(),
  onUpload: vi.fn(),
  onDelete: vi.fn(),
  onReprocess: vi.fn(),
  onSelectWorkspace: vi.fn(),
  onOpenSettings: vi.fn(),
  onSync: vi.fn(),
  onRefresh: vi.fn(),
  isUploading: false,
  isLoading: false,
  isSyncing: false,
  config: mockConfig,
  searchQuery: '',
  onSearchChange: vi.fn(),
  backendHealthy: true,
});

/** 检索框是受控组件：用带本地 state 的壳子模拟真实输入 */
export const SearchHarness = ({ docs, ...rest }: Partial<DashboardProps>) => {
  const [query, setQuery] = useState('');
  return (
    <Dashboard
      {...baseProps()}
      docs={docs ?? mockDocs}
      searchQuery={query}
      onSearchChange={setQuery}
      {...rest}
    />
  );
};

/** 各 describe 的 beforeEach 共用：把 api mock 复位到默认实现 */
export const resetApiMocks = () => {
  vi.clearAllMocks();
  (api.getActiveTasks as any).mockResolvedValue([]);
  (api.searchKnowledge as any).mockResolvedValue({ results: [] });
  (api.ingestKnowledge as any).mockResolvedValue({ success: true, result: {} });
  (api.cancelTask as any).mockResolvedValue({ success: true });
};

/** 打开 claims 检索并提交查询（tab → 输入 → 检索 三段式操作） */
export const searchClaims = (query: string) => {
  fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));
  fireEvent.change(screen.getByLabelText('检索知识库 claim'), { target: { value: query } });
  fireEvent.click(screen.getByRole('button', { name: /^检索$/ }));
};
