import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DimensionManager } from './DimensionManager';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { api } from '../../api/client';
import { ExtractionDimension } from '../../types';
import { ToastHost, clearToasts } from '../ui/Toast';

// 全部网络能力 mock：组件仅依赖 api 模块（不 mock fetch 本体，保持边界清晰）
vi.mock('../../api/client', () => ({
  api: {
    getDimensions: vi.fn(),
    saveDimension: vi.fn(),
    deleteDimension: vi.fn(),
    runBatch: vi.fn(),
    exportDimension: vi.fn(),
  }
}));

const getDimensions = vi.mocked(api.getDimensions);
const saveDimension = vi.mocked(api.saveDimension);
const deleteDimension = vi.mocked(api.deleteDimension);
const runBatch = vi.mocked(api.runBatch);
const exportDimension = vi.mocked(api.exportDimension);

const DIM_A: ExtractionDimension = {
  id: 'dim-a',
  label: 'Methodology',
  prompt: 'Extract the core methodology as JSON.',
  system_prompt: '',
  enabled: true,
};

const DIM_B: ExtractionDimension = {
  id: 'dim-b',
  label: 'Limitations',
  prompt: 'Extract stated limitations.',
  system_prompt: '',
  enabled: false,
};

/** 统一挂载（带 ToastHost，断言全局反馈 UX-06） */
const renderManager = () =>
  render(
    <>
      <DimensionManager />
      <ToastHost />
    </>
  );

/** 打开某一行的「更多操作」菜单并点击其中一项 */
const clickRowMenu = (label: string, item: string) => {
  fireEvent.click(screen.getByLabelText(`更多操作 ${label}`));
  fireEvent.click(screen.getByText(item));
};

describe('DimensionManager Component', () => {
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    clearToasts();
    getDimensions.mockResolvedValue({ dimensions: [DIM_A, DIM_B] });
    saveDimension.mockResolvedValue({ success: true, dimension: DIM_A });
    deleteDimension.mockResolvedValue({ success: true });
    runBatch.mockResolvedValue({ success: true, queued: 5, skipped: 2 });
    exportDimension.mockResolvedValue(new Blob(['a,b\n1,2'], { type: 'text/csv' }));

    // jsdom 无 createObjectURL / 真实导航：全部打桩
    (URL as any).createObjectURL = vi.fn(() => 'blob:mock-url');
    (URL as any).revokeObjectURL = vi.fn();
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  });

  afterEach(() => {
    clickSpy.mockRestore();
  });

  it('loads and renders dimensions on mount (with disabled badge)', async () => {
    renderManager();

    expect(await screen.findByText('Methodology')).toBeDefined();
    expect(screen.getByText('Limitations')).toBeDefined();
    // 禁用的维度显示「已禁用」徽标
    expect(screen.getByText('已禁用')).toBeDefined();
    expect(getDimensions).toHaveBeenCalledTimes(1);
  });

  it('shows empty state when no dimensions exist', async () => {
    getDimensions.mockResolvedValue({ dimensions: [] });
    renderManager();

    expect(await screen.findByText('还没有提取维度')).toBeDefined();
    // 空态不显示任何行操作
    expect(screen.queryByText('批量运行')).toBeNull();
  });

  it('opens the new-dimension form and keeps Save disabled until label+prompt filled', async () => {
    renderManager();
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByRole('button', { name: '新建维度' }));

    const saveBtn = screen.getByRole('button', { name: /保存维度/ });
    expect(saveBtn).toBeDisabled();

    fireEvent.change(screen.getByLabelText('维度名称'), { target: { value: 'Datasets' } });
    expect(saveBtn).toBeDisabled();  // 仅 label 不够

    fireEvent.change(screen.getByLabelText('提取提示词'), { target: { value: 'List datasets used.' } });
    expect(saveBtn).not.toBeDisabled();
  });

  it('saves a new dimension, refetches the list, and shows a success message', async () => {
    renderManager();
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByRole('button', { name: '新建维度' }));
    fireEvent.change(screen.getByLabelText('维度名称'), { target: { value: 'Datasets' } });
    fireEvent.change(screen.getByLabelText('提取提示词'), { target: { value: 'List datasets used.' } });
    fireEvent.change(screen.getByLabelText('系统提示词'), { target: { value: 'Be terse.' } });
    fireEvent.click(screen.getByRole('button', { name: /保存维度/ }));

    await waitFor(() => expect(saveDimension).toHaveBeenCalledTimes(1));
    expect(saveDimension).toHaveBeenCalledWith({
      id: '', label: 'Datasets', prompt: 'List datasets used.',
      system_prompt: 'Be terse.', enabled: true,
    });
    // 保存成功后重新拉取 + 关闭表单 + 成功提示（含「需再次批量运行」的说明）
    await waitFor(() => expect(getDimensions).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/已保存维度「Datasets」/)).toBeDefined();
    expect(screen.queryByLabelText('维度名称')).toBeNull();
  });

  it('shows error banner when save fails (e.g. duplicate label)', async () => {
    saveDimension.mockRejectedValue(new Error('label already exists'));
    renderManager();
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByRole('button', { name: '新建维度' }));
    fireEvent.change(screen.getByLabelText('维度名称'), { target: { value: 'Methodology' } });
    fireEvent.change(screen.getByLabelText('提取提示词'), { target: { value: 'dup' } });
    fireEvent.click(screen.getByRole('button', { name: /保存维度/ }));

    expect(await screen.findByText('label already exists')).toBeDefined();
    // 表单保持打开，允许修正后重试
    expect(screen.getByLabelText('维度名称')).toBeDefined();
  });

  it('pre-fills the form when editing an existing dimension', async () => {
    renderManager();
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('编辑 Methodology'));

    expect(screen.getByText('编辑维度')).toBeDefined();
    expect((screen.getByLabelText('维度名称') as HTMLInputElement).value).toBe('Methodology');
    expect((screen.getByLabelText('提取提示词') as HTMLTextAreaElement).value)
      .toBe('Extract the core methodology as JSON.');
  });

  it('deletes a dimension after confirm and refetches', async () => {
    renderManager();
    await screen.findByText('Methodology');

    // 删除已收纳进行内「更多操作」菜单（UX-34），确认走应用内 ConfirmDialog
    clickRowMenu('Limitations', '删除维度');

    expect(screen.getByRole('alertdialog')).toBeDefined();
    expect(screen.getByText('删除这个维度？')).toBeDefined();
    expect(screen.getByText(/已产生的提取结果会保留/)).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: '删除' }));

    await waitFor(() => expect(deleteDimension).toHaveBeenCalledWith('dim-b'));
    await waitFor(() => expect(getDimensions).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/已删除维度「Limitations」/)).toBeDefined();
  });

  it('does not delete when confirm is cancelled', async () => {
    renderManager();
    await screen.findByText('Methodology');

    clickRowMenu('Limitations', '删除维度');
    fireEvent.click(screen.getByRole('button', { name: '取消' }));

    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
    expect(deleteDimension).not.toHaveBeenCalled();
  });

  it('runs a batch and reports queued/skipped counts', async () => {
    renderManager();
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('批量运行 Methodology'));

    await waitFor(() => expect(runBatch).toHaveBeenCalledWith('dim-a'));
    expect(await screen.findByText(/已入队 5 篇（跳过 2 篇/)).toBeDefined();
  });

  it('shows a failure toast when batch run fails', async () => {
    runBatch.mockRejectedValue(new Error('no documents'));
    renderManager();
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('批量运行 Methodology'));

    expect(await screen.findByText(/批量运行失败：no documents/)).toBeDefined();
  });

  it('disables Run Batch for a disabled dimension (fail-fast parity)', async () => {
    renderManager();
    await screen.findByText('Methodology');

    expect(screen.getByLabelText('批量运行 Methodology')).not.toBeDisabled();
    expect(screen.getByLabelText('批量运行 Limitations')).toBeDisabled();

    // 点击停用维度的按钮不应触发任何请求
    fireEvent.click(screen.getByLabelText('批量运行 Limitations'));
    expect(runBatch).not.toHaveBeenCalled();
  });

  it('exports CSV via Blob download', async () => {
    renderManager();
    await screen.findByText('Methodology');

    clickRowMenu('Methodology', '导出 CSV');

    await waitFor(() => expect(exportDimension).toHaveBeenCalledWith('dim-a', 'csv'));
    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1));
    expect((URL as any).createObjectURL).toHaveBeenCalled();
    expect((URL as any).revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    expect(await screen.findByText(/已导出「Methodology」为 CSV/)).toBeDefined();
  });

  it('exports Markdown via Blob download', async () => {
    exportDimension.mockResolvedValue(new Blob(['# Report'], { type: 'text/markdown' }));
    renderManager();
    await screen.findByText('Methodology');

    clickRowMenu('Methodology', '导出 Markdown');

    await waitFor(() => expect(exportDimension).toHaveBeenCalledWith('dim-a', 'md'));
    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1));
  });

  it('shows a failure toast when export fails', async () => {
    exportDimension.mockRejectedValue(new Error('Export failed: HTTP 500'));
    renderManager();
    await screen.findByText('Methodology');

    clickRowMenu('Methodology', '导出 CSV');

    expect(await screen.findByText(/导出失败：Export failed: HTTP 500/)).toBeDefined();
  });
});
