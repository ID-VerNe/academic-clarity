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

describe('Dashboard Three-Color Status Tests', () => {
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

  it('displays emerald "completed" badge when both markdown and metadata exist', () => {
    const doc: any = { 
      id: 1, 
      filename: 'done.pdf', 
      ocr_markdown: 'Full text here', 
      metadata_json: '{"title": "x"}',
      ocr_status: 'completed',
      added_at: new Date().toISOString() 
    };
    render(<Dashboard docs={[doc]} {...mockHandlers} isUploading={false} />);
    
    const badge = screen.getByText('completed');
    expect(badge.className).toContain('bg-emerald-50');
  });

  it('displays amber "OCR READY" badge when markdown exists but metadata is missing', () => {
    const doc: any = { 
      id: 1, 
      filename: 'ocr_only.pdf', 
      ocr_markdown: 'Full text here', 
      metadata_json: null,
      ocr_status: 'completed',
      added_at: new Date().toISOString() 
    };
    render(<Dashboard docs={[doc]} {...mockHandlers} isUploading={false} />);
    
    expect(screen.getByText('OCR READY')).toBeDefined();
    const badge = screen.getByText('OCR READY');
    expect(badge.className).toContain('bg-amber-50');
  });

  it('displays rose "failed" badge when no markdown exists', () => {
    const doc: any = { 
      id: 1, 
      filename: 'broken.pdf', 
      ocr_markdown: null, 
      ocr_status: 'failed',
      added_at: new Date().toISOString() 
    };
    render(<Dashboard docs={[doc]} {...mockHandlers} isUploading={false} />);
    
    const badge = screen.getByText('failed');
    expect(badge.className).toContain('bg-rose-50');
  });

  it('triggers full AI reprocess when Refresh button on card is clicked', () => {
    const doc: any = { 
      id: 1, 
      filename: 'test.pdf', 
      ocr_status: 'failed',
      added_at: new Date().toISOString() 
    };
    render(<Dashboard docs={[doc]} {...mockHandlers} isUploading={false} />);
    
    const retryBtn = screen.getByTitle('Retry All AI Steps');
    fireEvent.click(retryBtn);
    expect(mockHandlers.onReprocess).toHaveBeenCalledWith(doc.id);
  });
});
