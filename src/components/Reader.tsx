import React, { useState, useEffect } from 'react';
import { 
  ChevronRight, 
  FileText, 
  FlaskConical, 
  BarChart3, 
  MessageSquare, 
  BookOpen
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// Sub-components
import { ReaderToolbar } from './reader/ReaderToolbar';
import { PdfViewer } from './reader/PdfViewer';
import { MarkdownViewer } from './reader/MarkdownViewer';
import { ChatSidebar } from './reader/ChatSidebar';

interface Document {
  id: number;
  filename: string;
  title: string;
  authors: string;
  ocr_markdown?: string;
  metadata_json?: string;
  added_at: string;
}

interface ReaderProps {
  doc: Document;
  onBack: () => void;
  tableStyle?: string;
  key?: React.Key;
}

export const Reader = ({ doc, onBack, tableStyle }: ReaderProps) => {
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string>('');
  const [viewMode, setViewMode] = useState<'split' | 'pdf' | 'markdown'>('split');
  const [chatQuery, setChatQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: 'user' | 'ai', content: string}[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    const fetchPdfUrl = async () => {
      const port = await (window as any).api.getPythonPort();
      const encodedFilename = encodeURIComponent(doc.filename);
      setPdfUrl(`http://127.0.0.1:${port}/files/${encodedFilename}`);
    };
    fetchPdfUrl();
  }, [doc.id, doc.filename]);

  const handleSendMessage = async () => {
    if (!chatQuery.trim()) return;
    
    const userMsg = chatQuery;
    setChatQuery('');
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsTyping(true);

    try {
      const port = await (window as any).api.getPythonPort();
      const res = await fetch(`http://127.0.0.1:${port}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: doc.id,
          query: userMsg
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setChatHistory(prev => [...prev, { role: 'ai', content: data.response }]);
      } else {
        setChatHistory(prev => [...prev, { role: 'ai', content: 'Error: Failed to get response from AI.' }]);
      }
    } catch (e) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Error: Connection failed.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex h-[calc(100vh-64px)] overflow-hidden bg-slate-100 font-sans"
    >
      {/* Left Sidebar: Structure (TOC) */}
      <motion.aside 
        animate={{ width: leftCollapsed ? 48 : 260 }}
        className="shrink-0 border-r border-slate-200 bg-slate-50 relative flex flex-col overflow-hidden z-30 shadow-sm"
      >
        <div className="p-4 border-b border-slate-200 flex items-center justify-between overflow-hidden text-slate-900">
          {!leftCollapsed && <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Structure</span>}
          <button onClick={() => setLeftCollapsed(!leftCollapsed)} className="p-1.5 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors">
            <ChevronRight className={`w-4 h-4 transition-transform ${leftCollapsed ? '' : 'rotate-180'}`} />
          </button>
        </div>
        {!leftCollapsed && (
          <nav className="p-4 space-y-1 overflow-y-auto">
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-bold shadow-sm shadow-indigo-200">
              <FileText className="w-4 h-4" /> Abstract
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-200/50 text-sm font-medium transition-colors">
              <FlaskConical className="w-4 h-4" /> 1. Introduction
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-200/50 text-sm font-medium transition-colors">
              <BarChart3 className="w-4 h-4" /> 2. Methodology
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-200/50 text-sm font-medium transition-colors">
              <MessageSquare className="w-4 h-4" /> 3. Analysis
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-200/50 text-sm font-medium transition-colors">
              <BookOpen className="w-4 h-4" /> References
            </button>
          </nav>
        )}
      </motion.aside>

      {/* Main Content Area */}
      <section className="flex-1 flex flex-col min-w-0 bg-slate-200 overflow-hidden relative z-20">
        <ReaderToolbar 
          onBack={onBack}
          viewMode={viewMode}
          setViewMode={setViewMode}
          title={doc.title || doc.filename}
        />
        
        <div className="flex-1 flex overflow-hidden">
          <AnimatePresence mode="popLayout">
            {(viewMode === 'pdf' || viewMode === 'split') && (
              <motion.div 
                key="pdf-viewer"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className={`h-full bg-slate-300 border-r border-slate-300 relative ${viewMode === 'split' ? 'w-1/2' : 'w-full'}`}
              >
                <PdfViewer url={pdfUrl} />
              </motion.div>
            )}

            {(viewMode === 'markdown' || viewMode === 'split') && (
              <motion.div 
                key="markdown-viewer"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className={`h-full bg-white overflow-y-auto px-8 lg:px-12 py-10 selection:bg-indigo-100 ${viewMode === 'split' ? 'w-1/2' : 'w-full'}`}
              >
                <MarkdownViewer 
                  content={doc.ocr_markdown} 
                  tableStyle={tableStyle} 
                  isSplitView={viewMode === 'split'} 
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </section>

      <ChatSidebar 
        collapsed={rightCollapsed}
        setCollapsed={setRightCollapsed}
        chatHistory={chatHistory}
        chatQuery={chatQuery}
        setChatQuery={setChatQuery}
        isTyping={isTyping}
        onSendMessage={handleSendMessage}
        metadataJson={doc.metadata_json}
      />
    </motion.div>
  );
};
