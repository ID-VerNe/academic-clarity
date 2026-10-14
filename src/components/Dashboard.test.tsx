import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Dashboard } from './Dashboard';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Document } from '../types';

// Mock Document data with basic_insight_json
const mockDocs: Document[] = [
  {
    id: 1,
    filename: 'paper1.pdf',
    title: 'Alpha Research',
    authors: 'Alice',
    ocr_status: 'completed',
    ocr_markdown: 'Content 1',
    basic_insight_json: JSON.stringify({ journal_or_conference: 'Nature', date: '2023' }),
    added_at: new Date().toISOString()
  },
  {
    id: 2,
    filename: 'paper2.pdf',
    title: 'Beta Science',
    authors: 'Bob',
    ocr_status: 'completed',
    ocr_markdown: 'Content 2',
    basic_insight_json: JSON.stringify({ journal_or_conference: 'Science', date: '2024' }),
    added_at: new Date().toISOString()
  }
];

describe('Dashboard Filtering', () => {
  const mockHandlers = {
    onSelectDoc: vi.fn(),
    onUpload: vi.fn(),
    onDelete: vi.fn(),
    onReprocess: vi.fn(),
    isUploading: false
  };

  it('filters by search query (Title/Authors)', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    const searchInput = screen.getByPlaceholderText(/Search papers/);
    fireEvent.change(searchInput, { target: { value: 'Alpha' } });
    
    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('filters by Journal selection', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    const journalSelect = screen.getByDisplayValue('All Journals');
    fireEvent.change(journalSelect, { target: { value: 'Nature' } });
    
    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('filters by Year selection', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    const yearSelect = screen.getByDisplayValue('All Years');
    fireEvent.change(yearSelect, { target: { value: '2024' } });
    
    expect(screen.getByText('Beta Science')).toBeDefined();
    expect(screen.queryByText('Alpha Research')).toBeNull();
  });

  it('resets all filters when clicking the filter clear button', async () => {
    render(<Dashboard docs={mockDocs} {...mockHandlers} />);
    
    // Select a year first to make the "Clear Filters" button appear
    const yearSelect = screen.getByDisplayValue('All Years');
    fireEvent.change(yearSelect, { target: { value: '2024' } });
    
    const searchInput = screen.getByPlaceholderText(/Search papers/);
    fireEvent.change(searchInput, { target: { value: 'Non-existent' } });
    
    expect(screen.getByText('No intelligence matches your current filter.')).toBeDefined();
    
    const resetBtn = screen.getByTitle('Clear Filters');
    fireEvent.click(resetBtn);
    
    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.getByText('Beta Science')).toBeDefined();
  });

  it('mounts a hidden file input wired to the Import button', () => {
    // Regression: fileInputRef was declared but never mounted to an
    // <input type="file">, making the Import button a no-op.
    const handlers = {
      onSelectDoc: vi.fn(),
      onUpload: vi.fn(),
      onDelete: vi.fn(),
      onReprocess: vi.fn(),
      isUploading: false
    };
    const { container } = render(<Dashboard docs={mockDocs} {...handlers} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(fileInput).not.toBeNull();
    expect(fileInput!.accept).toBe('.pdf,.tex,.zip');

    // Import button click must trigger the hidden input's click
    const clickSpy = vi.spyOn(fileInput!, 'click');
    fireEvent.click(screen.getByText('Import PDF / LaTeX'));
    expect(clickSpy).toHaveBeenCalled();

    // Selecting a file must invoke onUpload with that file
    const file = new File(['dummy'], 'paper.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput!, { target: { files: [file] } });
    expect(handlers.onUpload).toHaveBeenCalledWith(file);
  });
});
