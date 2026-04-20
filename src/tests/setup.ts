import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock Electron window.api
Object.defineProperty(window, 'api', {
  value: {
    getPythonPort: vi.fn().mockResolvedValue(38391),
    getWorkspace: vi.fn().mockResolvedValue('C:/mock/workspace'),
    selectWorkspace: vi.fn().mockResolvedValue('C:/new/workspace'),
    onWorkspaceChanged: vi.fn().mockReturnValue(() => {}),
  },
  writable: true,
});

// Mock fetch globally
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ success: true }),
});
