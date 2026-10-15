import React, { useEffect, useState } from 'react';
import { AnimatePresence } from 'motion/react';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { Reader } from './components/Reader';
import { SettingsModal } from './components/SettingsModal';
import { ConfirmDialog } from './components/ui/ConfirmDialog';
import { ToastHost } from './components/ui/Toast';
import { useBackendHealth } from './hooks/useBackendHealth';
import { useDocuments } from './hooks/useDocuments';
import { useDocumentActions } from './hooks/useDocumentActions';
import { Document, View } from './types';

export default function App() {
  const [view, setView] = useState<View>('dashboard');
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  // 全局检索词：Header 与 Dashboard 共享同一个 query（UX-02）
  const [searchQuery, setSearchQuery] = useState('');

  const health = useBackendHealth();
  const {
    docs, config, isLoading, isSyncing, fetchData, handleSync, setDocs, setConfig,
  } = useDocuments(health);
  const {
    isUploading, deleteTarget, setDeleteTarget, isDeleting,
    handleUpload, confirmDelete, handleReprocess, saveConfig,
  } = useDocumentActions({ markUnhealthy: health.markUnhealthy, fetchData, setDocs });

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
  }, [handleSync, setDocs, setConfig]);

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
            backendHealthy={health.backendHealthy}
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
