import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Dashboard } from '../Dashboard';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { api } from '../../api/client';
import { baseProps, mockDocs, resetApiMocks, searchClaims } from './testUtils';

// Mock the API client（claims 检索/摄入 + 处理队列轮询）
vi.mock('../../api/client', () => ({
  api: {
    getActiveTasks: vi.fn().mockResolvedValue([]),
    searchKnowledge: vi.fn().mockResolvedValue({ results: [] }),
    ingestKnowledge: vi.fn().mockResolvedValue({ success: true, result: {} }),
    cancelTask: vi.fn().mockResolvedValue({ success: true }),
  },
}));

describe('Dashboard Knowledge Claims (Phase 2)', () => {
  const claimResults = [
    {
      claim_id: 1,
      concept: 'trading bottleneck',
      quote: 'P2P 交易瓶颈在于各 agent 需顺序更新账本。',
      anchor: 'P2P 交易瓶颈在于各 agent 需顺序更新账本。',
      heading_path: 'Abstract',
      conflicting: 0,
      prompt_id: 'basic-insight-v1',
      doc_id: 1,
      title: 'Alpha Research',
    },
  ];

  beforeEach(() => {
    resetApiMocks();
  });

  it('switches to the claims tab, searches, and renders claim cards', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    render(<Dashboard {...baseProps()} />);

    searchClaims('交易');

    await waitFor(() => {
      expect(screen.getByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。')).toBeDefined();
    });
    expect(api.searchKnowledge).toHaveBeenCalledWith('交易', 20);
    // T1 徽标（统一中文术语）与论文标题回填
    expect(screen.getByText('逐字引文')).toBeDefined();
    expect(screen.getByText('Alpha Research')).toBeDefined();
    // 论文库网格在 claims 模式不渲染
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('opens the claim source document in Reader on card click', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    searchClaims('交易');

    const quote = await screen.findByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。');
    fireEvent.click(quote);

    expect(handlers.onSelectDoc).toHaveBeenCalledWith(mockDocs[0]);
  });

  it('ingests completed documents from the claims empty state', async () => {
    render(<Dashboard {...baseProps()} />);

    fireEvent.click(screen.getByRole('button', { name: /知识库检索/ }));
    fireEvent.click(screen.getByRole('button', { name: /摄入 2 篇文献/ }));

    await waitFor(() => {
      expect(api.ingestKnowledge).toHaveBeenCalledTimes(2);
    });
    expect(api.ingestKnowledge).toHaveBeenCalledWith(1);
    expect(api.ingestKnowledge).toHaveBeenCalledWith(2);
    expect(await screen.findByText(/已摄入 2 篇文献/)).toBeDefined();
  });

  it('shows a no-match state when the knowledge search returns nothing', async () => {
    render(<Dashboard {...baseProps()} />);

    searchClaims('不存在的词');

    expect(await screen.findByText(/没有匹配「不存在的词」的 claim/)).toBeDefined();
  });

  // UX-16：检索失败要与「无结果」区分，并提供重试
  it('shows an error state with retry when the knowledge search fails', async () => {
    (api.searchKnowledge as any).mockRejectedValueOnce(new Error('boom'));
    render(<Dashboard {...baseProps()} />);

    searchClaims('交易');

    expect(await screen.findByText('检索失败')).toBeDefined();
    expect(screen.getByRole('button', { name: /重试/ })).toBeDefined();

    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    fireEvent.click(screen.getByRole('button', { name: /重试/ }));

    expect(await screen.findByText('P2P 交易瓶颈在于各 agent 需顺序更新账本。')).toBeDefined();
  });

  it('reports the claim count in the footer while in claims mode', async () => {
    (api.searchKnowledge as any).mockResolvedValue({ results: claimResults });
    render(<Dashboard {...baseProps()} />);

    searchClaims('交易');

    await waitFor(() => {
      expect(screen.getByText('1 条检索结果')).toBeDefined();
    });
  });
});
