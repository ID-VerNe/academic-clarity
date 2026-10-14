import React from 'react';
import { Sparkles, Info, Tag, Calendar, User, FileText, ChevronDown, ChevronRight, ShieldCheck, ClipboardCopy, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { api } from '../../api/client';
import { DoiVerification } from '../../types';

interface MetadataNodeProps {
  label: string;
  value: any;
  depth: number;
  key?: React.Key;
}

const MetadataNode = ({ label, value, depth }: MetadataNodeProps) => {
  const [isOpen, setIsOpen] = React.useState(true);
  
  if (depth > 5) return <div className="ml-4 p-1 text-[8px] text-slate-400 italic">[Limit]</div>;

  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  const isArray = Array.isArray(value);

  const getIcon = (key: string) => {
    const k = key.toLowerCase();
    if (k.includes('author')) return <User className="w-3 h-3" />;
    if (k.includes('date') || k.includes('year')) return <Calendar className="w-3 h-3" />;
    if (k.includes('keyword') || k.includes('tag')) return <Tag className="w-3 h-3" />;
    if (k.includes('abstract') || k.includes('summary')) return <FileText className="w-3 h-3" />;
    return <Info className="w-3 h-3" />;
  };

  if (!isObject && !isArray) {
    return (
      <div className={`flex flex-col p-2 rounded-lg bg-white border border-slate-100 shadow-sm mb-2 ${depth > 0 ? 'ml-4' : ''}`}>
        <div className="flex items-center gap-2 text-slate-400 mb-1">
          {depth === 0 && getIcon(label)}
          <span className="text-[9px] font-black uppercase tracking-tighter italic">{label.replace(/_/g, ' ')}</span>
        </div>
        <p className="text-xs text-slate-600 leading-relaxed">{String(value)}</p>
      </div>
    );
  }

  if (isArray) {
    return (
      <div className={`flex flex-col p-2 rounded-lg bg-white border border-slate-100 shadow-sm mb-2 ${depth > 0 ? 'ml-4' : ''}`}>
        <div className="flex items-center gap-2 text-slate-400 mb-1">
          {depth === 0 && getIcon(label)}
          <span className="text-[9px] font-black uppercase tracking-tighter italic">{label.replace(/_/g, ' ')}</span>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-1">
          {value.map((item: any, i: number) => (
            typeof item === 'object' ? (
                <MetadataNode key={i} label={`${label}[${i}]`} value={item} depth={depth + 1} />
            ) : (
                <span key={i} className="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[10px] font-black border border-indigo-100">
                  {String(item)}
                </span>
            )
          ))}
        </div>
      </div>
    );
  }

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
  label?: string;
  docId?: number;
  onVerified?: () => void;
  key?: React.Key;
}

const DOI_STATUS_STYLE: Record<string, string> = {
  verified: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  corrected: 'bg-amber-50 text-amber-700 border-amber-100',
  mismatch: 'bg-rose-50 text-rose-700 border-rose-100',
  unverified: 'bg-slate-100 text-slate-500 border-slate-200',
};

export const MetadataPanel = ({ data, label, docId, onVerified }: MetadataPanelProps) => {
  const [verifying, setVerifying] = React.useState(false);
  const [verifyResult, setVerifyResult] = React.useState<DoiVerification | null>(null);
  const [copyNote, setCopyNote] = React.useState<string | null>(null);

  let metadata: any = null;
  
  try {
    if (data) metadata = JSON.parse(data);
  } catch (e) { console.error("JSON Parse Error", e); }

  const handleVerifyDoi = async () => {
    if (!docId) return;
    setVerifying(true);
    try {
      const res = await api.verifyDoi(docId);
      setVerifyResult(res.result || null);
      onVerified?.();
    } catch (e) {
      setVerifyResult({ status: 'unverified', doi: null, score: 0, source: 'unverified', note: 'network error' });
    } finally {
      setVerifying(false);
    }
  };

  const handleCopyBibtex = async () => {
    if (!docId) return;
    setCopyNote(null);
    try {
      const res = await api.getBibtex(docId);
      if (res.bibtex) {
        await navigator.clipboard.writeText(res.bibtex);
        setCopyNote('BibTeX copied');
      } else {
        setCopyNote('No BibTeX available');
      }
    } catch (e) {
      setCopyNote('Copy failed');
    }
  };

  if (!metadata || Object.keys(metadata).length === 0) {
    return (
      <div className="p-6 bg-slate-50/50 rounded-2xl border-2 border-dashed border-slate-200 text-center">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Empty Record</p>
      </div>
    );
  }

  const showDoiTools = label === 'Basic Insight' && !!docId && !!metadata.doi;

  return (
    <div className="space-y-2 mb-6">
      <div className="flex items-center gap-2 text-indigo-600 mb-3 px-2 border-b border-indigo-50 pb-2">
        <Sparkles className="w-3.5 h-3.5" />
        <h4 className="text-[10px] font-black uppercase tracking-[0.2em] truncate">{label || 'Insight'}</h4>
      </div>

      {showDoiTools && (
        <div className="px-1 mb-3 flex flex-wrap items-center gap-2">
          <button
            onClick={handleVerifyDoi}
            disabled={verifying}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-indigo-50 text-indigo-600 border border-indigo-100 rounded-lg text-[10px] font-black uppercase tracking-widest hover:bg-indigo-100 transition-colors disabled:opacity-50"
          >
            {verifying ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldCheck className="w-3 h-3" />}
            验证 DOI
          </button>
          <button
            onClick={handleCopyBibtex}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 text-slate-600 border border-slate-200 rounded-lg text-[10px] font-black uppercase tracking-widest hover:bg-slate-100 transition-colors"
          >
            <ClipboardCopy className="w-3 h-3" />
            复制 BibTeX
          </button>
          {verifyResult && (
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-widest border ${DOI_STATUS_STYLE[verifyResult.status] || DOI_STATUS_STYLE.unverified}`}>
              {verifyResult.status} · {verifyResult.source}
            </span>
          )}
          {copyNote && (
            <span className="text-[9px] font-bold text-slate-400">{copyNote}</span>
          )}
        </div>
      )}
      
      <div className="px-1">
        {Object.entries(metadata).map(([key, value]) => (
          <MetadataNode key={key} label={key} value={value} depth={0} />
        ))}
      </div>
    </div>
  );
};
