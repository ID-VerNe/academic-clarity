import { render, screen, fireEvent } from '@testing-library/react';
import { ReaderToolbar } from './ReaderToolbar';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('ReaderToolbar Component', () => {
  const mockHandlers = {
    onBack: vi.fn(),
    setViewMode: vi.fn(),
    onAnalyze: vi.fn(),
  };

  const renderToolbar = () =>
    render(
      <ReaderToolbar
        onBack={mockHandlers.onBack}
        viewMode="split"
        setViewMode={mockHandlers.setViewMode}
        title="Test Paper"
        onAnalyze={mockHandlers.onAnalyze}
      />
    );

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('triggers onBack when the back button is clicked', () => {
    renderToolbar();

    fireEvent.click(screen.getByLabelText('返回文献库'));

    expect(mockHandlers.onBack).toHaveBeenCalled();
  });

  it('shows the document title', () => {
    renderToolbar();

    expect(screen.getByText('Test Paper')).toBeDefined();
  });

  it('switches view modes and calls setViewMode', () => {
    renderToolbar();

    fireEvent.click(screen.getByLabelText('只显示 PDF 原页'));
    expect(mockHandlers.setViewMode).toHaveBeenCalledWith('pdf');

    fireEvent.click(screen.getByLabelText('只显示识别文本'));
    expect(mockHandlers.setViewMode).toHaveBeenCalledWith('markdown');
  });

  // UX-04：AI 分析不再是死控件
  it('wires the primary CTA to onAnalyze', () => {
    renderToolbar();

    fireEvent.click(screen.getByRole('button', { name: /AI 分析/ }));

    expect(mockHandlers.onAnalyze).toHaveBeenCalled();
  });

  // UX-04：未实现的书签按钮已移除，不再出现死控件
  it('no longer renders the dead bookmark control', () => {
    renderToolbar();

    expect(screen.queryByLabelText(/Bookmark/)).toBeNull();
  });
});
