import { render, screen, fireEvent } from '@testing-library/react';
import { SettingsModal } from './SettingsModal';
import { vi, describe, it, expect } from 'vitest';
import React from 'react';
import { AppConfig } from '../types';

describe('SettingsModal Component', () => {
  const mockConfig: AppConfig = {
    WORKSPACE_PATH: '/test/path',
    DEEPSEEK_API_KEY: 'test-key',
    API_BASE: 'http://localhost:1234',
    TABLE_STYLE: 'three-line'
  };

  const mockHandlers = {
    onClose: vi.fn(),
    onSaveConfig: vi.fn(),
    onSelectWorkspace: vi.fn(),
  };

  it('triggers onSaveConfig when input fields lose focus (onBlur)', () => {
    render(
      <SettingsModal 
        isOpen={true} 
        config={mockConfig} 
        onClose={mockHandlers.onClose}
        onSaveConfig={mockHandlers.onSaveConfig}
        onSelectWorkspace={mockHandlers.onSelectWorkspace} 
      />
    );
    
    const apiKeyInput = screen.getByPlaceholderText('sk-...');
    fireEvent.change(apiKeyInput, { target: { value: 'new-key' } });
    fireEvent.blur(apiKeyInput);
    
    expect(mockHandlers.onSaveConfig).toHaveBeenCalledWith('DEEPSEEK_API_KEY', 'new-key');
    
    const apiBaseInput = screen.getByPlaceholderText('http://localhost:37210/v1');
    fireEvent.change(apiBaseInput, { target: { value: 'http://new-base' } });
    fireEvent.blur(apiBaseInput);
    
    expect(mockHandlers.onSaveConfig).toHaveBeenCalledWith('API_BASE', 'http://new-base');
  });

  it('triggers onSelectWorkspace when Switch button is clicked', () => {
    render(
      <SettingsModal 
        isOpen={true} 
        config={mockConfig} 
        onClose={mockHandlers.onClose}
        onSaveConfig={mockHandlers.onSaveConfig}
        onSelectWorkspace={mockHandlers.onSelectWorkspace}
      />
    );
    
    const switchBtn = screen.getByText('Switch');
    fireEvent.click(switchBtn);
    
    expect(mockHandlers.onSelectWorkspace).toHaveBeenCalled();
  });

  it('triggers onClose when X button is clicked', () => {
    render(
      <SettingsModal 
        isOpen={true} 
        config={mockConfig} 
        onClose={mockHandlers.onClose}
        onSaveConfig={mockHandlers.onSaveConfig}
        onSelectWorkspace={mockHandlers.onSelectWorkspace}
      />
    );
    
    const closeBtns = screen.getAllByRole('button');
    fireEvent.click(closeBtns[0]); 
    expect(mockHandlers.onClose).toHaveBeenCalled();
  });
});
