import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MetadataPanel } from './MetadataPanel';
import { describe, it, expect } from 'vitest';
import React from 'react';

describe('MetadataPanel Component', () => {
  const nestedData = JSON.stringify({
    title: "Deep Learning",
    authors: ["John Doe", "Jane Smith"],
    details: {
      year: 2024,
      venue: {
        name: "CVPR",
        location: "Seattle"
      }
    }
  });

  it('renders nested JSON data recursively', () => {
    render(<MetadataPanel data={nestedData} label="Test Insight" />);
    
    expect(screen.getByText('Deep Learning')).toBeDefined();
    expect(screen.getByText('John Doe')).toBeDefined();
    expect(screen.getByText('Jane Smith')).toBeDefined();
    expect(screen.getByText('2024')).toBeDefined();
    expect(screen.getByText('CVPR')).toBeDefined();
    expect(screen.getByText('Seattle')).toBeDefined();
  });

  it('toggles open/close state when clicking chevron', async () => {
    render(<MetadataPanel data={nestedData} label="Test Insight" />);
    
    // "details" is an object, so it should have a toggle button
    const detailsBtn = screen.getByText(/details/i).closest('button');
    expect(detailsBtn).toBeDefined();
    
    // Initially open (default state is true in MetadataNode)
    expect(screen.getByText('2024')).toBeDefined();
    
    // Click to close
    fireEvent.click(detailsBtn!);
    
    // After closing, nested content should be hidden/removed
    await waitFor(() => {
        expect(screen.queryByText('2024')).toBeNull();
    }, { timeout: 1000 });
    
    // Click to open again
    fireEvent.click(detailsBtn!);
    await waitFor(() => {
        expect(screen.getByText('2024')).toBeDefined();
    }, { timeout: 1000 });
  });
});
