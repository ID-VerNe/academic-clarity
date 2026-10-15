import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence } from 'motion/react';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { Reader } from './components/Reader';
import { SettingsModal } from './components/SettingsModal';
import { ConfirmDialog } from './components/ui/ConfirmDialog';
import { ToastHost, toast } from './components/ui/Toast';
import { api } from './api/client';
import { Document, AppConfig, View } from './types';

export default function App() {
  const [view, setView] = useState<View>('dashboard');
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [backendHealthy, setBackendHealthy] = useState(true);
  // 全局检索词：Header 与 Dashboard 共享同一个 query（UX-02）
  const [searchQuery, setSearchQuery] = useState('');
  // 删除确认弹窗（UX-15：替代原生 confirm）
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const wasUnhealthy = useRef(false);

  /** 拉取配置 + 文档列表。silent 用于后台刷新（不闪骨架屏、不重复报错） */
  const fetchData = useCallback(async (opts?: { silent?: boolean; retries?: number }) => {
    const silent = !!opts?.silent;
    const retries = opts?.retries ?? 0;
    if (!silent) setIsLoading(true);
    try {
      let lastError: unknown = null;
      for (let attempt = 0; attempt <= retries; attempt += 1) {
        try {
          const [configData, docsData] = await Promise.all([api.getConfigs(), api.getDocuments()]);
          setConfig(configData);
          setDocs(Array.isArray(docsData) ? docsData : []);
          setBackendHealthy(true);
          wasUnhealthy.current = false;
          return;
        } catch (err) {
          lastError = err;
          if (attempt < retries) await new Promise((r) => setTimeout(r, 1200));
        }
      }
      throw lastError;
    } catch (e) {
      console.error('Fetch error:', e);
      setBackendHealthy(false);
      wasUnhealthy.current = true;
      if (!silent) toast.error('无法连接后端服务，请确认应用已完全启动后重试。');
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  /** 同步工作区：完成后刷新列表并给出数量反馈（UX-03 / UX-06） */
  const handleSync = useCallback(async (opts?: { announce?: boolean }) => {
    const announce = opts?.announce ?? true;
    setIsSyncing(true);
    try {
      const res = await api.syncWorkspace();
      await fetchData({ silent: true });
      setBackendHealthy(true);
      wasUnhealthy.current = false;
      if (announce) {
        const n = Number(res?.triggered ?? 0);
        toast.success(n > 0 ? `同步完成：${n} 篇文档已加入处理队列` : '同步完成：没有待处理的新文件');
      }
    } catch (e) {
      console.error('Sync failed:', e);
      setBackendHealthy(false);
      wasUnhealthy.current = true;
      if (announce) toast.error('同步失败：无法连接后端服务，请稍后重试。');
    } finally {
      setIsSyncing(false);
    }
  }, [fetchData]);

  // 启动：先渲染已有数据，再后台同步一次（任务 A 第 1 步的「同步中」状态可见）
  useEffect(() => {
    let cancelled = false;
    (async () => {
      await fetchData({ retries: 2 });
      if (!cancelled) await handleSync({ announce: false });
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchData, handleSync]);

  // 后端健康轮询（30s）；从「断连」恢复时自动重取数据（UX-36）
  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        await api.health();
        if (cancelled) return;
        if (wasUnhealthy.current) {
          wasUnhealthy.current = false;
          setBackendHealthy(true);
          fetchData({ silent: true });
        } else {
          setBackendHealthy(true);
        }
      } catch {
        if (!cancelled) {
          setBackendHealthy(false);
          wasUnhealthy.current = true;
        }
      }
    };
    const timer = setInterval(ping, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [fetchData]);

  // 工作区切换：清空列表避免「幽灵文档」，随后重新同步
  useEffect(() => {
    const cleanup = (window as any).api.onWorkspaceChanged((newPath: string) => {
      console.log('Workspace changed via Electron:', newPath);
      setDocs([]);
      setSelectedDoc(null);
      setView('dashboard');
      setSearchQuery('');
      setConfig((prev) => (prev ? { ...prev, WORKSPACE_PATH: newPath } : prev));
      handleSync();
    });
    return () => cleanup();
  }, [handleSync]);

  // 存在处理中的文档时短轮询（3s）
  useEffect(() => {
    const hasProcessing = docs.some((d) => d.ocr_status === 'processing' || d.ocr_status === 'pending');
    if (!hasProcessing) return;
    const timer = setTimeout(() => fetchData({ silent: true }), 3000);
    return () => clearTimeout(timer);
  }, [docs, fetchData]);

  const handleUpload = async (file: File) => {
    if (isUploading) return;
    setIsUploading(true);
    try {
      const res = await api.uploadDocument(file);
      if (res?.success) {
        toast.success(`已导入「${file.name}」，正在后台处理`);
        await fetchData({ silent: true });
      } else {
        toast.error(`导入失败：${res?.detail || '服务器未接受该文件'}`);
      }
    } catch (e) {
      console.error('Upload failed:', e);
      setBackendHealthy(false);
      wasUnhealthy.current = true;
      toast.error('导入失败：无法连接后端服务，请稍后重试。');
    } finally {
      setIsUploading(false);
    }
  };

  /** 删除：先弹应用内确认框（UX-15），确认后执行并给出反馈 */
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setIsDeleting(true);
    try {
      const res = await api.deleteDocument(target.id);
      if (res?.success) {
        setDocs((prev) => prev.filter((d) => d.id !== target.id));
        toast.success(`已删除「${target.title || target.filename}」`);
        setDeleteTarget(null);
      } else {
        toast.error('删除失败：该文档可能已被移除，请刷新后重试。');
      }
    } catch (e) {
      console.error('Delete failed:', e);
      setBackendHealthy(false);
      wasUnhealthy.current = true;
      toast.error('删除失败：无法连接后端服务。');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReprocess = async (id: number) => {
    try {
      await api.reprocessDocument(id);
      toast.success('已重新加入处理队列');
      await fetchData({ silent: true });
    } catch (e) {
      console.error('Reprocess failed:', e);
      setBackendHealthy(false);
      wasUnhealthy.current = true;
      toast.error('重新处理失败：无法连接后端服务。');
    }
  };

  const saveConfig = async (key: string, value: string): Promise<boolean> => {
    try {
      await api.setConfig(key, value);
      await fetchData({ silent: true });
      toast.success('配置已保存');
      return true;
    } catch (e) {
      console.error('Save config failed:', e);
      setBackendHealthy(false);
      wasUnhealthy.current = true;
      toast.error('保存失败：无法连接后端服务。');
      return false;
    }
  };

  const handleSelectWorkspace = () => {
    (window as any).api.selectWorkspace();
  };

  // 列表刷新后同步 Reader 中的文档对象（如重新处理完成）
  const activeDoc = selectedDoc ? docs.find((d) => d.id === selectedDoc.id) ?? selectedDoc : null;

  return (
    <div className="min-h-screen bg-slate-50 font-sans selection:bg-indigo-100 selection:text-indigo-900 overflow-x-hidden">
      <Header
        workspacePath={config?.WORKSPACE_PATH || ''}
        setView={setView}
        onOpenSettings={() => setIsSettingsOpen(true)}
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchSubmit={() => setView('dashboard')}
      />

      <AnimatePresence mode="wait">
        {view === 'dashboard' || !activeDoc ? (
          <Dashboard
            key="dashboard"
            docs={docs}
            isLoading={isLoading}
            isSyncing={isSyncing}
            onSync={() => handleSync()}
            onRefresh={() => fetchData({ silent: true })}
            onSelectWorkspace={handleSelectWorkspace}
            config={config}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onOpenSettings={() => setIsSettingsOpen(true)}
            backendHealthy={backendHealthy}
            onSelectDoc={(doc) => {
              setSelectedDoc(doc);
              setView('reader');
            }}
            onUpload={handleUpload}
            onDelete={setDeleteTarget}
            onReprocess={handleReprocess}
            isUploading={isUploading}
          />
        ) : (
          <Reader
            key="reader"
            doc={activeDoc}
            onBack={() => setView('dashboard')}
            tableStyle={config?.TABLE_STYLE}
            onOpenSettings={() => setIsSettingsOpen(true)}
            onReprocess={() => handleReprocess(activeDoc.id)}
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

      <ConfirmDialog
        open={!!deleteTarget}
        danger
        busy={isDeleting}
        title="删除这篇文档？"
        message={
          deleteTarget
            ? `「${deleteTarget.title || deleteTarget.filename}」及其 OCR 结果、知识库条目将被一并删除，此操作无法撤销。`
            : ''
        }
        confirmText={isDeleting ? '删除中…' : '删除'}
        cancelText="取消"
        onConfirm={confirmDelete}
        onCancel={() => {
          if (!isDeleting) setDeleteTarget(null);
        }}
      />

      <ToastHost />
    </div>
  );
}
