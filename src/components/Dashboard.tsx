import React, { useRef } from 'react';
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
  RefreshCw
} from 'lucide-react';
import { motion } from 'motion/react';

import { Document } from '../types';

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
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Library Dashboard</h2>
            <button 
              onClick={(window as any).api.selectWorkspace}
              className="p-1.5 mt-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors group relative"
              title="Switch Workspace"
            >
              <FolderOpen className="w-5 h-5" />
              <span className="absolute left-full ml-2 px-2 py-1 bg-slate-800 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50">
                Switch Workspace
              </span>
            </button>
          </div>
          <p className="text-slate-500 mt-1">Manage and organize your academic research papers.</p>
        </div>
        <button className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-100">
          <Plus className="w-4 h-4" />
          New Collection
        </button>
      </div>

      <div 
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`w-full h-40 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center transition-all group relative overflow-hidden
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
          <>
            <Loader2 className="w-10 h-10 text-indigo-600 mb-2 animate-spin" />
            <p className="text-indigo-600 font-bold">Uploading & Initializing...</p>
          </>
        ) : (
          <>
            <CloudUpload className="w-10 h-10 text-indigo-600 mb-2 group-hover:scale-110 transition-transform" />
            <p className="text-slate-600 font-bold text-lg">Drag & drop PDFs here</p>
            <p className="text-slate-400 text-sm mt-1">or click to browse from your computer</p>
          </>
        )}
      </div>

      <section>
        <div className="flex items-center justify-between mb-8 border-b border-slate-200 pb-px">
          <div className="flex gap-8">
            <button className="text-indigo-600 font-bold text-sm border-b-2 border-indigo-600 pb-4 -mb-px">All Documents</button>
            <button className="text-slate-400 font-bold text-sm hover:text-slate-600 transition-colors pb-4">OCR Processing</button>
          </div>
          <button className="flex items-center gap-1.5 text-slate-500 text-sm font-bold hover:text-slate-900 transition-colors pb-4">
            <Filter className="w-4 h-4" />
            Sort By Date
          </button>
        </div>

        {docs.length === 0 ? (
          <div className="py-20 text-center space-y-4">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto">
              <BookOpen className="w-8 h-8 text-slate-300" />
            </div>
            <p className="text-slate-400 font-medium">No documents in this workspace yet.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {docs.map((doc) => (
              <motion.div 
                key={doc.id}
                whileHover={{ y: -4, boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }}
                className={`bg-white border border-slate-200/60 rounded-3xl p-6 flex flex-col justify-between hover:border-indigo-200 transition-all duration-300 group relative overflow-hidden cursor-pointer shadow-sm
                  ${doc.ocr_status !== 'completed' ? 'opacity-90' : ''}`}
              >
                <div className={`absolute top-0 left-0 w-full h-1 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500
                  ${doc.ocr_status === 'completed' ? 'bg-indigo-500' : 'bg-amber-400'}`} />
                
                <div onClick={() => onSelectDoc(doc)}>
                  <div className="flex items-center justify-between mb-5">
                    <div className={`px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border
                      ${doc.ocr_status === 'completed' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 
                        doc.ocr_status === 'processing' ? 'bg-amber-50 text-amber-700 border-amber-100 animate-pulse' : 
                        doc.ocr_status === 'failed' ? 'bg-rose-50 text-rose-700 border-rose-100' :
                        'bg-slate-50 text-slate-500 border-slate-100'}`}>
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
                       {doc.ocr_status === 'processing' && <Loader2 className="w-3 h-3 text-amber-500 animate-spin" />}
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
                      onClick={() => onSelectDoc(doc)}
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
            <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Backend Connected</span>
          </div>
          <span className="text-[10px] text-slate-300">|</span>
          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{docs.length} Documents Found</span>
        </div>
        <div className="flex items-center gap-4 text-[10px] text-slate-400 font-bold uppercase tracking-widest">
          Workspace Mode
        </div>
      </footer>
    </motion.main>
  );
};
