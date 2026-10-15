import React, { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Document, AppConfig } from '../types';
import { toast } from './ui/Toast';
import { useActiveTasks } from '../hooks/useActiveTasks';
import { useClaimsSearch } from '../hooks/useClaimsSearch';
import { useIngestAll } from '../hooks/useIngestAll';
import { useLibraryFilter } from '../hooks/useLibraryFilter';
import { DashboardMode } from './dashboard/constants';
import { ActiveTaskQueue } from './dashboard/ActiveTaskQueue';
import { ClaimsPanel, ClaimsToolbar } from './dashboard/ClaimsPanel';
import { DocCard } from './dashboard/DocCard';
import { DashboardFooter } from './dashboard/DashboardFooter';
import { DashboardHeader } from './dashboard/DashboardHeader';
import { DashboardTabs } from './dashboard/DashboardTabs';
import { FilterBar } from './dashboard/FilterBar';
import { EmptyLibrary, LibrarySkeleton, NoFilterResults } from './dashboard/LibraryStates';

interface DashboardProps {
  docs: Document[];
  onSelectDoc: (doc: Document) => void;
  onUpload: (file: File) => void;
  onDelete: (doc: Document) => void;
  onReprocess: (id: number) => void;
  onSelectWorkspace: () => void;
  onOpenSettings: () => void;
  onSync: () => void;
  onRefresh: () => void;
  isUploading: boolean;
  isLoading: boolean;
  isSyncing: boolean;
  config: AppConfig | null;
  /** 全局检索词（与 Header 共享） */
  searchQuery: string;
  onSearchChange: (value: string) => void;
  backendHealthy: boolean;
  key?: React.Key;
}

export const Dashboard = ({
  docs,
  onSelectDoc,
  onUpload,
  onDelete,
  onReprocess,
  onSelectWorkspace,
  onOpenSettings,
  onSync,
  onRefresh,
  isUploading,
  isLoading,
  isSyncing,
  config,
  searchQuery,
  onSearchChange,
  backendHealthy,
}: DashboardProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  // Phase 2：知识层 Claims 检索模式
  const [mode, setMode] = useState<DashboardMode>('papers');

  const activeTasks = useActiveTasks();
  const claims = useClaimsSearch();
  const ingest = useIngestAll(docs);
  const filter = useLibraryFilter(docs, searchQuery, onSearchChange);
  const { filteredDocs } = filter;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0]);
      e.target.value = '';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    if (!/\.(pdf|tex|zip)$/i.test(file.name)) {
      toast.error('仅支持 PDF / LaTeX(.tex) / 压缩包(.zip)');
      return;
    }
    onUpload(file);
  };

  return (
    <motion.main
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-7xl mx-auto p-8 space-y-8 pb-20 relative"
      onDragOver={(e) => {
        e.preventDefault();
        if (!isDragging) setIsDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget.contains(e.relatedTarget as Node)) return;
        setIsDragging(false);
      }}
      onDrop={handleDrop}
    >
      {/* 拖拽导入遮罩（UX-35） */}
      <AnimatePresence>
        {isDragging && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[120] bg-indigo-600/20 backdrop-blur-sm flex items-center justify-center pointer-events-none"
          >
            <div className="bg-white rounded-3xl px-10 py-8 shadow-2xl border-2 border-dashed border-indigo-300 text-center">
              <Upload className="w-10 h-10 text-indigo-500 mx-auto mb-3" />
              <p className="text-sm font-bold text-slate-800">松开即可导入</p>
              <p className="text-xs text-slate-400 mt-1">支持 PDF / LaTeX(.tex) / 压缩包(.zip)</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <DashboardHeader
        docsCount={docs.length}
        activeCount={activeTasks.length}
        filteredCount={filteredDocs.length}
        isUploading={isUploading}
        isSyncing={isSyncing}
        config={config}
        onSync={onSync}
        onSelectWorkspace={onSelectWorkspace}
        onImportClick={() => fileInputRef.current?.click()}
        onOpenSettings={onOpenSettings}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.tex,.zip"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Intelligence Filter Bar（仅论文库模式） */}
      {mode === 'papers' && (
        <FilterBar searchQuery={searchQuery} onSearchChange={onSearchChange} filter={filter} />
      )}

      {/* Phase 2：Knowledge Claims 检索工具条（仅 Claims 模式） */}
      {mode === 'claims' && <ClaimsToolbar claims={claims} />}

      {/* Active Tasks Queue（含阶段 / 进度 / 取消，UX-26） */}
      <ActiveTaskQueue tasks={activeTasks} onRefresh={onRefresh} />

      <section>
        <DashboardTabs
          mode={mode}
          onModeChange={setMode}
          searchQuery={searchQuery}
          filteredCount={filteredDocs.length}
          docsCount={docs.length}
        />

        {mode === 'claims' ? (
          <ClaimsPanel docs={docs} onSelectDoc={onSelectDoc} claims={claims} ingest={ingest} />
        ) : isLoading ? (
          <LibrarySkeleton />
        ) : docs.length === 0 ? (
          <EmptyLibrary
            onSelectWorkspace={onSelectWorkspace}
            onOpenSettings={onOpenSettings}
            onImportFirst={() => fileInputRef.current?.click()}
          />
        ) : filteredDocs.length === 0 ? (
          <NoFilterResults onReset={filter.resetFilters} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredDocs.map((doc) => (
              <DocCard
                key={doc.id}
                doc={doc}
                onSelectDoc={onSelectDoc}
                onDelete={onDelete}
                onReprocess={onReprocess}
              />
            ))}
          </div>
        )}
      </section>

      <DashboardFooter
        backendHealthy={backendHealthy}
        mode={mode}
        claimsCount={claims.results.length}
        filteredCount={filteredDocs.length}
        docsCount={docs.length}
      />
    </motion.main>
  );
};
