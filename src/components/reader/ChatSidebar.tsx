import React, { useState, useEffect } from 'react';
import { ChevronRight, Sparkles, Send, Plus, Loader2, BrainCircuit, X } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { MetadataPanel } from './MetadataPanel';
import { api } from '../../api/client';

interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
}

interface MetadataEntry {
  id: number;
  label: string;
  content_json: string;
  created_at: string;
}

interface ChatSidebarProps {
  docId: number;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  chatHistory: ChatMessage[];
  chatQuery: string;
  setChatQuery: (query: string) => void;
  isTyping: boolean;
  onSendMessage: () => void;
}

export const ChatSidebar = ({
  docId,
  collapsed,
  setCollapsed,
  chatHistory,
  chatQuery,
  setChatQuery,
  isTyping,
  onSendMessage
}: ChatSidebarProps) => {
  const [metadataList, setMetadataList] = useState<MetadataEntry[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [showExtractForm, setShowExtractForm] = useState(false);
  const [customLabel, setCustomLabel] = useState('');
  const [customPrompt, setCustomPrompt] = useState('');

  const fetchMetadata = async () => {
    try {
      const data = await api.getMetadata(docId);
      setMetadataList(data);
    } catch (e) { console.error("Failed to fetch metadata", e); }
  };

  useEffect(() => {
    if (!collapsed) fetchMetadata();
  }, [docId, collapsed]);

  const handleRunExtraction = async () => {
    if (!customLabel || !customPrompt) return;
    setIsExtracting(true);
    try {
      await api.extractMetadata(docId, customLabel, customPrompt);
      await fetchMetadata();
      setShowExtractForm(false);
      setCustomLabel('');
      setCustomPrompt('');
    } catch (e) {
      console.error("Extraction failed", e);
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <motion.aside 
      animate={{ width: collapsed ? 48 : 380 }}
      className="shrink-0 bg-slate-50 relative flex flex-col overflow-hidden z-30 border-l border-slate-200 shadow-xl"
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-200 flex items-center justify-between overflow-hidden bg-white/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center">
          <button onClick={() => setCollapsed(!collapsed)} className="p-1.5 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors">
            <ChevronRight className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`} />
          </button>
          {!collapsed && <span className="ml-3 text-[10px] font-black uppercase tracking-widest text-slate-500">Academic Insight Hub</span>}
        </div>
        {!collapsed && (
          <button 
            onClick={() => setShowExtractForm(true)}
            className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 transition-colors border border-indigo-100"
            title="Extract New Perspective"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {collapsed ? (
        <div className="flex flex-col items-center py-8 gap-6 text-slate-300">
          <Sparkles className="w-4 h-4" />
          <BrainCircuit className="w-4 h-4" />
        </div>
      ) : (
        <div className="flex-1 flex flex-col overflow-hidden">
          
          {/* Metadata Section */}
          <div className="p-4 overflow-y-auto max-h-[50%] bg-slate-100/30 border-b border-slate-200 custom-scrollbar">
            <AnimatePresence>
               {showExtractForm && (
                 <motion.div 
                   initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
                   className="mb-6 p-4 bg-white rounded-2xl border-2 border-indigo-100 shadow-lg shadow-indigo-100/50 space-y-3 relative"
                 >
                    <button onClick={() => setShowExtractForm(false)} className="absolute top-2 right-2 text-slate-300 hover:text-slate-600"><X className="w-3 h-3" /></button>
                    <h5 className="text-[10px] font-black uppercase text-indigo-600 tracking-tighter">New Intelligence Dimension</h5>
                    <input 
                      value={customLabel} onChange={e => setCustomLabel(e.target.value)}
                      placeholder="Dimension Label (e.g. Methodology)" 
                      className="w-full text-xs p-2 rounded-lg border border-slate-100 bg-slate-50 focus:outline-none focus:border-indigo-300"
                    />
                    <textarea 
                      value={customPrompt} onChange={e => setCustomPrompt(e.target.value)}
                      placeholder="Custom Prompt (e.g. Extract the main experimental data points...)" 
                      className="w-full text-xs p-2 rounded-lg border border-slate-100 bg-slate-50 h-20 focus:outline-none focus:border-indigo-300 resize-none"
                    />
                    <button 
                      onClick={handleRunExtraction}
                      disabled={isExtracting || !customLabel || !customPrompt}
                      className="w-full py-2 bg-indigo-600 text-white rounded-xl text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2"
                    >
                      {isExtracting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                      Start Extraction
                    </button>
                 </motion.div>
               )}
            </AnimatePresence>

            <div className="space-y-4">
              {metadataList.map((meta) => (
                <MetadataPanel key={meta.id} data={meta.content_json} label={meta.label} />
              ))}
              {metadataList.length === 0 && !isExtracting && (
                <div className="py-10 text-center opacity-30">
                  <BrainCircuit className="w-10 h-10 mx-auto mb-2" />
                  <p className="text-[10px] font-bold uppercase">Synthesizing...</p>
                </div>
              )}
            </div>
          </div>

          {/* Chat Section */}
          <div className="flex-1 flex flex-col overflow-hidden bg-white">
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth custom-scrollbar">
               {chatHistory.length === 0 ? (
                 <div className="h-full flex flex-col items-center justify-center opacity-20 grayscale space-y-4">
                    <Sparkles className="w-10 h-10 text-indigo-400" />
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 text-center">Researcher Terminal</p>
                 </div>
               ) : (
                 chatHistory.map((msg, i) => (
                   <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] p-3 rounded-2xl text-[13px] leading-relaxed shadow-sm ${
                        msg.role === 'user' 
                          ? 'bg-indigo-600 text-white rounded-tr-none' 
                          : 'bg-slate-50 border border-slate-100 text-slate-700 rounded-tl-none font-medium'
                      }`}>
                        {msg.content}
                      </div>
                   </div>
                 ))
               )}
               {isTyping && (
                 <div className="flex justify-start">
                    <div className="bg-slate-50 border border-slate-100 p-3 rounded-2xl rounded-tl-none flex gap-1 items-center shadow-sm">
                      <div className="w-1 h-1 bg-indigo-300 rounded-full animate-bounce" />
                      <div className="w-1 h-1 bg-indigo-300 rounded-full animate-bounce [animation-delay:0.2s]" />
                      <div className="w-1 h-1 bg-indigo-300 rounded-full animate-bounce [animation-delay:0.4s]" />
                    </div>
                 </div>
               )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-slate-100 bg-white">
               <div className="relative flex items-center gap-2">
                  <input 
                    value={chatQuery}
                    onChange={(e) => setChatQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && onSendMessage()}
                    className="w-full text-xs rounded-2xl border border-slate-200 bg-slate-50 pl-4 pr-12 py-4 text-slate-700 placeholder:text-slate-400 focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400 outline-none transition-all font-medium" 
                    placeholder="Deep query document..." 
                    type="text" 
                  />
                  <button 
                    onClick={onSendMessage}
                    disabled={isTyping || !chatQuery.trim()}
                    className="absolute right-2 p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:bg-slate-300 transition-all shadow-lg shadow-indigo-100 active:scale-95"
                  >
                    <Send className="w-4 h-4" />
                  </button>
               </div>
            </div>
          </div>
        </div>
      )}
    </motion.aside>
  );
};
