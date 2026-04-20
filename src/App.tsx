import React, { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { Reader } from './components/Reader';
import { SettingsModal } from './components/SettingsModal';

// --- Types ---

type View = 'dashboard' | 'reader';

interface Document {
  id: number;
  filename: string;
  title: string;
  authors: string;
  ocr_status: 'pending' | 'processing' | 'completed' | 'failed';
  ocr_markdown?: string;
  added_at: string;
}

interface AppConfig {
  DEEPSEEK_API_KEY: string;
  API_BASE: string;
  WORKSPACE_PATH: string;
}

export default function App() {
  const [view, setView] = useState<View>('dashboard');
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // 获取后端 URL
  const getUrl = async (path: string) => {
    const port = await (window as any).api.getPythonPort();
    return `http://127.0.0.1:${port}${path}`;
  };

  // 数据加载逻辑
  const fetchData = async () => {
    try {
      const port = await (window as any).api.getPythonPort();
      if (!port) return;

      const [configRes, docsRes] = await Promise.all([
        fetch(`http://127.0.0.1:${port}/configs`),
        fetch(`http://127.0.0.1:${port}/documents`)
      ]);

      if (configRes.ok) setConfig(await configRes.json());
      if (docsRes.ok) setDocs(await docsRes.json());
    } catch (e) {
      console.error('Fetch error:', e);
    }
  };

  // 初始化获取数据及响应触发器刷新
  useEffect(() => {
    fetchData();
  }, [refreshTrigger]);

  // 监听工作区切换
  useEffect(() => {
    const cleanup = (window as any).api.onWorkspaceChanged((newPath: string) => {
      console.log('Workspace changed via Electron:', newPath);
      setRefreshTrigger(prev => prev + 1);
    });
    return () => cleanup();
  }, []);

  // 针对正在 OCR 的文档进行短时轮询 (可选)
  useEffect(() => {
    const hasProcessing = docs.some(d => d.ocr_status === 'processing' || d.ocr_status === 'pending');
    if (hasProcessing) {
      const timer = setTimeout(() => fetchData(), 3000);
      return () => clearTimeout(timer);
    }
  }, [docs]);

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const url = await getUrl('/documents/add');
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(url, { method: 'POST', body: formData });
      if (res.ok) setRefreshTrigger(prev => prev + 1);
    } catch (e) {
      console.error('Upload failed:', e);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
      const url = await getUrl(`/documents/${id}`);
      const res = await fetch(url, { method: 'DELETE' });
      if (res.ok) setRefreshTrigger(prev => prev + 1);
    } catch (e) {
      console.error('Delete failed:', e);
    }
  };

  const saveConfig = async (key: string, value: string) => {
    try {
      const url = await getUrl(`/configs?key=${key}&value=${encodeURIComponent(value)}`);
      await fetch(url, { method: 'POST' });
      setRefreshTrigger(prev => prev + 1);
    } catch (e) {
      console.error('Save config failed:', e);
    }
  };

  const handleSelectWorkspace = () => {
    (window as any).api.selectWorkspace();
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans selection:bg-indigo-100 selection:text-indigo-900 overflow-x-hidden">
      <Header 
        workspacePath={config?.WORKSPACE_PATH || ''} 
        setView={setView} 
        onOpenSettings={() => setIsSettingsOpen(true)}
      />
      
      <AnimatePresence mode="wait">
        {view === 'dashboard' ? (
          <Dashboard 
            key="dashboard"
            docs={docs}
            onSelectDoc={(doc) => {
              setSelectedDoc(doc);
              setView('reader');
            }}
            onUpload={handleUpload}
            onDelete={handleDelete}
            isUploading={isUploading}
          />
        ) : (
          <Reader 
            key="reader"
            doc={selectedDoc!} 
            onBack={() => setView('dashboard')} 
            tableStyle={config?.TABLE_STYLE}
          />
        )}
      </AnimatePresence>

      <SettingsModal 
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onSaveConfig={saveConfig}
        onSelectWorkspace={handleSelectWorkspace}
      />
    </div>
  );
}
