import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  ChevronRight, 
  FileText, 
  FlaskConical, 
  BarChart3, 
  MessageSquare, 
  BookOpen,
  GripVertical
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// Sub-components
import { ReaderToolbar } from './reader/ReaderToolbar';
import { PdfViewer } from './reader/PdfViewer';
import { MarkdownViewer } from './reader/MarkdownViewer';
import { ChatSidebar } from './reader/ChatSidebar';
import { api } from '../api/client';

import { Document } from '../types';

interface ReaderProps {
  doc: Document;
  onBack: () => void;
  tableStyle?: string;
  key?: React.Key;
}

export const Reader = ({ doc, onBack, tableStyle }: ReaderProps) => {
  const [pdfUrl, setPdfUrl] = useState<string>('');
  const [viewMode, setViewMode] = useState<'split' | 'pdf' | 'markdown'>('split');
  const [chatQuery, setChatQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: 'user' | 'ai', content: string}[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  
  // Resizable Logic: Left Sidebar
  const [leftWidth, setLeftWidth] = useState(260);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const isResizingLeft = useRef(false);

  // Resizable Logic: Right Sidebar
  const [rightWidth, setRightWidth] = useState(400);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const isResizingRight = useRef(false);

  // Resizable Logic: Mid Split
  const [splitRatio, setSplitRatio] = useState(50); // percentage for PDF
  const isResizingSplit = useRef(false);

  useEffect(() => {
    const fetchPdfUrl = async () => {
      try {
        const url = await api.getPdfUrl(doc.filename);
        setPdfUrl(url);
      } catch (e) {
        console.error('Failed to get PDF URL:', e);
      }
    };
    fetchPdfUrl();
  }, [doc.id, doc.filename]);

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (isResizingLeft.current) {
      const newWidth = Math.max(48, Math.min(600, e.clientX));
      setLeftWidth(newWidth);
      setLeftCollapsed(newWidth < 100);
    } else if (isResizingRight.current) {
      const newWidth = Math.max(48, Math.min(800, window.innerWidth - e.clientX));
      setRightWidth(newWidth);
      setRightCollapsed(newWidth < 100);
    } else if (isResizingSplit.current) {
      const centerArea = window.innerWidth - (leftCollapsed ? 48 : leftWidth) - (rightCollapsed ? 48 : rightWidth);
      const relativeX = e.clientX - (leftCollapsed ? 48 : leftWidth);
      const newRatio = Math.max(10, Math.min(90, (relativeX / centerArea) * 100));
      setSplitRatio(newRatio);
    }
  }, [leftWidth, leftCollapsed, rightWidth, rightCollapsed]);

  const onMouseUp = useCallback(() => {
    isResizingLeft.current = false;
    isResizingRight.current = false;
    isResizingSplit.current = false;
    document.body.style.cursor = 'default';
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const startResizing = (type: 'left' | 'right' | 'split') => {
    if (type === 'left') isResizingLeft.current = true;
    if (type === 'right') isResizingRight.current = true;
    if (type === 'split') isResizingSplit.current = true;
    document.body.style.cursor = 'col-resize';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  const handleSendMessage = async () => {
    if (!chatQuery.trim()) return;
    
    const userMsg = chatQuery;
    setChatQuery('');
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsTyping(true);

    try {
      const data = await api.chat(doc.id, userMsg);
      if (data.response) {
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
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-slate-100 font-sans select-none">
      {/* Left Sidebar */}
      <motion.aside 
        animate={{ width: leftCollapsed ? 48 : leftWidth }}
        className="shrink-0 border-r border-slate-200 bg-slate-50 relative flex flex-col overflow-hidden z-30 shadow-sm"
      >
        <div className="p-4 border-b border-slate-200 flex items-center justify-between overflow-hidden text-slate-900">
          {!leftCollapsed && <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Structure</span>}
          <button 
            aria-label="Toggle Left Sidebar"
            onClick={() => setLeftCollapsed(!leftCollapsed)} 
            className="p-1.5 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors"
          >
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

        {/* Resize Handle: Left */}
        <div 
          onMouseDown={() => startResizing('left')}
          className="absolute right-0 top-0 bottom-0 w-1 hover:bg-indigo-400 cursor-col-resize z-50 transition-colors flex items-center justify-center group"
        >
           <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
        </div>
      </motion.aside>

      {/* Main Area */}
      <section className="flex-1 flex flex-col min-w-0 bg-slate-200 overflow-hidden relative z-20">
        <ReaderToolbar 
          onBack={onBack}
          viewMode={viewMode}
          setViewMode={setViewMode}
          title={doc.title || doc.filename}
        />
        
        <div className="flex-1 flex overflow-hidden">
          {(viewMode === 'pdf' || viewMode === 'split') && (
            <div 
              style={{ width: viewMode === 'split' ? `${splitRatio}%` : '100%' }}
              className="h-full bg-slate-300 relative"
            >
              <PdfViewer url={pdfUrl} />
            </div>
          )}

          {viewMode === 'split' && (
            <div 
              onMouseDown={() => startResizing('split')}
              className="w-1.5 bg-slate-300 hover:bg-indigo-400 cursor-col-resize transition-colors z-40 flex items-center justify-center group"
            >
               <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
            </div>
          )}

          {(viewMode === 'markdown' || viewMode === 'split') && (
            <div 
              style={{ width: viewMode === 'split' ? `${100 - splitRatio}%` : '100%' }}
              className="h-full bg-white overflow-y-auto px-8 lg:px-12 py-10 selection:bg-indigo-100"
            >
              <MarkdownViewer 
                content={doc.ocr_markdown} 
                tableStyle={tableStyle} 
                isSplitView={viewMode === 'split'} 
              />
            </div>
          )}
        </div>
      </section>

      {/* Right Sidebar */}
      <motion.aside 
        animate={{ width: rightCollapsed ? 48 : rightWidth }}
        className="shrink-0 bg-slate-50 border-l border-slate-200 relative overflow-hidden flex flex-col z-30 shadow-sm"
      >
        {/* Resize Handle: Right */}
        <div 
          onMouseDown={() => startResizing('right')}
          className="absolute left-0 top-0 bottom-0 w-1 hover:bg-indigo-400 cursor-col-resize z-50 transition-colors flex items-center justify-center group"
        >
           <GripVertical className="w-3 h-3 text-white opacity-0 group-hover:opacity-100" />
        </div>

        <ChatSidebar 
          docId={doc.id}
          collapsed={rightCollapsed}
          setCollapsed={setRightCollapsed}
          chatHistory={chatHistory}
          chatQuery={chatQuery}
          setChatQuery={setChatQuery}
          isTyping={isTyping}
          onSendMessage={handleSendMessage}
        />
      </motion.aside>
    </div>
  );
};
