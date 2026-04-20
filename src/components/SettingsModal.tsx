import React from 'react';
import { X, Settings, Database, Server, Cpu, FolderOpen, Save } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { AppConfig } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig | null;
  onSaveConfig: (key: string, value: string) => void;
  onSelectWorkspace: () => void;
}

export const SettingsModal = ({ 
  isOpen, 
  onClose, 
  config, 
  onSaveConfig,
  onSelectWorkspace 
}: SettingsModalProps) => {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
        />
        
        <motion.div 
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-2xl bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-200"
        >
          {/* Header */}
          <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-600 rounded-xl">
                <Settings className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">System Preferences</h2>
                <p className="text-xs text-slate-400 font-medium">Configure AI engines and research environment</p>
              </div>
            </div>
            <button 
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-full text-slate-400 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-8 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
            {/* Workspace Section */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 text-slate-900">
                <Database className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold uppercase tracking-widest">Environment</h3>
              </div>
              <div className="bg-slate-50 rounded-2xl p-5 border border-slate-100">
                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Active Workspace</label>
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-white border border-slate-200 rounded-xl px-4 py-3 text-xs font-mono text-slate-600 truncate shadow-sm">
                    {config?.WORKSPACE_PATH || 'Not selected'}
                  </div>
                  <button 
                    onClick={onSelectWorkspace}
                    className="flex items-center gap-2 px-4 py-3 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50 transition-all shadow-sm active:scale-95"
                  >
                    <FolderOpen className="w-4 h-4 text-indigo-600" />
                    Switch
                  </button>
                </div>
              </div>
            </section>

            {/* AI Engines Section */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 text-slate-900">
                <Cpu className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold uppercase tracking-widest">AI Intelligence</h3>
              </div>
              
              <div className="grid gap-6">
                <div className="space-y-3">
                  <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest">SiliconFlow API Key (OCR)</label>
                  <input 
                    type="password"
                    defaultValue={config?.DEEPSEEK_API_KEY}
                    onBlur={(e) => onSaveConfig('DEEPSEEK_API_KEY', e.target.value)}
                    placeholder="sk-..."
                    className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-xs focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400 outline-none transition-all shadow-sm"
                  />
                </div>

                <div className="space-y-3">
                  <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Extraction Engine Base URL</label>
                  <input 
                    type="text"
                    defaultValue={config?.API_BASE}
                    onBlur={(e) => onSaveConfig('API_BASE', e.target.value)}
                    placeholder="http://localhost:37210/v1"
                    className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-xs focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400 outline-none transition-all shadow-sm"
                  />
                </div>
              </div>
            </section>
          </div>

          {/* Footer */}
          <div className="px-8 py-6 bg-slate-50 border-t border-slate-100 flex justify-end">
            <button 
              onClick={onClose}
              className="flex items-center gap-2 px-8 py-3 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-700 shadow-lg shadow-indigo-100 transition-all active:scale-95"
            >
              <Save className="w-4 h-4" />
              Done
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
