import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig, loadEnv} from 'vite';
import electron from 'vite-plugin-electron';
import renderer from 'vite-plugin-electron-renderer';

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [
      react(),
      tailwindcss(),
      electron([
        {
          entry: 'electron/main.ts',
        },
        {
          entry: 'electron/preload.ts',
        },
      ]),
      renderer(),
    ],
    optimizeDeps: {
      include: [
        'react', 
        'react-dom', 
        'lucide-react', 
        'motion', 
        'react-dom/client',
        'react/jsx-dev-runtime',
        'react-markdown',
        'remark-gfm',
        'remark-math',
        'rehype-raw',
        'rehype-katex',
        'katex'
      ],
      force: true,
    },
    build: {
      minify: false,
      cssCodeSplit: false,
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom'],
            'ui-vendor': ['lucide-react', 'motion'],
          },
        },
      },
    },
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      port: 30517,
      strictPort: false,
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true' ? {
        host: '127.0.0.1',
      } : false,
      host: '127.0.0.1',
      watch: {
        ignored: ['**/node_modules/**', '**/dist/**', '**/dist-electron/**', '**/python_embed/**'],
      },
    },
  };
});
