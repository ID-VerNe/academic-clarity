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
  blob: async () => new Blob([]),
});

// jsdom 未实现 Blob URL（PdfViewer 渲染 blob、导出下载用）
if (!(URL as any).createObjectURL) {
  (URL as any).createObjectURL = vi.fn(() => 'blob:mock-url');
}
if (!(URL as any).revokeObjectURL) {
  (URL as any).revokeObjectURL = vi.fn();
}

// jsdom 未实现 Range.getBoundingClientRect（划词工具条用它定位）
if (!(Range.prototype as any).getBoundingClientRect) {
  (Range.prototype as any).getBoundingClientRect = () => ({
    x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0,
    toJSON: () => ({}),
  });
}

// jsdom 未实现滚动相关 API（组件用于自动滚动 / 定位目录标题）
Element.prototype.scrollIntoView = vi.fn();
if (!window.scrollTo) {
  (window as any).scrollTo = vi.fn();
}
window.HTMLElement.prototype.scrollTo = vi.fn();

// 剪贴板（DOI/BibTeX 复制、划词复制）
if (!navigator.clipboard) {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn().mockResolvedValue(undefined), readText: vi.fn().mockResolvedValue('') },
    writable: true,
  });
}
