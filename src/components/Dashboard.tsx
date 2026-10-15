import React, { useRef, useState, useEffect, useMemo } from 'react';
import {
  Plus,
  Filter,
  Trash2,
  Loader2,
  BookOpen,
  FolderOpen,
  FileText,
  RefreshCw,
  Zap,
  CheckCircle2,
  AlertCircle,
  ShieldAlert,
  Search,
  Calendar,
  Building2,
  X,
  Quote,
  ArrowUpDown,
  Settings,
  Upload,
  AlertTriangle,
  Ban,
  Clock,
  RotateCcw,
  Inbox
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Document, KnowledgeClaim, AppConfig } from '../types';
import { api } from '../api/client';
import { toast } from './ui/Toast';

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

type DocStatus = 'completed' | 'partial' | 'processing' | 'queued' | 'failed';
type SortKey = 'added_desc' | 'added_asc' | 'title_asc' | 'year_desc';

const STATUS_META: Record<DocStatus, { label: string; badge: string; dot: string; border: string; bar: string }> = {
  completed: {
    label: '完成',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    dot: 'bg-emerald-500',
    border: 'border-emerald-100/60',
    bar: 'bg-emerald-500',
  },
  partial: {
    label: '仅 OCR',
    badge: 'bg-amber-50 text-amber-700 border-amber-100',
    dot: 'bg-amber-500',
    border: 'border-amber-100/60',
    bar: 'bg-amber-400',
  },
  processing: {
    label: '处理中',
    badge: 'bg-indigo-50 text-indigo-700 border-indigo-100',
    dot: 'bg-indigo-500',
    border: 'border-indigo-100',
    bar: 'bg-indigo-500',
  },
  queued: {
    label: '排队中',
    badge: 'bg-slate-100 text-slate-600 border-slate-200',
    dot: 'bg-slate-400',
    border: 'border-slate-200',
    bar: 'bg-slate-400',
  },
  failed: {
    label: '失败',
    badge: 'bg-rose-50 text-rose-700 border-rose-100',
    dot: 'bg-rose-500',
    border: 'border-rose-100',
    bar: 'bg-rose-500',
  },
};

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'added_desc', label: '最近导入' },
  { value: 'added_asc', label: '最早导入' },
  { value: 'title_asc', label: '标题 A→Z' },
  { value: 'year_desc', label: '发表年份（新→旧）' },
];

/** 容错解析 Basic Insight：坏 JSON 不应让整个列表白屏 */
const parseInsight = (doc: Document): any | null => {
  if (!doc.basic_insight_json) return null;
  try {
    return JSON.parse(doc.basic_insight_json);
  } catch {
    return null;
  }
};

const formatElapsed = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds < 0) return '';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m} 分 ${s} 秒`;
};

const formatAddedAt = (value?: string) => {
  if (!value) return '未知';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '未知';
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' });
};

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
  const [activeTasks, setActiveTasks] = useState<Document[]>([]);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Filtering States
  const [selectedJournal, setSelectedJournal] = useState<string>('all');
  const [selectedYear, setSelectedYear] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortKey>('added_desc');

  // Phase 2：知识层 Claims 检索模式
  const [mode, setMode] = useState<'papers' | 'claims'>('papers');
  const [claimsQuery, setClaimsQuery] = useState('');
  const [claimsResults, setClaimsResults] = useState<KnowledgeClaim[]>([]);
  const [claimsLoading, setClaimsLoading] = useState(false);
  const [claimsSearched, setClaimsSearched] = useState(false);
  const [claimsError, setClaimsError] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestedCount, setIngestedCount] = useState<number | null>(null);

  // 轮询处理队列（含 stage / progress / elapsed，UX-26）
  useEffect(() => {
    let cancelled = false;
    const fetchTasks = async () => {
      try {
        const tasks = await api.getActiveTasks();
        if (!cancelled) setActiveTasks(Array.isArray(tasks) ? tasks : []);
      } catch (e) {
        console.error('Task poll error', e);
      }
    };
    fetchTasks();
    const timer = setInterval(fetchTasks, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  // Phase 2：跨库检索 claims（limit 取 20，引用模式同样口径）
  const handleClaimsSearch = async () => {
    if (!claimsQuery.trim()) return;
    setClaimsLoading(true);
    setClaimsError(null);
    try {
      const data = await api.searchKnowledge(claimsQuery.trim(), 20);
      setClaimsResults(data?.results || []);
      setClaimsSearched(true);
    } catch (e) {
      console.error('Knowledge search failed', e);
      setClaimsResults([]);
      setClaimsSearched(true);
      setClaimsError('检索失败：无法连接后端服务。请确认应用已启动后重试。');
    } finally {
      setClaimsLoading(false);
    }
  };

  // 批量摄入：把已完成 OCR + Basic Insight 的文档写入知识库（幂等）
  const handleIngestAll = async () => {
    const targets = docs.filter((d) => d.ocr_status === 'completed' && d.basic_insight_json);
    if (targets.length === 0) {
      toast.info('没有可摄入的文献：需要先完成 OCR 与 Basic Insight');
      return;
    }
    setIngesting(true);
    try {
      for (const d of targets) {
        await api.ingestKnowledge(d.id);
      }
      setIngestedCount(targets.length);
      toast.success(`已摄入 ${targets.length} 篇文献，可以开始检索`);
    } catch (e) {
      console.error('Knowledge ingest failed', e);
      toast.error('摄入失败：无法连接后端服务，请稍后重试。');
    } finally {
      setIngesting(false);
    }
  };

  const handleCancelTask = async (task: Document) => {
    setCancellingId(task.id);
    try {
      const res = await api.cancelTask(task.id);
      if (res?.success) {
        toast.info(`已取消「${task.title || task.filename}」的处理`);
        onRefresh();
      } else {
        toast.error(res?.message || '取消失败：该任务可能已经结束');
      }
    } catch (e) {
      console.error('Cancel task failed', e);
      toast.error('取消失败：无法连接后端服务。');
    } finally {
      setCancellingId(null);
    }
  };

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

  // 状态判定逻辑
  const getDocStatus = (doc: Document): DocStatus => {
    if (doc.ocr_status === 'processing') return 'processing';
    if (doc.ocr_status === 'pending') return 'queued';
    if (doc.ocr_status === 'failed') return 'failed';
    const hasMarkdown = !!doc.ocr_markdown && doc.ocr_markdown.length > 10;
    if (!hasMarkdown) return 'failed';
    return doc.basic_insight_json ? 'completed' : 'partial';
  };

  // Intelligence Parsing & Filtering（检索覆盖标题 / 作者 / 期刊 / 洞察字段）
  const filteredDocs = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase();
    const matched = docs.filter((doc) => {
      const insight = parseInsight(doc) || {};
      const matchesSearch =
        !needle ||
        [
          doc.title,
          doc.filename,
          doc.authors,
          insight.journal_or_conference,
          insight.date,
          JSON.stringify(insight),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(needle);
      const matchesJournal = selectedJournal === 'all' || insight.journal_or_conference === selectedJournal;
      const matchesYear = selectedYear === 'all' || (insight.date && insight.date.toString().includes(selectedYear));

      return matchesSearch && matchesJournal && matchesYear;
    });

    const sorted = [...matched];
    sorted.sort((a, b) => {
      const ia = parseInsight(a) || {};
      const ib = parseInsight(b) || {};
      switch (sortBy) {
        case 'added_asc':
          return String(a.added_at || '').localeCompare(String(b.added_at || ''));
        case 'title_asc':
          return (a.title || a.filename).localeCompare(b.title || b.filename, 'zh-CN');
        case 'year_desc': {
          const ya = parseInt(String(ia.date || '').match(/\d{4}/)?.[0] || '0', 10);
          const yb = parseInt(String(ib.date || '').match(/\d{4}/)?.[0] || '0', 10);
          return yb - ya;
        }
        case 'added_desc':
        default:
          return String(b.added_at || '').localeCompare(String(a.added_at || ''));
      }
    });
    return sorted;
  }, [docs, searchQuery, selectedJournal, selectedYear, sortBy]);

  // Derived Filter Options
  const filterOptions = useMemo(() => {
    const journals = new Set<string>();
    const years = new Set<string>();

    docs.forEach((doc) => {
      const insight = parseInsight(doc);
      if (!insight) return;
      if (insight.journal_or_conference) journals.add(insight.journal_or_conference);
      if (insight.date) {
        const yearMatch = insight.date.toString().match(/\d{4}/);
        if (yearMatch) years.add(yearMatch[0]);
      }
    });

    return {
      journals: Array.from(journals).sort(),
      years: Array.from(years).sort((a, b) => b.localeCompare(a)),
    };
  }, [docs]);

  const hasActiveFilters = selectedJournal !== 'all' || selectedYear !== 'all' || !!searchQuery.trim();
  const resetFilters = () => {
    setSelectedJournal('all');
    setSelectedYear('all');
    onSearchChange('');
  };

  // 配置完整性（UX-32）：缺 Key / 缺模型时给出可操作提示
  const missingConfig = useMemo(() => {
    if (!config) return [];
    const missing: string[] = [];
    if (!config.DEEPSEEK_API_KEY) missing.push('OCR API Key');
    if (!config.OCR_MODEL) missing.push('OCR 模型名');
    return missing;
  }, [config]);

  const ingestibleCount = docs.filter((d) => d.ocr_status === 'completed' && d.basic_insight_json).length;

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

      <div className="flex items-end justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">文献库</h2>
            <button
              onClick={onSync}
              disabled={isSyncing}
              aria-label="同步工作区"
              title="同步工作区（扫描文件夹并处理未完成的文献）"
              className={`p-1.5 mt-1 rounded-lg transition-all ${
                isSyncing
                  ? 'text-indigo-600 bg-indigo-50'
                  : 'text-slate-400 hover:text-indigo-600 hover:bg-indigo-50'
              }`}
            >
              <RefreshCw className={`w-5 h-5 ${isSyncing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onSelectWorkspace}
              aria-label="切换工作区"
              title="切换工作区"
              className="p-1.5 mt-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            >
              <FolderOpen className="w-5 h-5" />
            </button>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            共 {docs.length} 篇文献
            {activeTasks.length > 0 && ` · ${activeTasks.length} 篇处理中`}
            {filteredDocs.length !== docs.length && ` · 当前显示 ${filteredDocs.length} 篇`}
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <button
            onClick={() => !isUploading && fileInputRef.current?.click()}
            disabled={isUploading}
            className={`flex items-center gap-2 px-5 py-2.5 text-white text-sm font-semibold rounded-xl transition-colors shadow-lg shadow-indigo-100 ${
              isUploading ? 'bg-slate-300 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            {isUploading ? '导入中…' : '导入 PDF / LaTeX'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.tex,.zip"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      </div>

      {/* 配置引导横幅（UX-32） */}
      {missingConfig.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-amber-900">尚未完成 AI 配置，导入的文献将无法处理</p>
            <p className="text-xs text-amber-700 mt-1">缺少：{missingConfig.join('、')}</p>
          </div>
          <button
            onClick={onOpenSettings}
            className="flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-xs font-bold rounded-xl hover:bg-amber-700 transition-colors shrink-0"
          >
            <Settings className="w-3.5 h-3.5" />
            去设置
          </button>
        </div>
      )}

      {/* Intelligence Filter Bar（仅论文库模式） */}
      {mode === 'papers' && (
        <div className="bg-white border border-slate-200 rounded-3xl p-3 shadow-sm flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[260px] relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
            <input
              type="text"
              placeholder="搜索标题、作者、期刊或洞察字段…"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              aria-label="搜索文献"
              className="w-full pl-11 pr-10 py-2.5 bg-slate-50 border-none rounded-2xl text-sm focus:ring-2 focus:ring-indigo-100 transition-all outline-none"
            />
            {searchQuery && (
              <button
                onClick={() => onSearchChange('')}
                aria-label="清空搜索"
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              <select
                value={selectedJournal}
                onChange={(e) => setSelectedJournal(e.target.value)}
                aria-label="按期刊筛选"
                className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-xs font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
              >
                <option value="all">全部期刊</option>
                {filterOptions.journals.map((j) => (
                  <option key={j} value={j}>
                    {j}
                  </option>
                ))}
              </select>
            </div>

            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              <select
                value={selectedYear}
                onChange={(e) => setSelectedYear(e.target.value)}
                aria-label="按年份筛选"
                className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-xs font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
              >
                <option value="all">全部年份</option>
                {filterOptions.years.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>

            <div className="relative">
              <ArrowUpDown className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortKey)}
                aria-label="排序方式"
                className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-xs font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            {hasActiveFilters && (
              <button
                onClick={resetFilters}
                className="p-2 text-rose-500 hover:bg-rose-50 rounded-xl transition-colors"
                title="清除筛选条件"
                aria-label="清除筛选条件"
              >
                <Filter className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Phase 2：Knowledge Claims 检索工具条（仅 Claims 模式） */}
      {mode === 'claims' && (
        <div className="bg-white border border-slate-200 rounded-3xl p-3 shadow-sm flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[260px] relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
            <input
              type="text"
              placeholder="在知识库中检索 claim（概念 + 逐字引文）…"
              value={claimsQuery}
              onChange={(e) => setClaimsQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.nativeEvent.isComposing) handleClaimsSearch();
              }}
              aria-label="检索知识库 claim"
              className="w-full pl-11 pr-10 py-2.5 bg-slate-50 border-none rounded-2xl text-sm focus:ring-2 focus:ring-indigo-100 transition-all outline-none"
            />
            {claimsQuery && (
              <button
                onClick={() => {
                  setClaimsQuery('');
                  setClaimsResults([]);
                  setClaimsSearched(false);
                  setClaimsError(null);
                }}
                aria-label="清空检索"
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <button
            onClick={handleClaimsSearch}
            disabled={claimsLoading || !claimsQuery.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100 disabled:bg-slate-300"
          >
            {claimsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            检索
          </button>
        </div>
      )}

      {/* Active Tasks Queue（含阶段 / 进度 / 取消，UX-26） */}
      <AnimatePresence>
        {activeTasks.length > 0 && (
          <motion.section
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="bg-indigo-600 rounded-3xl p-6 text-white shadow-2xl shadow-indigo-200">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Zap className="w-5 h-5 fill-indigo-300 text-indigo-300" />
                  <h3 className="text-sm font-black uppercase tracking-widest">处理队列</h3>
                </div>
                <span className="text-xs font-bold bg-white/20 px-2.5 py-1 rounded-full">
                  {activeTasks.length} 篇处理中
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {activeTasks.map((task) => {
                  const pct =
                    typeof task.progress === 'number' ? Math.max(0, Math.min(100, task.progress)) : null;
                  return (
                    <div
                      key={task.id}
                      className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/20"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
                            <Loader2 className="w-4 h-4 animate-spin" />
                          </div>
                          <p className="text-xs font-bold truncate" title={task.title || task.filename}>
                            {task.title || task.filename}
                          </p>
                        </div>
                        <button
                          onClick={() => handleCancelTask(task)}
                          disabled={cancellingId === task.id}
                          aria-label={`取消处理 ${task.title || task.filename}`}
                          title="取消处理"
                          className="p-1.5 rounded-lg text-indigo-100 hover:bg-white/20 transition-colors disabled:opacity-50 shrink-0"
                        >
                          {cancellingId === task.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Ban className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                      <p className="text-xs text-indigo-100 mt-3">{task.stage || '等待处理'}</p>
                      <div className="h-1.5 bg-white/20 rounded-full overflow-hidden mt-2">
                        {pct === null ? (
                          <div className="h-full w-1/3 bg-white/70 rounded-full animate-pulse" />
                        ) : (
                          <div
                            className="h-full bg-white rounded-full transition-all duration-500"
                            style={{ width: `${Math.max(pct, 3)}%` }}
                          />
                        )}
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-indigo-100 mt-1.5">
                        <span>{pct === null ? '处理中…' : `${Math.round(pct)}%`}</span>
                        {typeof task.elapsed === 'number' && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            已用时 {formatElapsed(task.elapsed)}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      <section>
        <div className="flex items-center justify-between mb-6 border-b border-slate-200 pb-px">
          <div className="flex gap-8">
            <button
              onClick={() => setMode('papers')}
              className={`font-bold text-sm border-b-2 pb-4 -mb-px transition-colors ${
                mode === 'papers' ? 'text-indigo-600 border-indigo-600' : 'text-slate-400 border-transparent hover:text-slate-600'
              }`}
            >
              文献
              {mode === 'papers' && filteredDocs.length !== docs.length && `（${filteredDocs.length}/${docs.length}）`}
            </button>
            <button
              onClick={() => setMode('claims')}
              className={`font-bold text-sm border-b-2 pb-4 -mb-px transition-colors ${
                mode === 'claims' ? 'text-indigo-600 border-indigo-600' : 'text-slate-400 border-transparent hover:text-slate-600'
              }`}
            >
              知识库检索
            </button>
          </div>
          {mode === 'papers' && (
            <div className="flex items-center gap-4 pb-4">
              {(['completed', 'partial', 'processing', 'failed'] as DocStatus[]).map((s) => (
                <div key={s} className="flex items-center gap-1.5 text-[11px] font-bold text-slate-500">
                  <div className={`w-2 h-2 rounded-full ${STATUS_META[s].dot}`} />
                  {STATUS_META[s].label}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 检索范围说明（UX-13：兑现 placeholder 承诺） */}
        {mode === 'papers' && searchQuery.trim() && (
          <p className="text-xs text-slate-500 mb-4">
            「{searchQuery.trim()}」匹配到 {filteredDocs.length} 篇（检索范围：标题、文件名、作者、期刊、年份与洞察字段）
          </p>
        )}

        {mode === 'claims' ? (
          /* ── Phase 2：Claims 检索结果 ─────────────────────── */
          claimsError ? (
            <div className="py-20 text-center space-y-4">
              <div className="w-16 h-16 bg-rose-50 rounded-full flex items-center justify-center mx-auto">
                <AlertCircle className="w-8 h-8 text-rose-400" />
              </div>
              <p className="text-slate-700 font-bold">检索失败</p>
              <p className="text-slate-500 text-sm max-w-md mx-auto">{claimsError}</p>
              <button
                onClick={handleClaimsSearch}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                重试
              </button>
            </div>
          ) : claimsSearched && claimsResults.length === 0 ? (
            <div className="py-20 text-center space-y-4">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto">
                <Search className="w-8 h-8 text-slate-300" />
              </div>
              <p className="text-slate-500 font-medium">没有匹配「{claimsQuery}」的 claim</p>
              <p className="text-slate-400 text-xs max-w-md mx-auto">
                知识库检索的是 claim 文本（概念 + 引文），不是 OCR 原文。换个关键词，或先摄入更多文献。
              </p>
            </div>
          ) : claimsResults.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {claimsResults.map((c) => {
                const targetDoc = docs.find((d) => d.id === c.doc_id);
                return (
                  <motion.div
                    key={c.claim_id}
                    whileHover={targetDoc ? { y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' } : undefined}
                    onClick={() => targetDoc && onSelectDoc(targetDoc)}
                    className={`bg-white border-2 border-slate-100 rounded-3xl p-6 flex flex-col gap-3 transition-all duration-300 group shadow-sm ${
                      targetDoc ? 'hover:border-indigo-200 cursor-pointer' : 'opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wide bg-indigo-50 text-indigo-700 border border-indigo-100">
                        {c.concept}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${
                          c.prompt_id.endsWith('~section')
                            ? 'bg-amber-50 text-amber-700 border-amber-100'
                            : 'bg-emerald-50 text-emerald-700 border-emerald-100'
                        }`}
                        title={c.prompt_id.endsWith('~section') ? '章节级转述（锚指向真实段落）' : '段落级逐字引文'}
                      >
                        {c.prompt_id.endsWith('~section') ? '章节转述' : '逐字引文'}
                      </span>
                    </div>
                    <p className="text-[13px] leading-relaxed text-slate-700 font-medium">{c.quote}</p>
                    <div className="mt-auto pt-3 border-t border-slate-100 flex items-center justify-between">
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-500 truncate">{c.title || c.paper_id || '未知论文'}</p>
                        {c.heading_path && <p className="text-[11px] text-slate-400 truncate">{c.heading_path}</p>}
                      </div>
                      {targetDoc && (
                        <span className="text-[11px] font-bold text-indigo-600 shrink-0 ml-2">打开原文 →</span>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="py-20 text-center space-y-4">
              <div className="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mx-auto">
                <Quote className="w-8 h-8 text-indigo-300" />
              </div>
              <p className="text-slate-700 font-bold">知识库</p>
              <p className="text-slate-500 text-sm max-w-md mx-auto">
                检索跨论文的结构化 claim（概念 + 逐字引文 + 可解析锚）。先摄入已完成 OCR 与 Basic Insight 的文献，再检索。
              </p>
              {ingestedCount !== null && (
                <p className="text-emerald-600 text-xs font-bold">已摄入 {ingestedCount} 篇文献，在上方检索试试。</p>
              )}
              <button
                onClick={handleIngestAll}
                disabled={ingesting || ingestibleCount === 0}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100 disabled:bg-slate-300"
              >
                {ingesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Quote className="w-4 h-4" />}
                {ingesting ? '摄入中…' : `摄入 ${ingestibleCount} 篇文献`}
              </button>
              {ingestibleCount === 0 && (
                <p className="text-slate-400 text-xs">暂无可摄入的文献：需要先完成 OCR 与 Basic Insight。</p>
              )}
            </div>
          )
        ) : isLoading ? (
          /* 骨架屏（UX-38：加载态可见） */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
              <div key={i} className="h-56 bg-white border-2 border-slate-100 rounded-3xl animate-pulse" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          /* 空库：三步引导（UX-12 / UX-32） */
          <div className="py-16 px-8 text-center bg-white border-2 border-dashed border-slate-200 rounded-3xl">
            <div className="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mx-auto">
              <Inbox className="w-8 h-8 text-indigo-400" />
            </div>
            <h3 className="text-lg font-bold text-slate-800 mt-4">文献库还是空的</h3>
            <p className="text-sm text-slate-500 mt-1">按下面三步开始：</p>
            <ol className="max-w-md mx-auto mt-6 space-y-3 text-left">
              {[
                { step: '1', title: '选择工作区', desc: '指定存放 PDF 的本地文件夹' },
                { step: '2', title: '配置 OCR API Key', desc: '在设置 → 基础配置中填写' },
                { step: '3', title: '导入 PDF / LaTeX', desc: '点击右上角按钮，或直接把文件拖到本页' },
              ].map((item) => (
                <li key={item.step} className="flex items-start gap-3 bg-slate-50 rounded-2xl px-4 py-3">
                  <span className="w-6 h-6 rounded-full bg-indigo-600 text-white text-xs font-bold flex items-center justify-center shrink-0">
                    {item.step}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-bold text-slate-700">{item.title}</span>
                    <span className="block text-xs text-slate-500 mt-0.5">{item.desc}</span>
                  </span>
                </li>
              ))}
            </ol>
            <div className="flex items-center justify-center gap-3 mt-6">
              <button
                onClick={onSelectWorkspace}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-700 text-sm font-semibold rounded-xl hover:bg-slate-50 transition-colors"
              >
                <FolderOpen className="w-4 h-4 text-indigo-600" />
                选择工作区
              </button>
              <button
                onClick={onOpenSettings}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-700 text-sm font-semibold rounded-xl hover:bg-slate-50 transition-colors"
              >
                <Settings className="w-4 h-4 text-indigo-600" />
                打开设置
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100"
              >
                <Upload className="w-4 h-4" />
                导入第一篇
              </button>
            </div>
          </div>
        ) : filteredDocs.length === 0 ? (
          /* 筛选无结果（UX-12：与空库区分） */
          <div className="py-20 text-center space-y-4">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto">
              <Search className="w-8 h-8 text-slate-300" />
            </div>
            <p className="text-slate-500 font-medium">没有符合当前筛选条件的文献</p>
            <button
              onClick={resetFilters}
              className="text-indigo-600 font-bold text-xs hover:underline"
            >
              重置全部筛选条件
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredDocs.map((doc) => {
              const status = getDocStatus(doc);
              const meta = STATUS_META[status];
              const insight = parseInsight(doc);
              const displayTitle = doc.title || doc.filename;

              return (
                <motion.div
                  key={doc.id}
                  whileHover={{ y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                  className={`bg-white border-2 rounded-3xl p-6 flex flex-col justify-between hover:border-indigo-200 transition-all duration-300 group relative overflow-hidden cursor-pointer shadow-sm ${meta.border}`}
                  onClick={() => onSelectDoc(doc)}
                >
                  <div
                    className={`absolute top-0 left-0 w-full h-1 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500 ${meta.bar}`}
                  />

                  <div>
                    <div className="flex items-center justify-between mb-5 gap-2">
                      <div
                        className={`px-2.5 py-1 rounded-full text-[11px] font-bold border flex items-center gap-1.5 ${meta.badge}`}
                      >
                        {status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                        {status === 'partial' && <ShieldAlert className="w-3 h-3" />}
                        {status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                        {status === 'queued' && <Clock className="w-3 h-3" />}
                        {status === 'failed' && <AlertCircle className="w-3 h-3" />}
                        {meta.label}
                      </div>
                      <div className="flex items-center gap-1">
                        {(status === 'failed' || status === 'partial') && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onReprocess(doc.id);
                            }}
                            aria-label={`重新处理 ${displayTitle}`}
                            title="重新处理（重跑 OCR 与洞察提取）"
                            className="p-1.5 hover:bg-indigo-50 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>

                    <h3 className="font-serif text-lg text-slate-800 leading-snug line-clamp-2 group-hover:text-indigo-600 transition-colors mb-2">
                      {displayTitle}
                    </h3>

                    {insight?.journal_or_conference && (
                      <div className="flex items-center gap-2 mb-2">
                        <Building2 className="w-3 h-3 text-indigo-400 shrink-0" />
                        <span className="text-xs font-medium text-slate-500 truncate">
                          {insight.journal_or_conference}
                        </span>
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-slate-400">
                      <FileText className="w-3 h-3 shrink-0" />
                      <p className="text-xs font-medium truncate italic max-w-[150px]">{doc.filename}</p>
                    </div>
                  </div>

                  <div className="flex items-end justify-between mt-8 gap-3">
                    <div className="flex flex-col gap-1 min-w-0">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-[11px] text-slate-400 shrink-0">发表</span>
                        <span className="text-xs text-slate-600 font-medium truncate">
                          {insight?.date || '未知'}
                        </span>
                      </div>
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-[11px] text-slate-400 shrink-0">导入</span>
                        <span className="text-xs text-slate-600 font-medium truncate">
                          {formatAddedAt(doc.added_at)}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectDoc(doc);
                        }}
                        aria-label={`阅读 ${displayTitle}`}
                        title="阅读"
                        className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all duration-200"
                      >
                        <BookOpen className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(doc);
                        }}
                        aria-label={`删除 ${displayTitle}`}
                        title="删除"
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-all duration-200"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </section>

      <footer className="fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-md border-t border-slate-200 h-12 flex items-center px-6 justify-between z-50">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${backendHealthy ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="text-xs text-slate-600 font-bold">
              {backendHealthy ? '后端已连接' : '后端未连接'}
            </span>
          </div>
          <span className="text-xs text-slate-300">|</span>
          <span className="text-xs text-slate-500 font-medium">
            {mode === 'claims'
              ? `${claimsResults.length} 条检索结果`
              : `${filteredDocs.length} / ${docs.length} 篇文献`}
          </span>
        </div>
        {!backendHealthy && (
          <span className="text-xs text-rose-600 font-bold">
            无法连接后端服务，请确认应用已完全启动或重启应用
          </span>
        )}
      </footer>
    </motion.main>
  );
};
