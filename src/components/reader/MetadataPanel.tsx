import React from 'react';
import { Sparkles, Info, Tag, Calendar, User, FileText, ChevronDown, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface MetadataNodeProps {
  label: string;
  value: any;
  depth: number;
  key?: React.Key;
}

const MetadataNode = ({ label, value, depth }: MetadataNodeProps) => {
  const [isOpen, setIsOpen] = React.useState(true);
  
  // Recursion safety: prevent stack overflow
  if (depth > 5) {
    return (
      <div className="ml-4 p-1 text-[8px] text-slate-400 italic">
        [Depth limit reached]
      </div>
    );
  }

  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  const isArray = Array.isArray(value);

  const getIcon = (key: string) => {
    const k = key.toLowerCase();
    if (k.includes('author')) return <User className="w-3 h-3" />;
    if (k.includes('date')) return <Calendar className="w-3 h-3" />;
    if (k.includes('keyword') || k.includes('tag')) return <Tag className="w-3 h-3" />;
    if (k.includes('abstract') || k.includes('summary')) return <FileText className="w-3 h-3" />;
    return <Info className="w-3 h-3" />;
  };

  // 基础类型渲染
  if (!isObject && !isArray) {
    return (
      <div className={`flex flex-col p-2 rounded-lg bg-white border border-slate-100 shadow-sm mb-2 ${depth > 0 ? 'ml-4' : ''}`}>
        <div className="flex items-center gap-2 text-slate-400 mb-1">
          {depth === 0 && getIcon(label)}
          <span className="text-[9px] font-bold uppercase tracking-tighter italic">{label.replace(/_/g, ' ')}</span>
        </div>
        <p className="text-xs text-slate-600 leading-relaxed">{String(value)}</p>
      </div>
    );
  }

  // 数组类型渲染
  if (isArray) {
    return (
      <div className={`flex flex-col p-2 rounded-lg bg-white border border-slate-100 shadow-sm mb-2 ${depth > 0 ? 'ml-4' : ''}`}>
        <div className="flex items-center gap-2 text-slate-400 mb-1">
          {depth === 0 && getIcon(label)}
          <span className="text-[9px] font-bold uppercase tracking-tighter italic">{label.replace(/_/g, ' ')}</span>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-1">
          {value.map((item: any, i: number) => (
            typeof item === 'object' ? (
                <MetadataNode key={i} label={`${label}[${i}]`} value={item} depth={depth + 1} />
            ) : (
                <span key={i} className="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[10px] font-bold border border-indigo-100">
                  {String(item)}
                </span>
            )
          ))}
        </div>
      </div>
    );
  }

  // 对象类型渲染 (递归)
  return (
    <div className={`mb-2 ${depth > 0 ? 'ml-4 border-l-2 border-slate-100 pl-2' : ''}`}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 w-full text-left p-2 hover:bg-slate-100 rounded-lg transition-colors group"
      >
        {isOpen ? <ChevronDown className="w-3 h-3 text-slate-400" /> : <ChevronRight className="w-3 h-3 text-slate-400" />}
        <div className="flex items-center gap-2 text-slate-500">
          {depth === 0 && getIcon(label)}
          <span className="text-[10px] font-black uppercase tracking-widest group-hover:text-indigo-600 transition-colors">
            {label.replace(/_/g, ' ')}
          </span>
        </div>
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            {Object.entries(value).map(([k, v]) => (
              <MetadataNode key={k} label={k} value={v} depth={depth + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

interface MetadataPanelProps {
  data?: string;
}

export const MetadataPanel = ({ data }: MetadataPanelProps) => {
  let metadata: any = null;
  
  try {
    if (data) {
      metadata = JSON.parse(data);
    }
  } catch (e) {
    console.error("Failed to parse metadata JSON", e);
  }

  if (!metadata || Object.keys(metadata).length === 0) {
    return (
      <div className="p-8 bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200 text-center">
        <Sparkles className="w-6 h-6 text-slate-200 mx-auto mb-2" />
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Waiting for extraction...</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-indigo-600 mb-4 px-2">
        <Sparkles className="w-4 h-4" />
        <h4 className="text-[10px] font-black uppercase tracking-[0.2em]">Intelligence Insight</h4>
      </div>
      
      <div className="px-1">
        {Object.entries(metadata).map(([key, value]) => (
          <MetadataNode key={key} label={key} value={value} depth={0} />
        ))}
      </div>
    </div>
  );
};
