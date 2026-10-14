import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MetadataPanel } from './MetadataPanel';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';

// Mock the API client
vi.mock('../../api/client', () => ({
  api: {
    verifyDoi: vi.fn(),
    getBibtex: vi.fn(),
  }
}));

import { api } from '../../api/client';

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

describe('MetadataPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

describe('MetadataPanel DOI tools (Phase 1)', () => {
  const insightWithDoi = JSON.stringify({
    title: "Some Paper",
    authors: "John Doe",
    doi: "10.1109/TVCG.2023.12345",
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not render DOI buttons without docId or without doi field', () => {
    const { rerender } = render(
      <MetadataPanel data={insightWithDoi} label="Basic Insight" />
    );
    expect(screen.queryByText('验证 DOI')).toBeNull();
    expect(screen.queryByText('复制 BibTeX')).toBeNull();

    rerender(<MetadataPanel data={nestedData} label="Basic Insight" docId={7} />);
    expect(screen.queryByText('验证 DOI')).toBeNull();
    expect(screen.queryByText('复制 BibTeX')).toBeNull();
  });

  it('renders DOI buttons for Basic Insight with doi + docId', () => {
    render(<MetadataPanel data={insightWithDoi} label="Basic Insight" docId={7} />);
    expect(screen.getByText('验证 DOI')).toBeDefined();
    expect(screen.getByText('复制 BibTeX')).toBeDefined();
  });

  it('verify button calls api.verifyDoi and renders status badge', async () => {
    (api.verifyDoi as any).mockResolvedValue({
      success: true,
      result: { status: 'verified', doi: '10.1109/TVCG.2023.12345', score: 100, source: 'crossref' },
    });
    const onVerified = vi.fn();
    render(
      <MetadataPanel data={insightWithDoi} label="Basic Insight" docId={7} onVerified={onVerified} />
    );

    fireEvent.click(screen.getByText('验证 DOI'));

    await waitFor(() => {
      expect(api.verifyDoi).toHaveBeenCalledWith(7);
    });
    await waitFor(() => {
      expect(screen.getByText(/verified · crossref/)).toBeDefined();
    });
    expect(onVerified).toHaveBeenCalled();
  });

  it('verify failure degrades to unverified badge (no throw)', async () => {
    (api.verifyDoi as any).mockRejectedValue(new Error('network'));
    render(<MetadataPanel data={insightWithDoi} label="Basic Insight" docId={7} />);

    fireEvent.click(screen.getByText('验证 DOI'));

    await waitFor(() => {
      expect(screen.getByText(/unverified · unverified/)).toBeDefined();
    });
  });

  it('bibtex button copies clipboard on success', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    (api.getBibtex as any).mockResolvedValue({ bibtex: '@article{...}' });
    render(<MetadataPanel data={insightWithDoi} label="Basic Insight" docId={7} />);

    fireEvent.click(screen.getByText('复制 BibTeX'));

    await waitFor(() => {
      expect(api.getBibtex).toHaveBeenCalledWith(7);
    });
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith('@article{...}');
    });
    await waitFor(() => {
      expect(screen.getByText('BibTeX copied')).toBeDefined();
    });
  });

  it('bibtex button shows failure note when clipboard write throws', async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) } });
    (api.getBibtex as any).mockResolvedValue({ bibtex: '@article{...}' });
    render(<MetadataPanel data={insightWithDoi} label="Basic Insight" docId={7} />);

    fireEvent.click(screen.getByText('复制 BibTeX'));

    await waitFor(() => {
      expect(screen.getByText('Copy failed')).toBeDefined();
    });
  });

  it('bibtex button shows note when no bibtex returned', async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn() } });
    (api.getBibtex as any).mockResolvedValue({});
    render(<MetadataPanel data={insightWithDoi} label="Basic Insight" docId={7} />);

    fireEvent.click(screen.getByText('复制 BibTeX'));

    await waitFor(() => {
      expect(screen.getByText('No BibTeX available')).toBeDefined();
    });
  });
});
