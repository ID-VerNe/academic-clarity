import React from 'react';
import { ChevronRight, Sparkles, Send } from 'lucide-react';
import { motion } from 'motion/react';
import { MetadataPanel } from './MetadataPanel';

interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
}

interface ChatSidebarProps {
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  chatHistory: ChatMessage[];
  chatQuery: string;
  setChatQuery: (query: string) => void;
  isTyping: boolean;
  onSendMessage: () => void;
  metadataJson?: string;
}

export const ChatSidebar = ({
  collapsed,
  setCollapsed,
  chatHistory,
  chatQuery,
  setChatQuery,
  isTyping,
  onSendMessage,
  metadataJson
}: ChatSidebarProps) => {
  return (
    <motion.aside 
      animate={{ width: collapsed ? 48 : 340 }}
      className="shrink-0 bg-slate-50 relative flex flex-col overflow-hidden z-30 border-l border-slate-200 shadow-xl"
    >
      <div className="p-4 border-b border-slate-200 flex items-center overflow-hidden bg-white/50">
        <button onClick={() => setCollapsed(!collapsed)} className="p-1.5 hover:bg-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 transition-colors">
          <ChevronRight className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`} />
        </button>
        {!collapsed && <span className="ml-3 text-[10px] font-bold uppercase tracking-widest text-slate-400">Academic AI Assistant</span>}
      </div>

      {collapsed ? (
        <div className="flex flex-col items-center py-8 gap-6 text-slate-300">
          <Sparkles className="w-4 h-4" />
        </div>
      ) : (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Metadata Section */}
          <div className="p-4 overflow-y-auto max-h-[40%] bg-slate-100/50 border-b border-slate-200 scrollbar-hide">
            <MetadataPanel data={metadataJson} />
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">
             {chatHistory.length === 0 ? (
               <div className="h-full flex flex-col items-center justify-center opacity-40 grayscale space-y-4">
                  <Sparkles className="w-10 h-10 text-indigo-400" />
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">How can I help you today?</p>
               </div>
             ) : (
               chatHistory.map((msg, i) => (
                 <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed shadow-sm ${
                      msg.role === 'user' 
                        ? 'bg-indigo-600 text-white rounded-tr-none' 
                        : 'bg-white border border-slate-100 text-slate-700 rounded-tl-none'
                    }`}>
                      {msg.content}
                    </div>
                 </div>
               ))
             )}
             {isTyping && (
               <div className="flex justify-start">
                  <div className="bg-white border border-slate-100 p-3 rounded-2xl rounded-tl-none flex gap-1 items-center shadow-sm">
                    <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce" />
                    <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce [animation-delay:0.2s]" />
                    <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce [animation-delay:0.4s]" />
                  </div>
               </div>
             )}
          </div>

          <div className="p-4 border-t border-slate-200 bg-white/50">
             <div className="relative flex items-center gap-2">
                <input 
                  value={chatQuery}
                  onChange={(e) => setChatQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && onSendMessage()}
                  className="w-full text-xs rounded-xl border border-slate-200 bg-white pl-3 pr-10 py-3 text-slate-700 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 outline-none transition-all shadow-sm font-sans" 
                  placeholder="Ask document context..." 
                  type="text" 
                />
                <button 
                  onClick={onSendMessage}
                  disabled={isTyping || !chatQuery.trim()}
                  className="absolute right-1.5 p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-slate-300 transition-colors shadow-lg shadow-indigo-100"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
             </div>
          </div>
        </div>
      )}
    </motion.aside>
  );
};
