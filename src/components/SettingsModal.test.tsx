import { render, screen, fireEvent } from '@testing-library/react';
import { SettingsModal } from './SettingsModal';
import { vi, describe, it, expect } from 'vitest';
import React from 'react';

describe('SettingsModal Component', () => {
  const mockConfig = {
    WORKSPACE_PATH: '/test/path',
    DEEPSEEK_API_KEY: 'test-key',
    API_BASE: 'http://localhost:1234'
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
    
    // Find the X button (it has lucide-x)
    // Actually it's better to find it by some identifier if possible, 
    // but looking at SettingsModal.tsx:
    // <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full text-slate-400 transition-colors">
    //   <X className="w-5 h-5" />
    // </button>
    // I can find it by getting the button that contains X
    const closeBtns = screen.getAllByRole('button');
    // The first one in the header should be the X button
    fireEvent.click(closeBtns[0]); 
    expect(mockHandlers.onClose).toHaveBeenCalled();
  });
});
