import React, { useState, useEffect } from 'react';
import { 
  X, 
  Key, 
  FolderOpen,
  Layout
} from 'lucide-react';
import { motion } from 'motion/react';

interface AppConfig {
  DEEPSEEK_API_KEY: string;
  API_BASE: string;
  WORKSPACE_PATH: string;
  TABLE_STYLE?: 'three-line' | 'full-line' | 'no-line';
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig | null;
  onSaveConfig: (key: string, value: string) => Promise<void>;
  onSelectWorkspace: () => void;
}

export const SettingsModal = ({ 
  isOpen, 
  onClose, 
  config, 
  onSaveConfig,
  onSelectWorkspace 
}: SettingsModalProps) => {
  const [apiKey, setApiKey] = useState(config?.DEEPSEEK_API_KEY || '');
  const currentTableStyle = config?.TABLE_STYLE || 'three-line';
  
  useEffect(() => {
    if (config) setApiKey(config.DEEPSEEK_API_KEY);
  }, [config]);

  if (!isOpen) return null;

  const tableStyles = [
    { id: 'three-line', label: '三线表' },
    { id: 'full-line', label: '全边框' },
    { id: 'no-line', label: '不显示' }
  ];

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
      >
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-bold text-lg text-slate-900">Application Settings</h3>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-lg text-slate-400">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 space-y-6">
          {/* API Key */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <Key className="w-3 h-3" /> DeepSeek API Key
            </label>
            <div className="flex gap-2">
              <input 
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="flex-1 h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 outline-none"
                placeholder="sk-..."
              />
              <button 
                onClick={() => onSaveConfig('DEEPSEEK_API_KEY', apiKey)}
                className="px-4 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 transition-colors"
              >
                Save
              </button>
            </div>
          </div>

          {/* Table Style Selection */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <Layout className="w-3 h-3" /> Table Render Style
            </label>
            <div className="flex p-1 bg-slate-100 rounded-xl border border-slate-200">
              {tableStyles.map((style) => (
                <button
                  key={style.id}
                  onClick={() => onSaveConfig('TABLE_STYLE', style.id)}
                  className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
                    currentTableStyle === style.id 
                      ? 'bg-white text-indigo-600 shadow-sm border border-slate-200/50' 
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {style.label}
                </button>
              ))}
            </div>
          </div>

          {/* Workspace */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <FolderOpen className="w-3 h-3" /> Workspace
            </label>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
              <p className="text-xs text-slate-600 break-all leading-relaxed">
                {config?.WORKSPACE_PATH}
              </p>
              <button 
                onClick={onSelectWorkspace}
                className="w-full py-2 bg-white border border-slate-200 text-slate-700 text-xs font-bold rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
              >
                Change Workspace Directory
              </button>
            </div>
          </div>
        </div>
        
        <div className="p-6 bg-slate-50 text-center border-t border-slate-100">
          <button 
            onClick={onClose}
            className="text-sm font-bold text-indigo-600 hover:text-indigo-700 transition-colors"
          >
            Done
          </button>
        </div>
      </motion.div>
    </div>
  );
};
