import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Reader } from './Reader';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { api } from '../api/client';

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
  });

  it('toggles left structure panel when the chevron button is clicked', async () => {
    render(<Reader {...mockProps} />);
    
    // Initially, "Structure" label should be visible
    expect(screen.getByText('Structure')).toBeDefined();
    
    const toggleBtn = screen.getByLabelText('Toggle Left Sidebar');
    fireEvent.click(toggleBtn);
    
    // After clicking, "Structure" label should be gone
    await waitFor(() => {
      expect(screen.queryByText('Structure')).toBeNull();
    });
    
    // Click again to expand
    fireEvent.click(toggleBtn);
    expect(screen.getByText('Structure')).toBeDefined();
  });
});
