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
});
