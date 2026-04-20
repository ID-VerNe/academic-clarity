import { render, screen, fireEvent } from '@testing-library/react';
import { ReaderToolbar } from './ReaderToolbar';
import { vi, describe, it, expect } from 'vitest';

describe('ReaderToolbar Component', () => {
  const mockHandlers = {
    onBack: vi.fn(),
    setViewMode: vi.fn(),
  };

  it('triggers onBack when Back button is clicked', () => {
    render(
      <ReaderToolbar 
        onBack={mockHandlers.onBack} 
        viewMode="split" 
        setViewMode={mockHandlers.setViewMode} 
        title="Test Paper" 
      />
    );
    
    const backBtn = screen.getByText('Library').closest('button');
    fireEvent.click(backBtn!);
    
    expect(mockHandlers.onBack).toHaveBeenCalled();
  });

  it('switches view modes and calls setViewMode', () => {
    render(
      <ReaderToolbar 
        onBack={mockHandlers.onBack} 
        viewMode="split" 
        setViewMode={mockHandlers.setViewMode} 
        title="Test Paper" 
      />
    );
    
    const pdfBtn = screen.getByText('pdf');
    const markdownBtn = screen.getByText('markdown');
    
    fireEvent.click(pdfBtn);
    expect(mockHandlers.setViewMode).toHaveBeenCalledWith('pdf');
    
    fireEvent.click(markdownBtn);
    expect(mockHandlers.setViewMode).toHaveBeenCalledWith('markdown');
  });
});
