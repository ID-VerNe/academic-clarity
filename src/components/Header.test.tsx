import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from './Header';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('Header Component', () => {
  const mockProps = {
    workspacePath: '/test/workspace',
    setView: vi.fn(),
    onOpenSettings: vi.fn(),
    searchValue: '',
    onSearchChange: vi.fn(),
    onSearchSubmit: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('triggers setView("dashboard") when Logo/Title area is clicked', () => {
    render(<Header {...mockProps} />);

    fireEvent.click(screen.getByLabelText('返回文献库'));

    expect(mockProps.setView).toHaveBeenCalledWith('dashboard');
  });

  it('triggers onOpenSettings when Settings icon is clicked', () => {
    render(<Header {...mockProps} />);

    fireEvent.click(screen.getByLabelText('打开设置'));

    expect(mockProps.onOpenSettings).toHaveBeenCalled();
  });

  it('shows the workspace path and falls back while loading', () => {
    const { rerender } = render(<Header {...mockProps} workspacePath="" />);
    expect(screen.getByText('正在加载工作区…')).toBeDefined();

    rerender(<Header {...mockProps} workspacePath="/papers/2024" />);
    expect(screen.getByText('/papers/2024')).toBeDefined();
  });

  // UX-02：Header 搜索框不再是无响应的死控件
  it('wires the global search box (controlled value + change handler)', () => {
    render(<Header {...mockProps} />);

    const input = screen.getByLabelText('搜索文献库');
    fireEvent.change(input, { target: { value: 'transformer' } });

    expect(mockProps.onSearchChange).toHaveBeenCalledWith('transformer');
  });

  it('submits the search on Enter', () => {
    render(<Header {...mockProps} />);

    fireEvent.keyDown(screen.getByLabelText('搜索文献库'), { key: 'Enter' });

    expect(mockProps.onSearchSubmit).toHaveBeenCalled();
  });

  // UX-17：中文输入法选词回车不应触发提交
  it('ignores Enter while an IME composition is active', () => {
    render(<Header {...mockProps} />);

    fireEvent.keyDown(screen.getByLabelText('搜索文献库'), { key: 'Enter', isComposing: true });

    expect(mockProps.onSearchSubmit).not.toHaveBeenCalled();
  });

  // UX-04 / UX-45：通知铃铛与头像等死控件已移除
  it('no longer renders the dead notification bell or avatar', () => {
    render(<Header {...mockProps} />);

    expect(screen.queryByText('AC')).toBeNull();
    expect(screen.queryByText('Bell')).toBeNull();
    // 右侧只剩搜索框与设置按钮两个可交互元素
    expect(screen.getAllByRole('button')).toHaveLength(2);
  });
});
