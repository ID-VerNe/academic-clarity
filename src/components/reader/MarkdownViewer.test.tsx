import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MarkdownViewer } from './MarkdownViewer';

describe('MarkdownViewer', () => {
  it('renders structured OCR JSON blocks with semantic hierarchy', () => {
    render(
      <MarkdownViewer
        isSplitView={false}
        structuredContent={{
          version: 1,
          blocks: [
            { type: 'title', text: 'Paper Title' },
            { type: 'subtitle', text: '1. Introduction' },
            { type: 'text', text: 'This is the first paragraph.' },
          ],
        }}
      />
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Paper Title' })).toBeDefined();
    expect(screen.getByRole('heading', { level: 2, name: '1. Introduction' })).toBeDefined();
    expect(screen.getByText('This is the first paragraph.')).toBeDefined();
  });

  it('falls back to markdown renderer for plain markdown content', () => {
    render(<MarkdownViewer isSplitView={false} content="# Plain Markdown Title" />);
    expect(screen.getByRole('heading', { level: 1, name: 'Plain Markdown Title' })).toBeDefined();
  });

  it('allows data URI images in structured markdown blocks', () => {
    const { container } = render(
      <MarkdownViewer
        isSplitView={false}
        structuredContent={{
          version: 1,
          blocks: [
            {
              type: 'text',
              text: '![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQfQ7dQAAAAASUVORK5CYII=)'
            }
          ],
        }}
      />
    );

    const image = container.querySelector('img');
    expect(image).toBeTruthy();
    expect(image?.getAttribute('src')?.startsWith('data:image/png;base64,')).toBe(true);
  });
});
