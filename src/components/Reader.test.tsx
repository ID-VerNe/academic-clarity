import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Reader } from './Reader';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { api } from '../api/client';

// Mock the API client
vi.mock('../api/client', () => ({
  api: {
    getPdfUrl: vi.fn().mockResolvedValue('http://example.com/test.pdf'),
    chat: vi.fn(),
    searchKnowledge: vi.fn().mockResolvedValue({ results: [] }),
    getMetadata: vi.fn().mockResolvedValue([]),
    extractMetadata: vi.fn(),
  }
}));

describe('Reader Component', () => {
  const mockDoc: any = {
    id: 1,
    title: 'Test Paper',
    filename: 'test.pdf',
    authors: 'John Doe',
    ocr_markdown: '# Content',
    ocr_status: 'completed',
    added_at: new Date().toISOString()
  };

  const mockProps = {
    doc: mockDoc,
    onBack: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    window.innerWidth = 1200;
  });

  it('toggles left structure panel when the chevron button is clicked', async () => {
    render(<Reader {...mockProps} />);
    expect(screen.getByText('Structure')).toBeDefined();
    
    const toggleBtn = screen.getByLabelText('Toggle Left Sidebar');
    fireEvent.click(toggleBtn);
    
    await waitFor(() => {
      expect(screen.queryByText('Structure')).toBeNull();
    });
    
    fireEvent.click(toggleBtn);
    expect(screen.getByText('Structure')).toBeDefined();
  });

  it('detects left sidebar resizing via mouse dragging', async () => {
    render(<Reader {...mockProps} />);
    
    const handle = screen.getByTestId('resize-handle-left');
    
    // Simulate resizing to collapse
    fireEvent.mouseDown(handle);
    fireEvent.mouseMove(document, { clientX: 50 });
    fireEvent.mouseUp(document);
    
    await waitFor(() => {
      expect(screen.queryByText('Structure')).toBeNull();
    });
  });

  it('defaults to markdown view for .tex documents (no PDF pane)', () => {
    render(<Reader {...mockProps} doc={{ ...mockDoc, filename: 'paper.tex' }} />);
    // PdfViewer 会对 .tex 请求 /pdf（server 对非 pdf 返回 404），
    // 故 .tex/.zip 文档默认纯 Markdown 视图，PDF 窗格整体不挂载：
    // 无 "Streaming PDF Bytes..."（加载态）也无 "Failed to load PDF content."（错误态）。
    expect(screen.queryByText('Streaming PDF Bytes...')).toBeNull();
    expect(screen.queryByText('Failed to load PDF content.')).toBeNull();
    // markdown 内容正常渲染
    expect(screen.getByText('Content')).toBeDefined();
  });

  // ── Phase 2：引用模式（知识库引文 → LLM） ──────────────

  it('quote mode: searches the knowledge base and sends only this doc quotes to the LLM', async () => {
    (api.searchKnowledge as any).mockResolvedValue({
      results: [
        { claim_id: 1, quote: 'P2P 交易瓶颈在于各 agent 需顺序更新账本。', doc_id: 1 },
        { claim_id: 2, quote: '另一篇论文的引文', doc_id: 2 },
      ]
    });
    (api.chat as any).mockResolvedValue({ response: 'AI answer' });

    render(<Reader {...mockProps} />);

    // 开启引用模式（开关在 ChatSidebar 输入区上方）
    fireEvent.click(screen.getByLabelText('Toggle Quote Mode'));

    const input = screen.getByPlaceholderText(/Quote mode/i);
    fireEvent.change(input, { target: { value: '交易瓶颈' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    // 先检索（limit 20），只把本文档的引文喂给 LLM
    await waitFor(() => {
      expect(api.searchKnowledge).toHaveBeenCalledWith('交易瓶颈', 20);
    });
    await waitFor(() => {
      expect(api.chat).toHaveBeenCalledWith(1, '交易瓶颈',
        ['P2P 交易瓶颈在于各 agent 需顺序更新账本。']);
    });
    await waitFor(() => {
      expect(screen.getByText('AI answer')).toBeDefined();
    });
  });

  it('quote mode: no citation hits -> LLM not called, hint shown', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: [] });
    (api.chat as any).mockResolvedValue({ response: 'should not happen' });

    render(<Reader {...mockProps} />);
    fireEvent.click(screen.getByLabelText('Toggle Quote Mode'));

    const input = screen.getByPlaceholderText(/Quote mode/i);
    fireEvent.change(input, { target: { value: '交易瓶颈' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/未找到可引用段落/)).toBeDefined();
    });
    expect(api.chat).not.toHaveBeenCalled();
  });
});
