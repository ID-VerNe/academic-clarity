import { render, screen, fireEvent, waitFor, waitForElementToBeRemoved } from '@testing-library/react';
import { ChatSidebar } from './ChatSidebar';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the API client
vi.mock('../../api/client', () => ({
  api: {
    getMetadata: vi.fn().mockResolvedValue([]),
    extractMetadata: vi.fn(),
  }
}));

describe('ChatSidebar Behavioral Tests', () => {
  const mockHandlers = {
    setCollapsed: vi.fn(),
    setChatQuery: vi.fn(),
    onSendMessage: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

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

  it('shows extraction form when Plus button is clicked and closes when X is clicked', async () => {
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
    
    // Verify form text appears
    const heading = screen.getByText(/New Intelligence Dimension/i);
    expect(heading).toBeDefined();

    // Click X button
    const closeBtn = heading.previousElementSibling;
    fireEvent.click(closeBtn!);

    // Wait for form to be removed from DOM
    await waitForElementToBeRemoved(() => screen.queryByText(/New Intelligence Dimension/i));
  });

  it('triggers setChatQuery when typing in the input', () => {
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
    
    const input = screen.getByPlaceholderText(/Deep query document/i);
    fireEvent.change(input, { target: { value: 'Hello' } });
    
    expect(mockHandlers.setChatQuery).toHaveBeenCalledWith('Hello');
  });

  it('triggers onSendMessage when Enter is pressed in the input', () => {
    render(
      <ChatSidebar 
        docId={1} 
        collapsed={false} 
        chatHistory={[]} 
        chatQuery="Some query" 
        isTyping={false} 
        {...mockHandlers} 
      />
    );
    
    const input = screen.getByPlaceholderText(/Deep query document/i);
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
    
    expect(mockHandlers.onSendMessage).toHaveBeenCalled();
  });
});
