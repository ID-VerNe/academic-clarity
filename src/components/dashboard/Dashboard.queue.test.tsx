import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Dashboard } from '../Dashboard';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { api } from '../../api/client';
import { baseProps, mockDocs, resetApiMocks } from './testUtils';

// Mock the API client（处理队列轮询 + 取消）
vi.mock('../../api/client', () => ({
  api: {
    getActiveTasks: vi.fn().mockResolvedValue([]),
    searchKnowledge: vi.fn().mockResolvedValue({ results: [] }),
    ingestKnowledge: vi.fn().mockResolvedValue({ success: true, result: {} }),
    cancelTask: vi.fn().mockResolvedValue({ success: true }),
  },
}));

describe('Dashboard Processing Queue (UX-26)', () => {
  beforeEach(() => {
    resetApiMocks();
  });

  it('renders stage / progress / elapsed for active tasks', async () => {
    (api.getActiveTasks as any).mockResolvedValue([
      { ...mockDocs[0], ocr_status: 'processing', stage: 'OCR 第 3/10 页', progress: 42, elapsed: 95 },
    ]);

    render(<Dashboard {...baseProps()} />);

    expect(await screen.findByText('OCR 第 3/10 页')).toBeDefined();
    expect(screen.getByText('42%')).toBeDefined();
    expect(screen.getByText(/已用时 1 分 35 秒/)).toBeDefined();
    expect(screen.getByText('1 篇处理中')).toBeDefined();
  });

  it('cancels an active task and asks the parent to refresh', async () => {
    (api.getActiveTasks as any).mockResolvedValue([
      { ...mockDocs[0], ocr_status: 'processing', stage: '提取 Basic Insight', progress: 70, elapsed: 10 },
    ]);
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    fireEvent.click(await screen.findByLabelText('取消处理 Alpha Research'));

    await waitFor(() => {
      expect(api.cancelTask).toHaveBeenCalledWith(1);
    });
    expect(handlers.onRefresh).toHaveBeenCalled();
  });
});
