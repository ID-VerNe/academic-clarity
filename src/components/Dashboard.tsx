import React, { useRef, useState, useEffect } from 'react';
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
  AlertCircle
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Document } from '../types';
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

  // Poll for active tasks (OCR/Extraction)
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0]);
    }
  };

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
              className="p-1.5 mt-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors group relative"
              title="Switch Workspace"
            >
              <FolderOpen className="w-5 h-5" />
            </button>
          </div>
          <p className="text-slate-500 mt-1">Manage, OCR, and extract insights from your academic library.</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => !isUploading && fileInputRef.current?.click()}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100"
          >
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Import PDF
          </button>
        </div>
      </div>

      {/* Active Tasks Queue */}
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
                  <h3 className="text-sm font-black uppercase tracking-widest">Processing Queue</h3>
                </div>
                <span className="text-[10px] font-bold bg-white/20 px-2 py-0.5 rounded-full">{activeTasks.length} Active Tasks</span>
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
                        {task.ocr_status === 'processing' ? 'Extracting Text & Math...' : 'Waiting in queue...'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      <div 
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`w-full h-32 border-2 border-dashed rounded-3xl flex flex-col items-center justify-center transition-all group relative overflow-hidden
          ${isUploading ? 'bg-slate-50 border-slate-200 cursor-wait' : 'bg-white border-slate-200 cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/30'}`}
      >
        <input 
          type="file" 
          ref={fileInputRef} 
          className="hidden" 
          accept=".pdf" 
          onChange={handleFileChange}
        />
        
        {isUploading ? (
          <div className="flex items-center gap-3">
            <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
            <p className="text-indigo-600 font-bold">Injecting document into researcher pipeline...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <CloudUpload className="w-8 h-8 text-indigo-400 mb-2 group-hover:scale-110 transition-transform" />
            <p className="text-slate-500 font-bold text-sm">Drop PDF to initialize AI processing</p>
          </div>
        )}
      </div>

      <section>
        <div className="flex items-center justify-between mb-8 border-b border-slate-200 pb-px">
          <div className="flex gap-8">
            <button className="text-indigo-600 font-bold text-sm border-b-2 border-indigo-600 pb-4 -mb-px">Library</button>
            <button className="text-slate-400 font-bold text-sm hover:text-slate-600 transition-colors pb-4">Processing</button>
            <button className="text-slate-400 font-bold text-sm hover:text-slate-600 transition-colors pb-4">Failed</button>
          </div>
          <button className="flex items-center gap-1.5 text-slate-500 text-sm font-bold hover:text-slate-900 transition-colors pb-4">
            <Filter className="w-4 h-4" />
            Latest
          </button>
        </div>

        {docs.length === 0 ? (
          <div className="py-20 text-center space-y-4">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto">
              <BookOpen className="w-8 h-8 text-slate-300" />
            </div>
            <p className="text-slate-400 font-medium">No documents. Drop a PDF to start.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {docs.map((doc) => (
              <motion.div 
                key={doc.id}
                whileHover={{ y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                className={`bg-white border border-slate-200/60 rounded-3xl p-6 flex flex-col justify-between hover:border-indigo-200 transition-all duration-300 group relative overflow-hidden cursor-pointer shadow-sm
                  ${doc.ocr_status !== 'completed' ? 'opacity-90' : ''}`}
                onClick={() => onSelectDoc(doc)}
              >
                <div className={`absolute top-0 left-0 w-full h-1 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500
                  ${doc.ocr_status === 'completed' ? 'bg-indigo-500' : 'bg-amber-400'}`} />
                
                <div>
                  <div className="flex items-center justify-between mb-5">
                    <div className={`px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border flex items-center gap-1.5
                      ${doc.ocr_status === 'completed' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 
                        doc.ocr_status === 'processing' ? 'bg-amber-50 text-amber-700 border-amber-100' : 
                        doc.ocr_status === 'failed' ? 'bg-rose-50 text-rose-700 border-rose-100' :
                        'bg-slate-50 text-slate-500 border-slate-100'}`}>
                      {doc.ocr_status === 'completed' ? <CheckCircle2 className="w-2.5 h-2.5" /> : 
                       doc.ocr_status === 'processing' ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> :
                       doc.ocr_status === 'failed' ? <AlertCircle className="w-2.5 h-2.5" /> : null}
                      {doc.ocr_status}
                    </div>
                    <div className="flex items-center gap-2">
                       {doc.ocr_status === 'failed' && (
                         <button 
                           onClick={(e) => { e.stopPropagation(); onReprocess(doc.id); }}
                           className="p-1 hover:bg-rose-100 rounded text-rose-600 transition-colors"
                           title="Retry OCR"
                         >
                           <RefreshCw className="w-3 h-3" />
                         </button>
                       )}
                    </div>
                  </div>
                  
                  <h3 className="font-serif text-lg text-slate-800 leading-snug line-clamp-2 group-hover:text-indigo-600 transition-colors mb-2">
                    {doc.title || doc.filename}
                  </h3>
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
                      {new Date(doc.added_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <button 
                      className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all duration-200 opacity-0 group-hover:opacity-100"
                    >
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
            ))}
          </div>
        )}
      </section>

      <footer className="fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-md border-t border-slate-200 h-12 flex items-center px-6 justify-between z-50">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Pipeline Active</span>
          </div>
          <span className="text-[10px] text-slate-300">|</span>
          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{docs.length} Items Indexed</span>
        </div>
      </footer>
    </motion.main>
  );
};
