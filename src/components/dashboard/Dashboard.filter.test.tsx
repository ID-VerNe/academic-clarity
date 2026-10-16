import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { Dashboard } from '../Dashboard';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { baseProps, mockConfig, mockDocs, SearchHarness, resetApiMocks } from './testUtils';

// Mock the API client（处理队列轮询 + claims 检索/摄入 + 取消）
vi.mock('../../api/client', () => ({
  api: {
    getActiveTasks: vi.fn().mockResolvedValue([]),
    searchKnowledge: vi.fn().mockResolvedValue({ results: [] }),
    ingestKnowledge: vi.fn().mockResolvedValue({ success: true, result: {} }),
    cancelTask: vi.fn().mockResolvedValue({ success: true }),
  },
}));

describe('Dashboard Filtering', () => {
  beforeEach(() => {
    resetApiMocks();
  });

  it('filters by search query (title / authors)', async () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('搜索文献'), { target: { value: 'Alpha' } });

    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  // UX-13：检索范围兑现 placeholder 承诺（含洞察字段）
  it('also matches insight fields and reports the search scope', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('搜索文献'), { target: { value: 'Science' } });

    expect(screen.getByText('Beta Science')).toBeDefined();
    expect(screen.queryByText('Alpha Research')).toBeNull();
    expect(screen.getByText(/检索范围：标题、文件名、作者、期刊、年份与洞察字段/)).toBeDefined();
  });

  it('filters by journal selection', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('按期刊筛选'), { target: { value: 'Nature' } });

    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.queryByText('Beta Science')).toBeNull();
  });

  it('filters by year selection', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('按年份筛选'), { target: { value: '2024' } });

    expect(screen.getByText('Beta Science')).toBeDefined();
    expect(screen.queryByText('Alpha Research')).toBeNull();
  });

  it('resets all filters when clicking the filter clear button', () => {
    render(<SearchHarness />);

    fireEvent.change(screen.getByLabelText('按年份筛选'), { target: { value: '2024' } });
    fireEvent.change(screen.getByLabelText('搜索文献'), { target: { value: '不存在的关键词' } });

    // UX-12：筛选无结果与「空库」区分开
    expect(screen.getByText('没有符合当前筛选条件的文献')).toBeDefined();

    fireEvent.click(screen.getByLabelText('清除筛选条件'));

    expect(screen.getByText('Alpha Research')).toBeDefined();
    expect(screen.getByText('Beta Science')).toBeDefined();
  });

  it('sorts the library by import time (newest first by default)', () => {
    render(<SearchHarness />);

    const cards = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(cards[0]).toBe('Beta Science');
    expect(cards[1]).toBe('Alpha Research');
  });

  it('mounts a hidden file input wired to the import button', () => {
    const handlers = baseProps();
    const { container } = render(<Dashboard {...handlers} />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(fileInput).not.toBeNull();
    expect(fileInput!.accept).toBe('.pdf,.tex,.zip');

    const clickSpy = vi.spyOn(fileInput!, 'click');
    fireEvent.click(screen.getByRole('button', { name: /导入 PDF \/ LaTeX/ }));
    expect(clickSpy).toHaveBeenCalled();

    const file = new File(['dummy'], 'paper.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput!, { target: { files: [file] } });
    expect(handlers.onUpload).toHaveBeenCalledWith(file);
  });

  it('disables the import button while uploading', () => {
    render(<Dashboard {...baseProps()} isUploading={true} />);

    const btn = screen.getByRole('button', { name: /导入中/ });
    expect(btn).toBeDisabled();
  });

  // UX-35：拖拽导入
  it('imports a file dropped onto the page and rejects unsupported types', () => {
    const handlers = baseProps();
    const { container } = render(<Dashboard {...handlers} />);
    const main = container.querySelector('main')!;

    const pdf = new File(['x'], 'dropped.pdf', { type: 'application/pdf' });
    fireEvent.drop(main, { dataTransfer: { files: [pdf] } });
    expect(handlers.onUpload).toHaveBeenCalledWith(pdf);

    const doc = new File(['x'], 'notes.docx');
    fireEvent.drop(main, { dataTransfer: { files: [doc] } });
    expect(handlers.onUpload).toHaveBeenCalledTimes(1);
  });

  // UX-03：同步按钮由上层负责刷新
  it('delegates sync to the parent handler', () => {
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    fireEvent.click(screen.getByLabelText('同步工作区'));

    expect(handlers.onSync).toHaveBeenCalled();
  });

  // UX-37：工具栏图标按钮具备可访问名称
  it('exposes accessible labels for workspace / sync / card actions', () => {
    const handlers = baseProps();
    render(<Dashboard {...handlers} />);

    expect(screen.getByLabelText('切换工作区')).toBeDefined();
    expect(screen.getByLabelText('阅读 Alpha Research')).toBeDefined();
    expect(screen.getByLabelText('删除 Alpha Research')).toBeDefined();

    fireEvent.click(screen.getByLabelText('删除 Alpha Research'));
    expect(handlers.onDelete).toHaveBeenCalledWith(mockDocs[0]);
  });

  // UX-32：配置不完整时的引导
  it('shows a setup banner and links to settings when config is incomplete', () => {
    const handlers = baseProps();
    render(
      <Dashboard
        {...handlers}
        config={{ ...mockConfig, DEEPSEEK_API_KEY: '', OCR_MODEL: '' }}
      />
    );

    expect(screen.getByText('尚未完成 AI 配置，导入的文献将无法处理')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /去设置/ }));
    expect(handlers.onOpenSettings).toHaveBeenCalled();
  });

  // UX-12 / UX-32：空库三步引导
  it('shows a 3-step onboarding guide when the library is empty', () => {
    const handlers = baseProps();
    render(<Dashboard {...handlers} docs={[]} />);

    expect(screen.getByText('文献库还是空的')).toBeDefined();

    // 三步引导（限定在有序列表内，避免与同名按钮文案冲突）
    const steps = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(steps).toHaveLength(3);
    expect(within(steps[0]).getByText('选择工作区')).toBeDefined();
    expect(within(steps[1]).getByText('配置 OCR API Key')).toBeDefined();
    expect(within(steps[2]).getByText('导入 PDF / LaTeX')).toBeDefined();

    // 引导卡上的三个操作按钮
    expect(screen.getByRole('button', { name: /选择工作区/ })).toBeDefined();
    expect(screen.getByRole('button', { name: /打开设置/ })).toBeDefined();
    expect(screen.getByRole('button', { name: /导入第一篇/ })).toBeDefined();

    expect(screen.queryByText('没有符合当前筛选条件的文献')).toBeNull();
  });

  it('renders skeleton cards while loading', () => {
    const { container } = render(<Dashboard {...baseProps()} isLoading={true} />);
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
    expect(screen.queryByText('Alpha Research')).toBeNull();
  });

  // UX-36 / UX-44：页脚真实健康状态与按模式计数的口径
  it('reflects the real backend health in the footer', () => {
    const { rerender } = render(<Dashboard {...baseProps()} backendHealthy={false} />);
    expect(screen.getByText('后端未连接')).toBeDefined();
    expect(screen.getByText(/请确认应用已完全启动/)).toBeDefined();

    rerender(<Dashboard {...baseProps()} backendHealthy={true} />);
    expect(screen.getByText('后端已连接')).toBeDefined();
    expect(screen.getByText('2 / 2 篇文献')).toBeDefined();
  });
});
