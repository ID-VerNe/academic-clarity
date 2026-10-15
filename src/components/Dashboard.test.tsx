import React, { useState } from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { Dashboard } from './Dashboard';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Document, AppConfig } from '../types';
import { api } from '../api/client';

// Mock the API client（claims 检索/摄入 + 处理队列轮询 + 取消）
vi.mock('../api/client', () => ({
  api: {
    getActiveTasks: vi.fn().mockResolvedValue([]),
    searchKnowledge: vi.fn().mockResolvedValue({ results: [] }),
    ingestKnowledge: vi.fn().mockResolvedValue({ success: true, result: {} }),
    cancelTask: vi.fn().mockResolvedValue({ success: true }),
  },
}));

const mockConfig: AppConfig = {
  DEEPSEEK_API_KEY: 'sk-test',
  API_BASE: 'http://localhost:37210/v1',
  OCR_MODEL: 'deepseek-ai/DeepSeek-OCR',
  WORKSPACE_PATH: '/papers',
  TABLE_STYLE: 'three-line',
};

const mockDocs: Document[] = [
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

type DashboardProps = React.ComponentProps<typeof Dashboard>;

const baseProps = (): DashboardProps => ({
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
const SearchHarness = ({ docs, ...rest }: Partial<DashboardProps>) => {
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

describe('Dashboard Filtering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getActiveTasks as any).mockResolvedValue([]);
  });

  it('filters by search query (title / authors)', async () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('搜索文献'), { target: { value: 'Alpha' } });

    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  // UX-13：检索范围兑现 placeholder 承诺（含洞察字段）
  it('also matches insight fields and reports the search scope', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('搜索文献'), { target: { value: 'Science' } });

    expect(screen.getByText('Beta Science')).toBeDefined();
    expect(screen.queryByText('Alpha Research')).toBeNull();
    expect(screen.getByText(/检索范围：标题、文件名、作者、期刊、年份与洞察字段/)).toBeDefined();
  });

  it('filters by journal selection', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('按期刊筛选'), { target: { value: 'Nature' } });

    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('filters by year selection', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('按年份筛选'), { target: { value: '2024' } });

    expect(screen.getByText('Beta Science')).toBeDefined();
    expect(screen.queryByText('Alpha Research')).toBeNull();
  });

  it('resets all filters when clicking the filter clear button', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('按年份筛选'), { target: { value: '2024' } });
    fireEvent.change(screen.getByLabelText('搜索文献'), { target: { value: '不存在的关键词' } });

    // UX-12：筛选无结果与「空库」区分开
    expect(screen.getByText('没有符合当前筛选条件的文献')).toBeDefined();

    fireEvent.click(screen.getByLabelText('清除筛选条件'));

    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.getByText('Beta Science')).toBeDefined();
  });

  it('sorts the library by import time (newest first by default)', () => {
    render(<SearchHarness />);

    const cards = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(cards[0]).toBe('Beta Science');
    expect(cards[1]).toBe('Alpha Research');
  });

  it('mounts a hidden file input wired to the import button', () => {
    const handlers = baseProps();
    const { container } = render(<Dashboard {...handlers} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(fileInput).not.toBeNull();
    expect(fileInput!.accept).toBe('.pdf,.tex,.zip');

    const clickSpy = vi.spyOn(fileInput!, 'click');
    fireEvent.click(screen.getByRole('button', { name: /导入 PDF \/ LaTeX/ }));
    expect(clickSpy).toHaveBeenCalled();

    const file = new File(['dummy'], 'paper.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput!, { target: { files: [file] } });
    expect(handlers.onUpload).toHaveBeenCalledWith(file);
  });

  it('disables the import button while uploading', () => {
    render(<Dashboard {...baseProps()} isUploading={true} />);

    const btn = screen.getByRole('button', { name: /导入中/ });
    expect(btn).toBeDisabled();
  });

  // UX-35：拖拽导入
  it('imports a file dropped onto the page and rejects unsupported types', () => {
    const handlers = baseProps();
    const { container } = render(<Dashboard {...handlers} />);
    const main = container.querySelector('main')!;

    const pdf = new File(['x'], 'dropped.pdf', { type: 'application/pdf' });
    fireEvent.drop(main, { dataTransfer: { files: [pdf] } });
    expect(handlers.onUpload).toHaveBeenCalledWith(pdf);

    const doc = new File(['x'], 'notes.docx');
    fireEvent.drop(main, { dataTransfer: { files: [doc] } });
    expect(handlers.onUpload).toHaveBeenCalledTimes(1);
  });

  // UX-03：同步按钮由上层负责刷新
  it('delegates sync to the parent handler', () => {
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    fireEvent.click(screen.getByLabelText('同步工作区'));

    expect(handlers.onSync).toHaveBeenCalled();
  });

  // UX-37：工具栏图标按钮具备可访问名称
  it('exposes accessible labels for workspace / sync / card actions', () => {
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    expect(screen.getByLabelText('切换工作区')).toBeDefined();
    expect(screen.getByLabelText('阅读 Alpha Research')).toBeDefined();
    expect(screen.getByLabelText('删除 Alpha Research')).toBeDefined();

    fireEvent.click(screen.getByLabelText('删除 Alpha Research'));
    expect(handlers.onDelete).toHaveBeenCalledWith(mockDocs[0]);
  });

  // UX-32：配置不完整时的引导
  it('shows a setup banner and links to settings when config is incomplete', () => {
    const handlers = baseProps();
    render(
      <Dashboard
        {...handlers}
        config={{ ...mockConfig, DEEPSEEK_API_KEY: '', OCR_MODEL: '' }}
      />
    );

    expect(screen.getByText('尚未完成 AI 配置，导入的文献将无法处理')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /去设置/ }));
    expect(handlers.onOpenSettings).toHaveBeenCalled();
  });

  // UX-12 / UX-32：空库三步引导
  it('shows a 3-step onboarding guide when the library is empty', () => {
    const handlers = baseProps();
    render(<Dashboard {...handlers} docs={[]} />);

    expect(screen.getByText('文献库还是空的')).toBeDefined();

    // 三步引导（限定在有序列表内，避免与同名按钮文案冲突）
    const steps = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(steps).toHaveLength(3);
    expect(within(steps[0]).getByText('选择工作区')).toBeDefined();
    expect(within(steps[1]).getByText('配置 OCR API Key')).toBeDefined();
    expect(within(steps[2]).getByText('导入 PDF / LaTeX')).toBeDefined();

    // 引导卡上的三个操作按钮
    expect(screen.getByRole('button', { name: /选择工作区/ })).toBeDefined();
    expect(screen.getByRole('button', { name: /打开设置/ })).toBeDefined();
    expect(screen.getByRole('button', { name: /导入第一篇/ })).toBeDefined();

    expect(screen.queryByText('没有符合当前筛选条件的文献')).toBeNull();
  });

  it('renders skeleton cards while loading', () => {
    const { container } = render(<Dashboard {...baseProps()} isLoading={true} />);
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
    expect(screen.queryByText('Alpha Research')).toBeNull();
  });

  // UX-36 / UX-44：页脚真实健康状态与按模式计数的口径
  it('reflects the real backend health in the footer', () => {
    const { rerender } = render(<Dashboard {...baseProps()} backendHealthy={false} />);
    expect(screen.getByText('后端未连接')).toBeDefined();
    expect(screen.getByText(/请确认应用已完全启动/)).toBeDefined();

    rerender(<Dashboard {...baseProps()} backendHealthy={true} />);
    expect(screen.getByText('后端已连接')).toBeDefined();
    expect(screen.getByText('2 / 2 篇文献')).toBeDefined();
  });
});

describe('Dashboard Processing Queue (UX-26)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders stage / progress / elapsed for active tasks', async () => {
    (api.getActiveTasks as any).mockResolvedValue([
      { ...mockDocs[0], ocr_status: 'processing', stage: 'OCR 第 3/10 页', progress: 42, elapsed: 95 },
    ]);

    render(<Dashboard {...baseProps()} />);

    expect(await screen.findByText('OCR 第 3/10 页')).toBeDefined();
    expect(screen.getByText('42%')).toBeDefined();
    expect(screen.getByText(/已用时 1 分 35 秒/)).toBeDefined();
    expect(screen.getByText('1 篇处理中')).toBeDefined();
  });

  it('cancels an active task and asks the parent to refresh', async () => {
    (api.getActiveTasks as any).mockResolvedValue([
      { ...mockDocs[0], ocr_status: 'processing', stage: '提取 Basic Insight', progress: 70, elapsed: 10 },
    ]);
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    fireEvent.click(await screen.findByLabelText('取消处理 Alpha Research'));

    await waitFor(() => {
      expect(api.cancelTask).toHaveBeenCalledWith(1);
    });
    expect(handlers.onRefresh).toHaveBeenCalled();
  });
});

describe('Dashboard Knowledge Claims (Phase 2)', () => {
  const claimResults = [
    {
      claim_id: 1,
      concept: 'trading bottleneck',
      quote: 'P2P 交易瓶颈在于各 agent 需顺序更新账本。',
      anchor: 'P2P 交易瓶颈在于各 agent 需顺序更新账本。',
      heading_path: 'Abstract',
      conflicting: 0,
      prompt_id: 'basic-insight-v1',
      doc_id: 1,
      title: 'Alpha Research',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getActiveTasks as any).mockResolvedValue([]);
    (api.searchKnowledge as any).mockResolvedValue({ results: [] });
    (api.ingestKnowledge as any).mockResolvedValue({ success: true, result: {} });
  });

  it('switches to the claims tab, searches, and renders claim cards', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    render(<Dashboard {...baseProps()} />);

    fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));

    fireEvent.change(screen.getByLabelText('检索知识库 claim'), { target: { value: '交易' } });
    fireEvent.click(screen.getByRole('button', { name: /^检索$/ }));

    await waitFor(() => {
      expect(screen.getByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。')).toBeDefined();
    });
    expect(api.searchKnowledge).toHaveBeenCalledWith('交易', 20);
    // T1 徽标（统一中文术语）与论文标题回填
    expect(screen.getByText('逐字引文')).toBeDefined();
    expect(screen.getByText('Alpha Research')).toBeDefined();
    // 论文库网格在 claims 模式不渲染
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('opens the claim source document in Reader on card click', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));
    fireEvent.change(screen.getByLabelText('检索知识库 claim'), { target: { value: '交易' } });
    fireEvent.click(screen.getByRole('button', { name: /^检索$/ }));

    const quote = await screen.findByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。');
    fireEvent.click(quote);

    expect(handlers.onSelectDoc).toHaveBeenCalledWith(mockDocs[0]);
  });

  it('ingests completed documents from the claims empty state', async () => {
    render(<Dashboard {...baseProps()} />);

    fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));
    fireEvent.click(screen.getByRole('button', { name: /摄入 2 篇文献/ }));

    await waitFor(() => {
      expect(api.ingestKnowledge).toHaveBeenCalledTimes(2);
    });
    expect(api.ingestKnowledge).toHaveBeenCalledWith(1);
    expect(api.ingestKnowledge).toHaveBeenCalledWith(2);
    expect(await screen.findByText(/已摄入 2 篇文献/)).toBeDefined();
  });

  it('shows a no-match state when the knowledge search returns nothing', async () => {
    render(<Dashboard {...baseProps()} />);

    fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));
    fireEvent.change(screen.getByLabelText('检索知识库 claim'), { target: { value: '不存在的词' } });
    fireEvent.click(screen.getByRole('button', { name: /^检索$/ }));

    expect(await screen.findByText(/没有匹配「不存在的词」的 claim/)).toBeDefined();
  });

  // UX-16：检索失败要与「无结果」区分，并提供重试
  it('shows an error state with retry when the knowledge search fails', async () => {
    (api.searchKnowledge as any).mockRejectedValueOnce(new Error('boom'));
    render(<Dashboard {...baseProps()} />);

    fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));
    fireEvent.change(screen.getByLabelText('检索知识库 claim'), { target: { value: '交易' } });
    fireEvent.click(screen.getByRole('button', { name: /^检索$/ }));

    expect(await screen.findByText('检索失败')).toBeDefined();
    expect(screen.getByRole('button', { name: /重试/ })).toBeDefined();

    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    fireEvent.click(screen.getByRole('button', { name: /重试/ }));

    expect(await screen.findByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。')).toBeDefined();
  });

  it('reports the claim count in the footer while in claims mode', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    render(<Dashboard {...baseProps()} />);

    fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));
    fireEvent.change(screen.getByLabelText('检索知识库 claim'), { target: { value: '交易' } });
    fireEvent.click(screen.getByRole('button', { name: /^检索$/ }));

    await waitFor(() => {
      expect(screen.getByText('1 条检索结果')).toBeDefined();
    });
  });
});
