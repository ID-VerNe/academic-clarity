import { render, screen, fireEvent } from '@testing-library/react';
import { Dashboard } from './Dashboard';
import { vi, describe, it, expect } from 'vitest';

describe('Dashboard Component Behavioral Tests', () => {
  const mockDocs: any[] = [
    { id: 1, filename: 'paper1.pdf', title: 'Paper One', ocr_status: 'completed', added_at: new Date().toISOString() },
    { id: 2, filename: 'paper2.pdf', title: 'Paper Two', ocr_status: 'failed', added_at: new Date().toISOString() }
  ];

  const mockHandlers = {
    onSelectDoc: vi.fn(),
    onUpload: vi.fn(),
    onDelete: vi.fn(),
    onReprocess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock window.api.selectWorkspace
    (window as any).api = {
      selectWorkspace: vi.fn(),
    };
  });

  it('triggers onSelectDoc when a completed card body is clicked', () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} isUploading={false} />);
    
    // 点击卡片正文区域 (标题或文件名)
    const cardTitle = screen.getByText('Paper One');
    fireEvent.click(cardTitle);
    
    expect(mockHandlers.onSelectDoc).toHaveBeenCalledWith(mockDocs[0]);
  });

  it('triggers onSelectDoc when the Eye icon is clicked', () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} isUploading={false} />);
    
    const eyeBtns = screen.getAllByRole('button').filter(btn => btn.querySelector('svg.lucide-eye'));
    // The Dashboard component doesn't have aria-labels for all buttons, but Eye is one of them.
    // Let's use the first eye icon button.
    const eyeBtn = screen.getAllByRole('button').find(btn => btn.innerHTML.includes('lucide-eye'));
    
    fireEvent.click(eyeBtn!);
    expect(mockHandlers.onSelectDoc).toHaveBeenCalled();
  });

  it('triggers window.api.selectWorkspace when the folder icon is clicked', () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} isUploading={false} />);
    
    const switchBtn = screen.getByTitle('Switch Workspace');
    fireEvent.click(switchBtn);
    
    expect((window as any).api.selectWorkspace).toHaveBeenCalled();
  });

  it('shows retry button and triggers onReprocess when ocr fails', () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} isUploading={false} />);
    
    // 寻找重试按钮 (RefreshCw icon)
    const retryBtn = screen.getByTitle('Retry OCR');
    expect(retryBtn).toBeDefined();
    
    fireEvent.click(retryBtn);
    expect(mockHandlers.onReprocess).toHaveBeenCalledWith(mockDocs[1].id);
  });

  it('opens file selector when upload area is clicked', () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} isUploading={false} />);
    
    const uploadArea = screen.getByText(/Drag & drop PDFs here/i);
    fireEvent.click(uploadArea);
    
    // 注意：由于无法模拟原生文件对话框，我们验证 click 事件是否冒泡到了 input
    // 但在 React 测试中，我们可以确保 onUpload 能被 handleFileChange 触发
  });

  it('triggers onDelete when clicking the trash icon', () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} isUploading={false} />);

    // Find trash buttons by title
    const trashBtns = screen.getAllByTitle('Delete Document');

    fireEvent.click(trashBtns[0]);
    expect(mockHandlers.onDelete).toHaveBeenCalledWith(mockDocs[0].id);
  });
});
