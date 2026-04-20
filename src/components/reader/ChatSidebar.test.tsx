import { render, screen, fireEvent } from '@testing-library/react';
import { ChatSidebar } from './ChatSidebar';
import { vi, describe, it, expect } from 'vitest';

describe('ChatSidebar Behavioral Tests', () => {
  const mockHandlers = {
    setCollapsed: vi.fn(),
    setChatQuery: vi.fn(),
    onSendMessage: vi.fn(),
  };

  it('toggles collapse state when chevron is clicked', () => {
    render(
      <ChatSidebar 
        docId={1} 
        collapsed={false} 
        chatHistory={[]} 
        chatQuery="" 
        isTyping={false} 
        {...mockHandlers} 
      />
    );
    
    // 寻找折叠按钮 (via aria-label)
    const toggleBtn = screen.getByLabelText('Toggle Sidebar');
    fireEvent.click(toggleBtn);
    
    expect(mockHandlers.setCollapsed).toHaveBeenCalledWith(true);
  });

  it('triggers onSendMessage when Send button is clicked', () => {
    render(
      <ChatSidebar 
        docId={1} 
        collapsed={false} 
        chatHistory={[]} 
        chatQuery="Summarize please" 
        isTyping={false} 
        {...mockHandlers} 
      />
    );
    
    // 寻找发送按钮 (via aria-label)
    const sendBtn = screen.getByLabelText('Send Message');
    fireEvent.click(sendBtn);
    
    expect(mockHandlers.onSendMessage).toHaveBeenCalled();
  });

  it('shows extraction form when Plus button is clicked', () => {
    render(
      <ChatSidebar 
        docId={1} 
        collapsed={false} 
        chatHistory={[]} 
        chatQuery="" 
        isTyping={false} 
        {...mockHandlers} 
      />
    );
    
    const plusBtn = screen.getByTitle('Extract New Perspective');
    fireEvent.click(plusBtn);
    
    // 验证表单文本出现
    expect(screen.getByText(/New Intelligence Dimension/i)).toBeDefined();
  });
});
