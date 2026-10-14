import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Reader } from './Reader';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the API client
vi.mock('../api/client', () => ({
  api: {
    getPdfUrl: vi.fn().mockResolvedValue('http://example.com/test.pdf'),
    chat: vi.fn(),
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
});
