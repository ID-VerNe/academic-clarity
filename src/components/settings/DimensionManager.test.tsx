import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DimensionManager } from './DimensionManager';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { api } from '../../api/client';
import { ExtractionDimension } from '../../types';

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

describe('DimensionManager Component', () => {
  let clickSpy: ReturnType<typeof vi.spyOn>;
  let confirmSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    getDimensions.mockResolvedValue({ dimensions: [DIM_A, DIM_B] });
    saveDimension.mockResolvedValue({ success: true, dimension: DIM_A });
    deleteDimension.mockResolvedValue({ success: true });
    runBatch.mockResolvedValue({ success: true, queued: 5, skipped: 2 });
    exportDimension.mockResolvedValue(new Blob(['a,b\n1,2'], { type: 'text/csv' }));

    // jsdom 无 createObjectURL / 真实导航：全部打桩
    (URL as any).createObjectURL = vi.fn(() => 'blob:mock-url');
    (URL as any).revokeObjectURL = vi.fn();
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  afterEach(() => {
    clickSpy.mockRestore();
    confirmSpy.mockRestore();
  });

  it('loads and renders dimensions on mount (with disabled badge)', async () => {
    render(<DimensionManager />);

    expect(await screen.findByText('Methodology')).toBeDefined();
    expect(screen.getByText('Limitations')).toBeDefined();
    // 禁用的维度显示 disabled 徽标
    expect(screen.getByText('disabled')).toBeDefined();
    expect(getDimensions).toHaveBeenCalledTimes(1);
  });

  it('shows empty state when no dimensions exist', async () => {
    getDimensions.mockResolvedValue({ dimensions: [] });
    render(<DimensionManager />);

    expect(await screen.findByText('No dimensions yet')).toBeDefined();
  });

  it('opens the new-dimension form and keeps Save disabled until label+prompt filled', async () => {
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByText('New Dimension'));

    const saveBtn = screen.getByText('Save Dimension').closest('button')!;
    expect(saveBtn).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Dimension Label'), { target: { value: 'Datasets' } });
    expect(saveBtn).toBeDisabled();  // 仅 label 不够

    fireEvent.change(screen.getByLabelText('Dimension Prompt'), { target: { value: 'List datasets used.' } });
    expect(saveBtn).not.toBeDisabled();
  });

  it('saves a new dimension, refetches the list, and shows a success message', async () => {
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByText('New Dimension'));
    fireEvent.change(screen.getByLabelText('Dimension Label'), { target: { value: 'Datasets' } });
    fireEvent.change(screen.getByLabelText('Dimension Prompt'), { target: { value: 'List datasets used.' } });
    fireEvent.change(screen.getByLabelText('Dimension System Prompt'), { target: { value: 'Be terse.' } });
    fireEvent.click(screen.getByText('Save Dimension'));

    await waitFor(() => expect(saveDimension).toHaveBeenCalledTimes(1));
    expect(saveDimension).toHaveBeenCalledWith({
      id: '', label: 'Datasets', prompt: 'List datasets used.',
      system_prompt: 'Be terse.', enabled: true,
    });
    // 保存成功后重新拉取 + 关闭表单 + 成功提示
    await waitFor(() => expect(getDimensions).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/已保存维度「Datasets」/)).toBeDefined();
    expect(screen.queryByText('Save Dimension')).toBeNull();
  });

  it('shows error banner when save fails (e.g. duplicate label)', async () => {
    saveDimension.mockRejectedValue(new Error('label already exists'));
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByText('New Dimension'));
    fireEvent.change(screen.getByLabelText('Dimension Label'), { target: { value: 'Methodology' } });
    fireEvent.change(screen.getByLabelText('Dimension Prompt'), { target: { value: 'dup' } });
    fireEvent.click(screen.getByText('Save Dimension'));

    expect(await screen.findByText('label already exists')).toBeDefined();
    // 表单保持打开，允许修正后重试
    expect(screen.getByText('Save Dimension')).toBeDefined();
  });

  it('pre-fills the form when editing an existing dimension', async () => {
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Edit Methodology'));

    expect(screen.getByText('Edit Dimension')).toBeDefined();
    expect((screen.getByLabelText('Dimension Label') as HTMLInputElement).value).toBe('Methodology');
    expect((screen.getByLabelText('Dimension Prompt') as HTMLTextAreaElement).value)
      .toBe('Extract the core methodology as JSON.');
  });

  it('deletes a dimension after confirm and refetches', async () => {
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Delete Limitations'));

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('删除维度「Limitations」'));
    await waitFor(() => expect(deleteDimension).toHaveBeenCalledWith('dim-b'));
    await waitFor(() => expect(getDimensions).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/已删除维度「Limitations」/)).toBeDefined();
  });

  it('does not delete when confirm is cancelled', async () => {
    confirmSpy.mockReturnValue(false);
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Delete Limitations'));

    expect(deleteDimension).not.toHaveBeenCalled();
  });

  it('runs a batch and reports queued/skipped counts', async () => {
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Run Batch Methodology'));

    await waitFor(() => expect(runBatch).toHaveBeenCalledWith('dim-a'));
    expect(await screen.findByText(/已入队 5 篇（跳过 2 篇/)).toBeDefined();
  });

  it('shows error banner when batch run fails', async () => {
    runBatch.mockRejectedValue(new Error('no documents'));
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Run Batch Methodology'));

    expect(await screen.findByText('no documents')).toBeDefined();
  });

  it('disables Run Batch for a disabled dimension (fail-fast parity)', async () => {
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    expect(screen.getByLabelText('Run Batch Methodology')).not.toBeDisabled();
    expect(screen.getByLabelText('Run Batch Limitations')).toBeDisabled();

    // 点击停用维度的按钮不应触发任何请求
    fireEvent.click(screen.getByLabelText('Run Batch Limitations'));
    expect(runBatch).not.toHaveBeenCalled();
  });

  it('exports CSV via Blob download', async () => {
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Export CSV Methodology'));

    await waitFor(() => expect(exportDimension).toHaveBeenCalledWith('dim-a', 'csv'));
    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1));
    expect((URL as any).createObjectURL).toHaveBeenCalled();
    expect((URL as any).revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });

  it('exports Markdown via Blob download', async () => {
    exportDimension.mockResolvedValue(new Blob(['# Report'], { type: 'text/markdown' }));
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Export MD Methodology'));

    await waitFor(() => expect(exportDimension).toHaveBeenCalledWith('dim-a', 'md'));
    await waitFor(() => expect(clickSpy).toHaveBeenCalledTimes(1));
  });

  it('shows error banner when export fails', async () => {
    exportDimension.mockRejectedValue(new Error('Export failed: HTTP 500'));
    render(<DimensionManager />);
    await screen.findByText('Methodology');

    fireEvent.click(screen.getByLabelText('Export CSV Methodology'));

    expect(await screen.findByText('Export failed: HTTP 500')).toBeDefined();
  });
});
