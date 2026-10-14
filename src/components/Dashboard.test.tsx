import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Dashboard } from './Dashboard';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Document } from '../types';
import { api } from '../api/client';

// Mock the API client（claims 检索/摄入 + 原有轮询静默）
vi.mock('../api/client', () => ({
  api: {
    getActiveTasks: vi.fn().mockResolvedValue([]),
    syncWorkspace: vi.fn().mockResolvedValue({}),
    searchKnowledge: vi.fn().mockResolvedValue({ results: [] }),
    ingestKnowledge: vi.fn().mockResolvedValue({ success: true, result: {} }),
  }
}));

// Mock Document data with basic_insight_json
const mockDocs: Document[] = [
  {
    id: 1,
    filename: 'paper1.pdf',
    title: 'Alpha Research',
    authors: 'Alice',
    ocr_status: 'completed',
    ocr_markdown: 'Content 1',
    basic_insight_json: JSON.stringify({ journal_or_conference: 'Nature', date: '2023' }),
    added_at: new Date().toISOString()
  },
  {
    id: 2,
    filename: 'paper2.pdf',
    title: 'Beta Science',
    authors: 'Bob',
    ocr_status: 'completed',
    ocr_markdown: 'Content 2',
    basic_insight_json: JSON.stringify({ journal_or_conference: 'Science', date: '2024' }),
    added_at: new Date().toISOString()
  }
];

describe('Dashboard Filtering', () => {
  const mockHandlers = {
    onSelectDoc: vi.fn(),
    onUpload: vi.fn(),
    onDelete: vi.fn(),
    onReprocess: vi.fn(),
    isUploading: false
  };

  it('filters by search query (Title/Authors)', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    const searchInput = screen.getByPlaceholderText(/Search papers/);
    fireEvent.change(searchInput, { target: { value: 'Alpha' } });
    
    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('filters by Journal selection', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    const journalSelect = screen.getByDisplayValue('All Journals');
    fireEvent.change(journalSelect, { target: { value: 'Nature' } });
    
    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('filters by Year selection', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    const yearSelect = screen.getByDisplayValue('All Years');
    fireEvent.change(yearSelect, { target: { value: '2024' } });
    
    expect(screen.getByText('Beta Science')).toBeDefined();
    expect(screen.queryByText('Alpha Research')).toBeNull();
  });

  it('resets all filters when clicking the filter clear button', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    // Select a year first to make the "Clear Filters" button appear
    const yearSelect = screen.getByDisplayValue('All Years');
    fireEvent.change(yearSelect, { target: { value: '2024' } });
    
    const searchInput = screen.getByPlaceholderText(/Search papers/);
    fireEvent.change(searchInput, { target: { value: 'Non-existent' } });
    
    expect(screen.getByText('No intelligence matches your current filter.')).toBeDefined();
    
    const resetBtn = screen.getByTitle('Clear Filters');
    fireEvent.click(resetBtn);
    
    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.getByText('Beta Science')).toBeDefined();
  });

  it('mounts a hidden file input wired to the Import button', () => {
    // Regression: fileInputRef was declared but never mounted to an
    // <input type="file">, making the Import button a no-op.
    const handlers = {
      onSelectDoc: vi.fn(),
      onUpload: vi.fn(),
      onDelete: vi.fn(),
      onReprocess: vi.fn(),
      isUploading: false
    };
    const { container } = render(<Dashboard docs={mockDocs} {...handlers} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(fileInput).not.toBeNull();
    expect(fileInput!.accept).toBe('.pdf,.tex,.zip');

    // Import button click must trigger the hidden input's click
    const clickSpy = vi.spyOn(fileInput!, 'click');
    fireEvent.click(screen.getByText('Import PDF / LaTeX'));
    expect(clickSpy).toHaveBeenCalled();

    // Selecting a file must invoke onUpload with that file
    const file = new File(['dummy'], 'paper.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput!, { target: { files: [file] } });
    expect(handlers.onUpload).toHaveBeenCalledWith(file);
  });
});

describe('Dashboard Knowledge Claims (Phase 2)', () => {
  const mockHandlers = {
    onSelectDoc: vi.fn(),
    onUpload: vi.fn(),
    onDelete: vi.fn(),
    onReprocess: vi.fn(),
    isUploading: false
  };

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
      title: 'Alpha Research'
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getActiveTasks as any).mockResolvedValue([]);
    (api.searchKnowledge as any).mockResolvedValue({ results: [] });
    (api.ingestKnowledge as any).mockResolvedValue({ success: true, result: {} });
  });

  it('switches to the Claims tab, searches, and renders claim cards', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);

    fireEvent.click(screen.getByText('Knowledge Claims'));

    const input = screen.getByPlaceholderText(/Search claims/);
    fireEvent.change(input, { target: { value: '交易' } });
    fireEvent.click(screen.getByText('Search Claims'));

    await waitFor(() => {
      expect(screen.getByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。')).toBeDefined();
    });
    expect(api.searchKnowledge).toHaveBeenCalledWith('交易', 20);
    // T1 徽标与论文标题回填
    expect(screen.getByText('T1 verbatim')).toBeDefined();
    expect(screen.getByText('Alpha Research')).toBeDefined();
    // 论文库网格在 claims 模式不渲染（卡片标题消失；标签页仍可见）
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('opens the claim source document in Reader on card click', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    const handlers = { ...mockHandlers, onSelectDoc: vi.fn() };
    render(<Dashboard docs={mockDocs} {...handlers} />);

    fireEvent.click(screen.getByText('Knowledge Claims'));
    fireEvent.change(screen.getByPlaceholderText(/Search claims/), { target: { value: '交易' } });
    fireEvent.click(screen.getByText('Search Claims'));

    await waitFor(() => {
      expect(screen.getByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。')).toBeDefined();
    });
    fireEvent.click(screen.getByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。'));

    // 点击 claim 卡片 → 用 doc_id 回填定位文档 → 进 Reader
    expect(handlers.onSelectDoc).toHaveBeenCalledWith(mockDocs[0]);
  });

  it('ingests completed documents from the claims empty state', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);

    fireEvent.click(screen.getByText('Knowledge Claims'));
    fireEvent.click(screen.getByText(/Ingest 2 Documents/));

    await waitFor(() => {
      expect(api.ingestKnowledge).toHaveBeenCalledTimes(2);
    });
    expect(api.ingestKnowledge).toHaveBeenCalledWith(1);
    expect(api.ingestKnowledge).toHaveBeenCalledWith(2);
    expect(screen.getByText(/已摄入 2 篇文档/)).toBeDefined();
  });

  it('shows no-match state when the knowledge search returns nothing', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: [] });
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);

    fireEvent.click(screen.getByText('Knowledge Claims'));
    fireEvent.change(screen.getByPlaceholderText(/Search claims/), { target: { value: '不存在的词' } });
    fireEvent.click(screen.getByText('Search Claims'));

    await waitFor(() => {
      expect(screen.getByText(/No claims match/)).toBeDefined();
    });
  });
});
