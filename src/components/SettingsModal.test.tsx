import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SettingsModal } from './SettingsModal';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { AppConfig } from '../types';

// api mock：仅 DimensionManager 需要（SettingsModal 本体已不再依赖多 Key 统计接口）
vi.mock('../api/client', () => ({
  api: {
    getDimensions: vi.fn().mockResolvedValue({ dimensions: [] }),
    saveDimension: vi.fn(),
    deleteDimension: vi.fn(),
    runBatch: vi.fn(),
    exportDimension: vi.fn(),
  },
}));

describe('SettingsModal Component', () => {
  const mockConfig: AppConfig = {
    WORKSPACE_PATH: '/test/path',
    DEEPSEEK_API_KEY: 'test-key',
    API_BASE: 'http://localhost:1234',
    OCR_MODEL: 'deepseek-ai/DeepSeek-OCR',
    TABLE_STYLE: 'three-line',
  };

  const mockHandlers = {
    onClose: vi.fn(),
    onSaveConfig: vi.fn().mockResolvedValue(true),
    onSelectWorkspace: vi.fn(),
  };

  const renderModal = (config: AppConfig = mockConfig) =>
    render(
      <SettingsModal
        isOpen={true}
        config={config}
        onClose={mockHandlers.onClose}
        onSaveConfig={mockHandlers.onSaveConfig}
        onSelectWorkspace={mockHandlers.onSelectWorkspace}
      />
    );

  beforeEach(() => {
    vi.clearAllMocks();
    mockHandlers.onSaveConfig.mockResolvedValue(true);
  });

  // UX-29：显式保存 + 保存反馈（不再失焦静默保存）
  it('saves only the modified field via the explicit save button', async () => {
    renderModal();

    const apiKeyInput = screen.getByLabelText('OCR API Key');
    fireEvent.change(apiKeyInput, { target: { value: 'new-key' } });

    expect(mockHandlers.onSaveConfig).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /保存$/ }));

    await waitFor(() => {
      expect(mockHandlers.onSaveConfig).toHaveBeenCalledWith('DEEPSEEK_API_KEY', 'new-key');
    });
    // 只保存脏字段，不误写其它配置
    expect(mockHandlers.onSaveConfig).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(mockHandlers.onClose).toHaveBeenCalled());
  });

  it('keeps the save button disabled until something changes', () => {
    renderModal();

    const saveBtn = screen.getByRole('button', { name: /保存$/ });
    expect(saveBtn).toBeDisabled();
    expect(screen.getByText('所有修改已保存')).toBeDefined();

    fireEvent.change(screen.getByLabelText('API Base URL'), { target: { value: 'http://changed' } });
    expect(saveBtn).not.toBeDisabled();
    expect(screen.getByText(/1 项未保存的修改/)).toBeDefined();
  });

  // UX-29：空值保护——不能静默清空密钥
  it('blocks saving an empty required field', async () => {
    renderModal();

    fireEvent.change(screen.getByLabelText('OCR API Key'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /保存$/ }));

    expect(await screen.findByText('不能为空')).toBeDefined();
    expect(mockHandlers.onSaveConfig).not.toHaveBeenCalled();
  });

  it('validates the API base URL format', async () => {
    renderModal();

    fireEvent.change(screen.getByLabelText('API Base URL'), { target: { value: 'localhost:1234' } });
    fireEvent.click(screen.getByRole('button', { name: /保存$/ }));

    expect(await screen.findByText('必须以 http:// 或 https:// 开头')).toBeDefined();
    expect(mockHandlers.onSaveConfig).not.toHaveBeenCalled();
  });

  // UX-31：未保存修改需二次确认
  it('asks for confirmation before discarding unsaved changes', async () => {
    renderModal();

    fireEvent.change(screen.getByLabelText('OCR 模型名'), { target: { value: 'other-model' } });
    fireEvent.click(screen.getByLabelText('关闭设置'));

    expect(await screen.findByText('放弃未保存的修改？')).toBeDefined();
    expect(mockHandlers.onClose).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('继续编辑'));
    expect(mockHandlers.onClose).not.toHaveBeenCalled();
  });

  it('triggers onSelectWorkspace when the switch button is clicked', () => {
    renderModal();

    fireEvent.click(screen.getByRole('button', { name: /切换/ }));

    expect(mockHandlers.onSelectWorkspace).toHaveBeenCalled();
  });

  it('switches to the dimensions tab and mounts DimensionManager (empty state)', async () => {
    renderModal();

    // 默认在基础配置 tab：DimensionManager 尚未挂载
    expect(screen.queryByText('还没有提取维度')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /提取维度/ }));

    expect(await screen.findByText('还没有提取维度')).toBeDefined();
    expect(screen.getByRole('button', { name: '新建维度' })).toBeDefined();
  });

  // Task 2：多 Key 轮询方案已移除（不再有 OCR Keys / LLM Keys 两个 Tab）
  it('no longer exposes multi-key tabs', () => {
    renderModal();

    expect(screen.queryByText('OCR Keys')).toBeNull();
    expect(screen.queryByText('LLM Keys')).toBeNull();
    expect(screen.queryByText(/Multi-Key/)).toBeNull();
  });
});
