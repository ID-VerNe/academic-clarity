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
  },
}));

describe('Reader Component', () => {
  const mockDoc: any = {
    id: 1,
    title: 'Test Paper',
    filename: 'test.pdf',
    authors: 'John Doe',
    ocr_markdown: '# Content',
    ocr_status: 'completed',
    added_at: new Date().toISOString(),
  };

  const mockProps = {
    doc: mockDoc,
    onBack: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    window.innerWidth = 1200;
    localStorage.clear();
  });

  it('toggles the left outline panel when the chevron button is clicked', async () => {
    render(<Reader {...mockProps} />);
    expect(screen.getByText('文档目录')).toBeDefined();

    const toggleBtn = screen.getByLabelText(/^(收起|展开)目录栏$/);
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(screen.queryByText('文档目录')).toBeNull();
    });

    fireEvent.click(screen.getByLabelText(/^(收起|展开)目录栏$/));
    expect(screen.getByText('文档目录')).toBeDefined();
  });

  it('detects left sidebar resizing via mouse dragging', async () => {
    render(<Reader {...mockProps} />);

    const handle = screen.getByTestId('resize-handle-left');

    // Simulate resizing to collapse
    fireEvent.mouseDown(handle);
    fireEvent.mouseMove(document, { clientX: 50 });
    fireEvent.mouseUp(document);

    await waitFor(() => {
      expect(screen.queryByText('文档目录')).toBeNull();
    });
  });

  it('defaults to markdown view for .tex documents (no PDF pane)', () => {
    render(<Reader {...mockProps} doc={{ ...mockDoc, filename: 'paper.tex' }} />);
    // PdfViewer 会对 .tex 请求 /pdf（server 对非 pdf 返回 404），
    // 故 .tex/.zip 文档默认纯 Markdown 视图，PDF 窗格整体不挂载：
    // 无「正在加载 PDF…」（加载态）也无「PDF 加载失败」（错误态）。
    expect(screen.queryByText('正在加载 PDF…')).toBeNull();
    expect(screen.queryByText('PDF 加载失败')).toBeNull();
    // markdown 内容正常渲染
    expect(screen.getByRole('heading', { name: 'Content' })).toBeDefined();
  });

  // UX-05：目录从文档结构动态生成并可定位正文
  it('builds the outline from the document and scrolls to a heading on click', () => {
    const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView');
    render(
      <Reader
        {...mockProps}
        doc={{ ...mockDoc, ocr_markdown: '# Introduction\n\ntext\n\n## Method\n\nmore' }}
      />
    );

    // 目录项（1 个 H1 + 1 个 H2）
    const outlineItem = screen.getByRole('button', { name: /Introduction/ });
    fireEvent.click(outlineItem);

    expect(scrollSpy).toHaveBeenCalled();
    scrollSpy.mockRestore();
  });

  it('shows an honest empty outline when the document has no structure', () => {
    render(<Reader {...mockProps} doc={{ ...mockDoc, ocr_markdown: 'plain text only' }} />);

    expect(screen.getByText(/还没有可用的结构信息/)).toBeDefined();
  });

  // UX-19：会话按文档持久化
  it('restores the persisted conversation for this document', () => {
    localStorage.setItem('ac:chat:1', JSON.stringify([{ role: 'user', content: '之前问过的问题' }]));

    render(<Reader {...mockProps} />);

    expect(screen.getByText('之前问过的问题')).toBeDefined();
  });

  // ── Phase 2：引用模式（知识库引文 → LLM） ──────────────

  it('quote mode: searches the knowledge base and sends only this doc quotes to the LLM', async () => {
    (api.searchKnowledge as any).mockResolvedValue({
      results: [
        { claim_id: 1, quote: 'P2P 交易瓶颈在于各 agent 需顺序更新账本。', doc_id: 1 },
        { claim_id: 2, quote: '另一篇论文的引文', doc_id: 2 },
      ],
    });
    (api.chat as any).mockResolvedValue({ response: 'AI answer' });

    render(<Reader {...mockProps} />);

    // 开启引用模式（开关在 ChatSidebar 输入区上方）
    fireEvent.click(screen.getByLabelText('切换引用模式'));

    const input = screen.getByPlaceholderText(/基于引文提问/);
    fireEvent.change(input, { target: { value: '交易瓶颈' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    // 先检索（limit 20），只把本文档的引文喂给 LLM
    await waitFor(() => {
      expect(api.searchKnowledge).toHaveBeenCalledWith('交易瓶颈', 20);
    });
    await waitFor(() => {
      expect(api.chat).toHaveBeenCalledWith(1, '交易瓶颈', ['P2P 交易瓶颈在于各 agent 需顺序更新账本。']);
    });
    await waitFor(() => {
      expect(screen.getByText('AI answer')).toBeDefined();
    });
  });

  it('quote mode: no citation hits -> LLM not called, hint shown', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: [] });
    (api.chat as any).mockResolvedValue({ response: 'should not happen' });

    render(<Reader {...mockProps} />);
    fireEvent.click(screen.getByLabelText('切换引用模式'));

    const input = screen.getByPlaceholderText(/基于引文提问/);
    fireEvent.change(input, { target: { value: '交易瓶颈' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/没有找到可引用段落/)).toBeDefined();
    });
    expect(api.chat).not.toHaveBeenCalled();
  });

  // UX-18：连接失败给出可操作指引，并把问题放回输入框便于重试
  it('chat failure: explains what to do and keeps the question for retry', async () => {
    (api.chat as any).mockRejectedValue(new Error('boom'));

    render(<Reader {...mockProps} />);

    const input = screen.getByPlaceholderText(/针对本文档提问/);
    fireEvent.change(input, { target: { value: '这篇论文讲了什么？' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/无法连接后端服务/)).toBeDefined();
    });
    expect(screen.getByText(/问题已放回输入框/)).toBeDefined();
  });

  // 划词工具条：复制 / 引用到提问
  it('offers copy + quote actions when text is selected in the document', async () => {
    render(<Reader {...mockProps} doc={{ ...mockDoc, ocr_markdown: '# Content\n\n可被选中的段落文本。' }} />);

    const paragraph = screen.getByText(/可被选中的段落文本/);
    const range = document.createRange();
    range.selectNodeContents(paragraph);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);

    fireEvent.mouseUp(paragraph);

    const copyBtn = await screen.findByText('复制');
    expect(copyBtn).toBeDefined();
    expect(screen.getByText('引用到提问')).toBeDefined();

    fireEvent.click(screen.getByText('引用到提问'));

    // 引用后进入提问框（> 前缀的引用块）
    await waitFor(() => {
      const input = screen.getByLabelText('向文档提问') as HTMLInputElement;
      expect(input.value).toContain('可被选中的段落文本');
    });
  });
});
