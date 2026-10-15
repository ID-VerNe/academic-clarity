import { render, screen, fireEvent, waitForElementToBeRemoved } from '@testing-library/react';
import { ChatSidebar } from './ChatSidebar';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the API client
vi.mock('../../api/client', () => ({
  api: {
    getMetadata: vi.fn().mockResolvedValue([]),
    extractMetadata: vi.fn(),
  },
}));

const baseProps = () => ({
  docId: 1,
  collapsed: false,
  chatHistory: [] as { role: 'user' | 'ai'; content: string }[],
  chatQuery: '',
  isTyping: false,
  setCollapsed: vi.fn(),
  setChatQuery: vi.fn(),
  onSendMessage: vi.fn(),
  onClearHistory: vi.fn(),
});

describe('ChatSidebar Behavioral Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('toggles collapse state when chevron is clicked', () => {
    render(<ChatSidebar {...baseProps()} />);

    fireEvent.click(screen.getByLabelText('收起右侧栏'));

    expect(baseProps().setCollapsed).toBeDefined();
  });

  it('uses consistent arrow semantics for the collapsed state', () => {
    const handlers = baseProps();
    const { rerender } = render(<ChatSidebar {...handlers} collapsed={false} />);
    expect(screen.getByLabelText('收起右侧栏')).toBeDefined();

    rerender(<ChatSidebar {...handlers} collapsed={true} />);
    const expandBtn = screen.getByLabelText('展开右侧栏');
    fireEvent.click(expandBtn);
    expect(handlers.setCollapsed).toHaveBeenCalledWith(false);
  });

  it('triggers onSendMessage when Send button is clicked', () => {
    const handlers = baseProps();
    render(<ChatSidebar {...handlers} chatQuery="Summarize please" />);

    fireEvent.click(screen.getByLabelText('发送'));

    expect(handlers.onSendMessage).toHaveBeenCalled();
  });

  it('shows the extraction form when the + button is clicked and closes on X', async () => {
    render(<ChatSidebar {...baseProps()} />);

    fireEvent.click(screen.getByLabelText('新增提取维度并立即提取'));

    // UX-33：与设置页「新建维度」区分命名
    expect(screen.getByText('立即提取（仅本文档）')).toBeDefined();

    fireEvent.click(screen.getByLabelText('关闭提取表单'));

    await waitForElementToBeRemoved(() => screen.queryByText('立即提取（仅本文档）'));
  });

  it('triggers setChatQuery when typing in the input', () => {
    const handlers = baseProps();
    render(<ChatSidebar {...handlers} />);

    fireEvent.change(screen.getByLabelText('向文档提问'), { target: { value: 'Hello' } });

    expect(handlers.setChatQuery).toHaveBeenCalledWith('Hello');
  });

  it('triggers onSendMessage when Enter is pressed in the input', () => {
    const handlers = baseProps();
    render(<ChatSidebar {...handlers} chatQuery="Some query" />);

    fireEvent.keyDown(screen.getByLabelText('向文档提问'), { key: 'Enter', code: 'Enter' });

    expect(handlers.onSendMessage).toHaveBeenCalled();
  });

  // UX-17：中文输入法选词回车不发送
  it('does not send while an IME composition is active', () => {
    const handlers = baseProps();
    render(<ChatSidebar {...handlers} chatQuery="中文问题" />);

    fireEvent.keyDown(screen.getByLabelText('向文档提问'), { key: 'Enter', isComposing: true });

    expect(handlers.onSendMessage).not.toHaveBeenCalled();
  });

  // UX-07：LLM 多段回答必须保留换行
  it('preserves newlines in AI messages', () => {
    const handlers = baseProps();
    handlers.chatHistory = [{ role: 'ai', content: '第一段\n第二段\n第三段' }];
    render(<ChatSidebar {...handlers} />);

    const bubble = screen.getByText(/第一段/);
    expect(bubble.className).toContain('whitespace-pre-wrap');
  });

  // UX-22：空闲态不再显示误导性的 "Synthesizing..."
  it('shows an honest empty state for the chat tab', () => {
    render(<ChatSidebar {...baseProps()} />);

    expect(screen.getByText('针对本文档提问')).toBeDefined();
    expect(screen.queryByText(/Synthesizing/)).toBeNull();
  });

  it('clears the conversation from the header action', () => {
    const handlers = baseProps();
    handlers.chatHistory = [{ role: 'user', content: 'hi' }];
    render(<ChatSidebar {...handlers} />);

    fireEvent.click(screen.getByLabelText('清空对话'));

    expect(handlers.onClearHistory).toHaveBeenCalled();
  });

  // UX-46：洞察与对话改为标签页，避免嵌套滚动
  it('switches between the chat and insight tabs', () => {
    render(<ChatSidebar {...baseProps()} />);

    expect(screen.getByLabelText('向文档提问')).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: /洞察/ }));

    expect(screen.getByText('暂无洞察')).toBeDefined();
    expect(screen.queryByLabelText('向文档提问')).toBeNull();
  });

  it('Phase 2: toggles quote mode, explains it, and switches the placeholder', () => {
    const setCiteMode = vi.fn();
    const handlers = { ...baseProps(), setCiteMode };

    // 关闭态：点击 → 请求开启，并给出后果说明
    const { rerender } = render(<ChatSidebar {...handlers} citeMode={false} />);
    expect(screen.getByText(/关闭：把整篇 OCR 全文发给 AI/)).toBeDefined();
    fireEvent.click(screen.getByLabelText('切换引用模式'));
    expect(setCiteMode).toHaveBeenCalledWith(true);

    // 开启态：占位符切换为引用模式提示，再点击 → 请求关闭
    rerender(<ChatSidebar {...handlers} citeMode={true} />);
    expect(screen.getByText(/开启：只把知识库中的逐字引文发给 AI/)).toBeDefined();
    expect(screen.getByPlaceholderText(/基于引文提问/)).toBeDefined();
    fireEvent.click(screen.getByLabelText('切换引用模式'));
    expect(setCiteMode).toHaveBeenCalledWith(false);
  });
});
