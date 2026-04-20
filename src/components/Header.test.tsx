import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from './Header';
import { vi, describe, it, expect } from 'vitest';

describe('Header Component', () => {
  const mockProps = {
    workspacePath: '/test/workspace',
    setView: vi.fn(),
    onOpenSettings: vi.fn(),
  };

  it('triggers setView("dashboard") when Logo/Title area is clicked', () => {
    render(<Header {...mockProps} />);
    
    const logoArea = screen.getByText('Academic Clarity').parentElement;
    fireEvent.click(logoArea!);
    
    expect(mockProps.setView).toHaveBeenCalledWith('dashboard');
  });

  it('triggers onOpenSettings when Settings icon is clicked', () => {
    render(<Header {...mockProps} />);
    
    const settingsBtn = screen.getByLabelText('Open Settings');
    fireEvent.click(settingsBtn);
    
    expect(mockProps.onOpenSettings).toHaveBeenCalled();
  });
});
