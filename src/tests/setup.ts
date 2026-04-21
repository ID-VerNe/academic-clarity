import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock Electron window.api
Object.defineProperty(window, 'api', {
  value: {
    getPythonPort: vi.fn().mockResolvedValue(38392),
    getWorkspace: vi.fn().mockResolvedValue('C:/mock/workspace'),
    selectWorkspace: vi.fn().mockResolvedValue('C:/new/workspace'),
    onWorkspaceChanged: vi.fn().mockReturnValue(() => {}),
  },
  writable: true,
});

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock DOMMatrix (required by pdf.js in Node/JSDOM)
if (!global.DOMMatrix) {
  (global as any).DOMMatrix = class DOMMatrix {
    constructor() {}
    static fromMatrix() { return new DOMMatrix(); }
  };
}

// Mock PointerEvent (needed for some drag-drop tests in jsdom)
if (!global.PointerEvent) {
  (global as any).PointerEvent = class PointerEvent extends MouseEvent {};
}

// Mock fetch globally
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ success: true }),
});
