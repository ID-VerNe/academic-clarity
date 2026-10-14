import React, { useRef, useState, useEffect, useMemo } from 'react';
import { 
  Plus, 
  CloudUpload, 
  Filter, 
  Eye, 
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
  Quote
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Document, KnowledgeClaim } from '../types';
import { api } from '../api/client';

interface DashboardProps {
  docs: Document[];
  onSelectDoc: (doc: Document) => void;
  onUpload: (file: File) => void;
  onDelete: (id: number) => void;
  onReprocess: (id: number) => void;
  isUploading: boolean;
  key?: React.Key;
}

export const Dashboard = ({ 
  docs, 
  onSelectDoc, 
  onUpload, 
  onDelete,
  onReprocess,
  isUploading 
}: DashboardProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeTasks, setActiveTasks] = useState<Document[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  
  // Filtering States
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedJournal, setSelectedJournal] = useState<string>('all');
  const [selectedYear, setSelectedYear] = useState<string>('all');

  // Phase 2：知识层 Claims 检索模式
  const [mode, setMode] = useState<'papers' | 'claims'>('papers');
  const [claimsQuery, setClaimsQuery] = useState('');
  const [claimsResults, setClaimsResults] = useState<KnowledgeClaim[]>([]);
  const [claimsLoading, setClaimsLoading] = useState(false);
  const [claimsSearched, setClaimsSearched] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestedCount, setIngestedCount] = useState<number | null>(null);

  // Poll for active tasks
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const tasks = await api.getActiveTasks();
        setActiveTasks(tasks);
      } catch (e) { console.error("Task poll error", e); }
    };
    
    fetchTasks();
    const timer = setInterval(fetchTasks, 2000);
    return () => clearInterval(timer);
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await api.syncWorkspace();
    } finally {
      setIsSyncing(false);
    }
  };

  // Phase 2：跨库检索 claims（limit 取 20，引用模式同样口径）
  const handleClaimsSearch = async () => {
    if (!claimsQuery.trim()) return;
    setClaimsLoading(true);
    try {
      const data = await api.searchKnowledge(claimsQuery.trim(), 20);
      setClaimsResults(data.results || []);
      setClaimsSearched(true);
    } catch (e) {
      console.error('Knowledge search failed', e);
      setClaimsResults([]);
      setClaimsSearched(true);
    } finally {
      setClaimsLoading(false);
    }
  };

  // 批量摄入：把已完成 OCR + Basic Insight 的文档写入知识库（幂等）
  const handleIngestAll = async () => {
    setIngesting(true);
    try {
      const targets = docs.filter(d => d.ocr_status === 'completed' && d.basic_insight_json);
      for (const d of targets) {
        await api.ingestKnowledge(d.id);
      }
      setIngestedCount(targets.length);
    } catch (e) {
      console.error('Knowledge ingest failed', e);
    } finally {
      setIngesting(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0]);
    }
  };

  // 状态判定逻辑
  const getDocStatus = (doc: Document) => {
    const hasMarkdown = !!doc.ocr_markdown && doc.ocr_markdown.length > 10;
    const hasMetadata = !!doc.basic_insight_json;

    if (doc.ocr_status === 'processing' || doc.ocr_status === 'pending') return 'processing';
    if (!hasMarkdown || doc.ocr_status === 'failed') return 'failed';
    if (hasMarkdown && !hasMetadata) return 'partial';
    return 'completed';
  };

  // Intelligence Parsing & Filtering
  const filteredDocs = useMemo(() => {
    return docs.filter(doc => {
      const insight = doc.basic_insight_json ? JSON.parse(doc.basic_insight_json) : {};
      const matchesSearch = (doc.title || doc.filename).toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (doc.authors || '').toLowerCase().includes(searchQuery.toLowerCase());
      const matchesJournal = selectedJournal === 'all' || insight.journal_or_conference === selectedJournal;
      const matchesYear = selectedYear === 'all' || (insight.date && insight.date.toString().includes(selectedYear));
      
      return matchesSearch && matchesJournal && matchesYear;
    });
  }, [docs, searchQuery, selectedJournal, selectedYear]);

  // Derived Filter Options
  const filterOptions = useMemo(() => {
    const journals = new Set<string>();
    const years = new Set<string>();
    
    docs.forEach(doc => {
      if (doc.basic_insight_json) {
        try {
          const insight = JSON.parse(doc.basic_insight_json);
          if (insight.journal_or_conference) journals.add(insight.journal_or_conference);
          if (insight.date) {
            const yearMatch = insight.date.toString().match(/\d{4}/);
            if (yearMatch) years.add(yearMatch[0]);
          }
        } catch(e) {}
      }
    });
    
    return {
      journals: Array.from(journals).sort(),
      years: Array.from(years).sort((a, b) => b.localeCompare(a))
    };
  }, [docs]);

  return (
    <motion.main 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-7xl mx-auto p-8 space-y-8 pb-20"
    >
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Intelligence Dashboard</h2>
            <button 
              onClick={handleSync}
              className={`p-1.5 mt-1 rounded-lg transition-all ${isSyncing ? 'text-indigo-600 bg-indigo-50 animate-spin' : 'text-slate-400 hover:text-indigo-600 hover:bg-indigo-50'}`}
              title="Sync Workspace & Trigger OCR"
            >
              <RefreshCw className="w-5 h-5" />
            </button>
            <button 
              onClick={(window as any).api.selectWorkspace}
              className="p-1.5 mt-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
              title="Switch Workspace"
            >
              <FolderOpen className="w-5 h-5" />
            </button>
          </div>
          <p className="text-slate-500 mt-1">Unified view of your research intelligence and document status.</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => !isUploading && fileInputRef.current?.click()}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100"
          >
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Import PDF / LaTeX
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

      {/* Intelligence Filter Bar（仅论文库模式） */}
      {mode === 'papers' && (
      <div className="bg-white border border-slate-200 rounded-3xl p-3 shadow-sm flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[300px] relative group">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
          <input 
            type="text"
            placeholder="Search papers, authors, or insights..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-2.5 bg-slate-50 border-none rounded-2xl text-sm focus:ring-2 focus:ring-indigo-100 transition-all outline-none"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500">
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
              className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-[12px] font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
            >
              <option value="all">All Journals</option>
              {filterOptions.journals.map(j => <option key={j} value={j}>{j}</option>)}
            </select>
          </div>

          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
            <select 
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value)}
              className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-[12px] font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
            >
              <option value="all">All Years</option>
              {filterOptions.years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>

          {(selectedJournal !== 'all' || selectedYear !== 'all' || searchQuery) && (
            <button
              onClick={() => { setSelectedJournal('all'); setSelectedYear('all'); setSearchQuery(''); }}
              className="p-2 text-rose-500 hover:bg-rose-50 rounded-xl transition-colors"
              title="Clear Filters"
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
          <div className="flex-1 min-w-[300px] relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
            <input
              type="text"
              placeholder="Search claims across the knowledge base..."
              value={claimsQuery}
              onChange={(e) => setClaimsQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleClaimsSearch()}
              className="w-full pl-11 pr-4 py-2.5 bg-slate-50 border-none rounded-2xl text-sm focus:ring-2 focus:ring-indigo-100 transition-all outline-none"
            />
            {claimsQuery && (
              <button onClick={() => { setClaimsQuery(''); setClaimsResults([]); setClaimsSearched(false); }} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500">
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
            Search Claims
          </button>
        </div>
      )}

      {/* Active Tasks Queue */}
      <AnimatePresence>
        {activeTasks.length > 0 && (
          <motion.section 
            initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="bg-indigo-600 rounded-3xl p-6 text-white shadow-2xl shadow-indigo-200">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Zap className="w-5 h-5 fill-indigo-300 text-indigo-300" />
                  <h3 className="text-sm font-black uppercase tracking-widest">Active Processing Pipeline</h3>
                </div>
                <span className="text-[10px] font-bold bg-white/20 px-2 py-0.5 rounded-full">{activeTasks.length} Documents Active</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {activeTasks.map(task => (
                  <div key={task.id} className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/20 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
                      <Loader2 className="w-5 h-5 animate-spin" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold truncate">{task.filename}</p>
                      <p className="text-[10px] text-indigo-200 font-medium uppercase tracking-tighter">
                        AI is digesting content...
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      <section>
        <div className="flex items-center justify-between mb-8 border-b border-slate-200 pb-px">
          <div className="flex gap-8">
            <button
              onClick={() => setMode('papers')}
              className={`font-bold text-sm border-b-2 pb-4 -mb-px transition-colors ${
                mode === 'papers' ? 'text-indigo-600 border-indigo-600' : 'text-slate-400 border-transparent hover:text-slate-600'}`}
            >
              Research Library {mode === 'papers' && filteredDocs.length !== docs.length && `(${filteredDocs.length}/${docs.length})`}
            </button>
            <button
              onClick={() => setMode('claims')}
              className={`font-bold text-sm border-b-2 pb-4 -mb-px transition-colors ${
                mode === 'claims' ? 'text-indigo-600 border-indigo-600' : 'text-slate-400 border-transparent hover:text-slate-600'}`}
            >
              Knowledge Claims
            </button>
          </div>
          <div className="flex items-center gap-4 pb-4">
             <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 uppercase">
                <div className="w-2 h-2 rounded-full bg-emerald-500" /> Complete
             </div>
             <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 uppercase">
                <div className="w-2 h-2 rounded-full bg-amber-500" /> OCR Only
             </div>
             <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 uppercase">
                <div className="w-2 h-2 rounded-full bg-rose-500" /> Pending/Fail
             </div>
          </div>
        </div>

        {mode === 'claims' ? (
          /* ── Phase 2：Claims 检索结果 ─────────────────────── */
          claimsSearched && claimsResults.length === 0 ? (
            <div className="py-20 text-center space-y-4">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto">
                <Search className="w-8 h-8 text-slate-300" />
              </div>
              <p className="text-slate-400 font-medium">No claims match "{claimsQuery}".</p>
              <p className="text-slate-400 text-xs">知识库检索的是 claim 文本（概念 + 引文），不是 OCR 原文。</p>
            </div>
          ) : claimsResults.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {claimsResults.map((c) => {
                const targetDoc = docs.find(d => d.id === c.doc_id);
                return (
                  <motion.div
                    key={c.claim_id}
                    whileHover={targetDoc ? { y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' } : undefined}
                    onClick={() => targetDoc && onSelectDoc(targetDoc)}
                    className={`bg-white border-2 border-slate-100 rounded-3xl p-6 flex flex-col gap-3 transition-all duration-300 group shadow-sm ${
                      targetDoc ? 'hover:border-indigo-200 cursor-pointer' : 'opacity-60'}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest bg-indigo-50 text-indigo-700 border border-indigo-100">
                        {c.concept}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-[8px] font-black uppercase tracking-widest border ${
                        c.prompt_id.endsWith('~section')
                          ? 'bg-amber-50 text-amber-700 border-amber-100'
                          : 'bg-emerald-50 text-emerald-700 border-emerald-100'}`}
                        title={c.prompt_id.endsWith('~section') ? '章节级转述（锚指向真实段落）' : '段落级逐字'}>
                        {c.prompt_id.endsWith('~section') ? 'T2 section' : 'T1 verbatim'}
                      </span>
                    </div>
                    <p className="text-[13px] leading-relaxed text-slate-700 font-medium">{c.quote}</p>
                    <div className="mt-auto pt-3 border-t border-slate-100 flex items-center justify-between">
                      <div className="min-w-0">
                        <p className="text-[10px] font-bold text-slate-500 truncate">{c.title || c.paper_id || '未知论文'}</p>
                        {c.heading_path && <p className="text-[9px] text-slate-400 truncate">{c.heading_path}</p>}
                      </div>
                      {targetDoc && (
                        <span className="text-[10px] font-black uppercase tracking-widest text-indigo-600 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2">
                          Open in Reader
                        </span>
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
              <p className="text-slate-500 font-bold">Knowledge Base</p>
              <p className="text-slate-400 text-sm max-w-md mx-auto">
                检索跨论文的结构化 claim（概念 + 逐字引文 + 可解析锚）。先摄入已完成 OCR 与 Basic Insight 的文档，再搜索。
              </p>
              {ingestedCount !== null && (
                <p className="text-emerald-600 text-xs font-bold">已摄入 {ingestedCount} 篇文档，在上方搜索试试。</p>
              )}
              <button
                onClick={handleIngestAll}
                disabled={ingesting || docs.filter(d => d.ocr_status === 'completed' && d.basic_insight_json).length === 0}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100 disabled:bg-slate-300"
              >
                {ingesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Quote className="w-4 h-4" />}
                Ingest {docs.filter(d => d.ocr_status === 'completed' && d.basic_insight_json).length} Documents
              </button>
            </div>
          )
        ) : filteredDocs.length === 0 ? (
          <div className="py-20 text-center space-y-4">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto">
              <Search className="w-8 h-8 text-slate-300" />
            </div>
            <p className="text-slate-400 font-medium">No intelligence matches your current filter.</p>
            {(selectedJournal !== 'all' || selectedYear !== 'all' || searchQuery) && (
              <button 
                onClick={() => { setSearchQuery(''); setSelectedJournal('all'); setSelectedYear('all'); }}
                className="text-indigo-600 font-bold text-xs hover:underline"
              >
                Reset all filters
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredDocs.map((doc) => {
              const status = getDocStatus(doc);
              const insight = doc.basic_insight_json ? JSON.parse(doc.basic_insight_json) : null;
              
              return (
                <motion.div 
                  key={doc.id}
                  whileHover={{ y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                  className={`bg-white border-2 rounded-3xl p-6 flex flex-col justify-between hover:border-indigo-200 transition-all duration-300 group relative overflow-hidden cursor-pointer shadow-sm
                    ${status === 'completed' ? 'border-emerald-100/50' : 
                      status === 'partial' ? 'border-amber-100/50' : 
                      status === 'processing' ? 'border-indigo-100 animate-pulse' : 'border-rose-100'}`}
                  onClick={() => onSelectDoc(doc)}
                >
                  <div className={`absolute top-0 left-0 w-full h-1 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500
                    ${status === 'completed' ? 'bg-emerald-500' : status === 'partial' ? 'bg-amber-400' : 'bg-rose-500'}`} />
                  
                  <div>
                    <div className="flex items-center justify-between mb-5">
                      <div className={`px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border flex items-center gap-1.5
                        ${status === 'completed' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 
                          status === 'partial' ? 'bg-amber-50 text-amber-700 border-amber-100' : 
                          status === 'processing' ? 'bg-indigo-50 text-indigo-700 border-indigo-100' :
                          'bg-rose-50 text-rose-700 border-rose-100'}`}>
                        {status === 'completed' ? <CheckCircle2 className="w-2.5 h-2.5" /> : 
                         status === 'partial' ? <ShieldAlert className="w-2.5 h-2.5" /> :
                         status === 'processing' ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> :
                         <AlertCircle className="w-2.5 h-2.5" />}
                        {status === 'partial' ? 'OCR READY' : status}
                      </div>
                      <div className="flex items-center gap-2">
                         {(status === 'failed' || status === 'partial') && (
                           <button 
                             onClick={(e) => { e.stopPropagation(); onReprocess(doc.id); }}
                             className="p-1.5 hover:bg-indigo-50 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors"
                             title="Retry All AI Steps"
                           >
                             <RefreshCw className="w-3.5 h-3.5" />
                           </button>
                         )}
                      </div>
                    </div>
                    
                    <h3 className="font-serif text-lg text-slate-800 leading-snug line-clamp-2 group-hover:text-indigo-600 transition-colors mb-2">
                      {doc.title || doc.filename}
                    </h3>
                    
                    {insight?.journal_or_conference && (
                      <div className="flex items-center gap-2 mb-2">
                        <Building2 className="w-3 h-3 text-indigo-400" />
                        <span className="text-[10px] font-bold text-slate-500 truncate">{insight.journal_or_conference}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-slate-400">
                      <FileText className="w-3 h-3" />
                      <p className="text-[10px] font-medium truncate italic max-w-[150px]">
                        {doc.filename}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mt-10">
                    <div className="flex flex-col">
                      <span className="text-[8px] text-slate-300 uppercase font-black tracking-tighter">Acquired</span>
                      <span className="text-[10px] text-slate-500 font-bold">
                        {insight?.date ? insight.date : new Date(doc.added_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                    </div>
                    <div className="flex gap-1">
                      <button className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all duration-200 opacity-0 group-hover:opacity-100">
                        <Eye className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={(e) => { e.stopPropagation(); onDelete(doc.id); }}
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-all duration-200 opacity-0 group-hover:opacity-100"
                        title="Delete Document"
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
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Core Active</span>
          </div>
          <span className="text-[10px] text-slate-300">|</span>
          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{filteredDocs.length} Visible Intelligence</span>
        </div>
      </footer>
    </motion.main>
  );
};
