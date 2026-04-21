import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Dashboard } from './Dashboard';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { api } from '../api/client';

// 深度 Mock API Client
vi.mock('../api/client', () => ({
  api: {
    syncWorkspace: vi.fn().mockResolvedValue({ success: true }),
    getDocuments: vi.fn().mockResolvedValue([]),
    getActiveTasks: vi.fn().mockResolvedValue([
      { id: 101, filename: 'processing_paper.pdf', ocr_status: 'processing' }
    ]),
    uploadDocument: vi.fn().mockResolvedValue({ success: true }),
  }
}));

describe('Dashboard Deep Behavioral Tests', () => {
  const mockHandlers = {
    onSelectDoc: vi.fn(),
    onUpload: vi.fn(),
    onDelete: vi.fn(),
    onReprocess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (window as any).api = {
      selectWorkspace: vi.fn(),
      getPythonPort: vi.fn().mockResolvedValue(38391),
    };
  });

  it('renders active task queue from API and shows processing status', async () => {
    render(<Dashboard docs={[]} {...mockHandlers} isUploading={false} />);
    
    // 验证是否出现了“Processing Queue”面板
    await waitFor(() => {
      expect(screen.getByText('Processing Queue')).toBeDefined();
      expect(screen.getByText('processing_paper.pdf')).toBeDefined();
    });
  });

  it('triggers full workspace sync when refresh button is clicked', async () => {
    render(<Dashboard docs={[]} {...mockHandlers} isUploading={false} />);
    
    const syncBtn = screen.getByTitle('Sync Workspace & Trigger OCR');
    fireEvent.click(syncBtn);
    
    expect(api.syncWorkspace).toHaveBeenCalled();
  });

  it('shows distinctive upload status when isUploading is true', () => {
    render(<Dashboard docs={[]} {...mockHandlers} isUploading={true} />);
    
    expect(screen.getByText(/Injecting document into researcher pipeline/i)).toBeDefined();
    // 寻找具有 dashed 边框的上传区域容器
    const uploadArea = screen.getByText(/Injecting document into researcher pipeline/i).closest('.border-dashed');
    expect(uploadArea?.className).toContain('cursor-wait');
  });

  it('displays correct icon and color for completed vs processing documents', () => {
    const mixedDocs: any[] = [
      { id: 1, filename: 'done.pdf', ocr_status: 'completed', added_at: new Date().toISOString() },
      { id: 2, filename: 'busy.pdf', ocr_status: 'processing', added_at: new Date().toISOString() }
    ];
    
    render(<Dashboard docs={mixedDocs} {...mockHandlers} isUploading={false} />);
    
    const completedBadge = screen.getByText('completed');
    expect(completedBadge.className).toContain('bg-emerald-50');
    
    const processingBadge = screen.getByText('processing');
    expect(processingBadge.className).toContain('bg-amber-50');
  });
});
