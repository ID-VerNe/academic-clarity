import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// ── Windows 盘符大小写规范化（修复 React 双实例） ────────────────────────────
// Windows 下进程 cwd 的盘符可能是小写（c:\...），而 node_modules 中 pnpm 符号
// 链接经 realpath 解析后是规范大写（C:\...）。同一个 react.development.js 因此
// 被以两条路径各加载一次，React 内部 dispatcher 互不可见，报
// "Invalid hook call / Cannot read properties of null (reading 'useState')"。
// 解决：把 cwd 与 vitest root 的盘符统一为规范大写，使全部模块路径一致。
const canonicalRoot = (() => {
  const cwd = process.cwd();
  const fixed = cwd.replace(/^([a-z]):/, (_, d: string) => `${d.toUpperCase()}:`);
  if (fixed !== cwd) {
    try {
      process.chdir(fixed);
    } catch {
      return cwd; // 规范化失败时保持原样，不影响非 Windows 环境
    }
  }
  return process.cwd();
})();

export default defineConfig({
  plugins: [react()],
  test: {
    root: canonicalRoot,
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.ts'],
    // 全量套件与 8 路 Python 测试并发时 CPU 争抢会让交互型用例触碰默认 5s 上限
    // （实测 4 个用例假超时、单独跑 14s 全绿）——放宽到 20s：仍能抓住真挂死，
    // 不再拿时钟赛跑当门禁（与 run_all_tests.py 的 600s 超时策略一致）。
    testTimeout: 20000,
    alias: {
      '@': path.resolve(canonicalRoot, 'src'),
    },
  },
});
