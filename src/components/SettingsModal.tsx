import React, { useState, useEffect } from 'react';
import { X, Settings, Database, Cpu, FolderOpen, Save, Plus, Trash2, RefreshCw, CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { AppConfig, MultiKeyStats, KeyConfig, KeyPoolStats } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig | null;
  onSaveConfig: (key: string, value: string) => void;
  onSelectWorkspace: () => void;
}

type TabType = 'basic' | 'ocr-keys' | 'llm-keys';

interface ValidationError {
  field: string;
  message: string;
}

interface KeyStatsDisplay {
  api_key: string;
  api_base: string;
  model_name: string;
  max_concurrent: number;
  rpm_limit: number;
  tpm_limit: number;
  enabled: boolean;
  is_healthy?: boolean;
  active_requests?: number;
  rpm_used?: number;
  tpm_used?: number;
  consecutive_errors?: number;
}

export const SettingsModal = ({
  isOpen,
  onClose,
  config,
  onSaveConfig,
  onSelectWorkspace
}: SettingsModalProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('basic');
  const [multiKeyStats, setMultiKeyStats] = useState<MultiKeyStats | null>(null);
  const [ocrKeys, setOcrKeys] = useState<KeyConfig[]>([]);
  const [llmKeys, setLlmKeys] = useState<KeyConfig[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);

  useEffect(() => {
    if (isOpen) {
      loadMultiKeyStats();
    }
  }, [isOpen]);

  const loadMultiKeyStats = async () => {
    try {
      const stats = await window.api.getMultiKeyStats();
      setMultiKeyStats(stats);
    } catch (error) {
      console.error('Failed to load multi-key stats:', error);
    }
  };

  const validateKeyConfig = (key: KeyConfig, index: number, type: 'ocr' | 'llm'): ValidationError[] => {
    const newErrors: ValidationError[] = [];

    if (!key.api_key || key.api_key.trim() === '') {
      newErrors.push({ field: `${type}-${index}-api_key`, message: 'API Key is required' });
    }

    if (!key.api_base || key.api_base.trim() === '') {
      newErrors.push({ field: `${type}-${index}-api_base`, message: 'API Base URL is required' });
    } else if (!key.api_base.startsWith('http://') && !key.api_base.startsWith('https://')) {
      newErrors.push({ field: `${type}-${index}-api_base`, message: 'API Base URL must start with http:// or https://' });
    }

    if (!key.model_name || key.model_name.trim() === '') {
      newErrors.push({ field: `${type}-${index}-model_name`, message: 'Model name is required for multi-key mode' });
    }

    if (key.max_concurrent !== undefined && key.max_concurrent < 1) {
      newErrors.push({ field: `${type}-${index}-max_concurrent`, message: 'Max concurrent must be at least 1' });
    }

    if (key.rpm_limit !== undefined && key.rpm_limit < 1) {
      newErrors.push({ field: `${type}-${index}-rpm_limit`, message: 'RPM limit must be at least 1' });
    }

    if (key.tpm_limit !== undefined && key.tpm_limit < 1) {
      newErrors.push({ field: `${type}-${index}-tpm_limit`, message: 'TPM limit must be at least 1' });
    }

    return newErrors;
  };

  const handleSaveKeys = async (type: 'ocr' | 'llm') => {
    const keys = type === 'ocr' ? ocrKeys : llmKeys;
    const allErrors: ValidationError[] = [];

    keys.forEach((key, index) => {
      allErrors.push(...validateKeyConfig(key, index, type));
    });

    if (allErrors.length > 0) {
      setErrors(allErrors);
      return;
    }

    setErrors([]);
    setIsSaving(true);
    try {
      if (type === 'ocr') {
        await window.api.updateOcrKeys(JSON.stringify(keys));
      } else {
        await window.api.updateLlmKeys(JSON.stringify(keys));
      }
      await loadMultiKeyStats();
      setShowAddForm(false);
    } catch (error) {
      console.error('Failed to save keys:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      setErrors([{ field: 'general', message: `Failed to save: ${errorMessage}` }]);
    } finally {
      setIsSaving(false);
    }
  };

  const addKey = (type: 'ocr' | 'llm') => {
    const newKey: KeyConfig = {
      api_key: '',
      api_base: type === 'ocr' ? 'https://api.siliconflow.cn/v1' : 'http://localhost:37210/v1',
      model_name: '',
      max_concurrent: 5,
      rpm_limit: 60,
      tpm_limit: 100000,
      enabled: true
    };
    if (type === 'ocr') {
      setOcrKeys([...ocrKeys, newKey]);
    } else {
      setLlmKeys([...llmKeys, newKey]);
    }
    setShowAddForm(true);
  };

  const updateKey = (type: 'ocr' | 'llm', index: number, field: keyof KeyConfig, value: any) => {
    if (type === 'ocr') {
      const updated = [...ocrKeys];
      updated[index] = { ...updated[index], [field]: value };
      setOcrKeys(updated);
      const keyErrors = validateKeyConfig(updated[index], index, type);
      setErrors(prev => [
        ...prev.filter(e => !e.field.startsWith(`${type}-${index}`)),
        ...keyErrors
      ]);
    } else {
      const updated = [...llmKeys];
      updated[index] = { ...updated[index], [field]: value };
      setLlmKeys(updated);
      const keyErrors = validateKeyConfig(updated[index], index, type);
      setErrors(prev => [
        ...prev.filter(e => !e.field.startsWith(`${type}-${index}`)),
        ...keyErrors
      ]);
    }
  };

  const removeKey = (type: 'ocr' | 'llm', index: number) => {
    const otherType = type === 'ocr' ? 'llm' : 'ocr';
    const otherKeys = type === 'ocr' ? llmKeys : ocrKeys;

    if (type === 'ocr') {
      const updated = ocrKeys.filter((_, i) => i !== index);
      setOcrKeys(updated);
      const newOcrErrors = updated.flatMap((key, i) => validateKeyConfig(key, i, type));
      const otherErrors = errors.filter(e => e.field.startsWith(otherType));
      setErrors([...newOcrErrors, ...otherErrors]);
      if (updated.length === 0) setShowAddForm(false);
    } else {
      const updated = llmKeys.filter((_, i) => i !== index);
      setLlmKeys(updated);
      const newLlmErrors = updated.flatMap((key, i) => validateKeyConfig(key, i, type));
      const otherErrors = errors.filter(e => e.field.startsWith(otherType));
      setErrors([...newLlmErrors, ...otherErrors]);
      if (updated.length === 0) setShowAddForm(false);
    }
  };

  const loadKeysToEdit = (pool: KeyPoolStats | undefined, type: 'ocr' | 'llm') => {
    if (pool?.keys) {
      const keys = pool.keys.map((k: KeyStatsDisplay) => ({
        api_key: '',
        api_base: k.api_base,
        model_name: k.model_name,
        max_concurrent: k.max_concurrent,
        rpm_limit: k.rpm_limit,
        tpm_limit: k.tpm_limit,
        enabled: k.is_healthy
      }));
      if (type === 'ocr') {
        setOcrKeys(keys);
      } else {
        setLlmKeys(keys);
      }
    }
    setErrors([]);
  };

  const getError = (field: string): string | undefined => {
    return errors.find(e => e.field === field)?.message;
  };

  if (!isOpen) return null;

  const renderTab = (tab: TabType, label: string, icon: React.ReactNode) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
        activeTab === tab
          ? 'bg-indigo-600 text-white shadow-lg'
          : 'text-slate-500 hover:bg-slate-100'
      }`}
    >
      {icon}
      {label}
    </button>
  );

  const renderKeyCard = (key: KeyConfig | KeyStatsDisplay, index: number, type: 'ocr' | 'llm') => {
    const apiKeyError = getError(`${type}-${index}-api_key`);
    const apiBaseError = getError(`${type}-${index}-api_base`);
    const modelError = getError(`${type}-${index}-model_name`);
    const isStats = 'is_healthy' in key && key.is_healthy !== undefined;

    return (
      <div key={index} className={`bg-white border rounded-xl p-4 space-y-3 ${apiKeyError || apiBaseError || modelError ? 'border-red-300' : 'border-slate-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isStats ? (
              key.is_healthy ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500" />
              )
            ) : (
              <Plus className="w-4 h-4 text-slate-400" />
            )}
            <span className="text-xs font-mono text-slate-600">
              {'api_key' in key && key.api_key ? `${key.api_key.slice(0, 8)}...${key.api_key.slice(-4)}` : 'not set'}
            </span>
          </div>
          {showAddForm && (
            <button
              onClick={() => removeKey(type, index)}
              className="p-1 hover:bg-red-50 rounded text-red-400 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>

        {showAddForm && 'api_key' in key ? (
          <>
            <div>
              <input
                type="password"
                placeholder="API Key *"
                value={key.api_key || ''}
                onChange={(e) => updateKey(type, index, 'api_key', e.target.value)}
                className={`w-full bg-slate-50 border rounded-lg px-3 py-2 text-xs outline-none transition-all ${
                  apiKeyError ? 'border-red-400 focus:ring-2 focus:ring-red-50' : 'border-slate-200 focus:ring-2 focus:ring-indigo-50 focus:border-indigo-400'
                }`}
              />
              {apiKeyError && <p className="text-[10px] text-red-500 mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{apiKeyError}</p>}
            </div>

            <div>
              <input
                type="text"
                placeholder="API Base URL *"
                value={key.api_base || ''}
                onChange={(e) => updateKey(type, index, 'api_base', e.target.value)}
                className={`w-full bg-slate-50 border rounded-lg px-3 py-2 text-xs outline-none transition-all ${
                  apiBaseError ? 'border-red-400 focus:ring-2 focus:ring-red-50' : 'border-slate-200 focus:ring-2 focus:ring-indigo-50 focus:border-indigo-400'
                }`}
              />
              {apiBaseError && <p className="text-[10px] text-red-500 mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{apiBaseError}</p>}
            </div>

            <div>
              <input
                type="text"
                placeholder="Model Name *"
                value={key.model_name || ''}
                onChange={(e) => updateKey(type, index, 'model_name', e.target.value)}
                className={`w-full bg-slate-50 border rounded-lg px-3 py-2 text-xs outline-none transition-all ${
                  modelError ? 'border-red-400 focus:ring-2 focus:ring-red-50' : 'border-slate-200 focus:ring-2 focus:ring-indigo-50 focus:border-indigo-400'
                }`}
              />
              {modelError && <p className="text-[10px] text-red-500 mt-1 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{modelError}</p>}
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <input
                  type="number"
                  placeholder="Concurrent"
                  min="1"
                  value={key.max_concurrent || 5}
                  onChange={(e) => updateKey(type, index, 'max_concurrent', parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-50 focus:border-indigo-400 outline-none"
                />
              </div>
              <div>
                <input
                  type="number"
                  placeholder="RPM"
                  min="1"
                  value={key.rpm_limit || 60}
                  onChange={(e) => updateKey(type, index, 'rpm_limit', parseInt(e.target.value) || 60)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-50 focus:border-indigo-400 outline-none"
                />
              </div>
              <div>
                <input
                  type="number"
                  placeholder="TPM"
                  min="1"
                  value={key.tpm_limit || 100000}
                  onChange={(e) => updateKey(type, index, 'tpm_limit', parseInt(e.target.value) || 100000)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-50 focus:border-indigo-400 outline-none"
                />
              </div>
            </div>
          </>
        ) : (
          <div className="grid grid-cols-4 gap-2 text-xs text-slate-500">
            <div className="bg-slate-50 rounded-lg px-3 py-2 text-center">
              <div className="font-bold text-slate-700">{'active_requests' in key ? `${key.active_requests}/${key.max_concurrent}` : '-'}</div>
              <div className="text-[10px] text-slate-400">Concurrent</div>
            </div>
            <div className="bg-slate-50 rounded-lg px-3 py-2 text-center">
              <div className="font-bold text-slate-700">{'rpm_used' in key ? `${key.rpm_used}/${key.rpm_limit}` : '-'}</div>
              <div className="text-[10px] text-slate-400">RPM</div>
            </div>
            <div className="bg-slate-50 rounded-lg px-3 py-2 text-center">
              <div className="font-bold text-slate-700">{'tpm_used' in key ? `${((key.tpm_used || 0) / 1000).toFixed(0)}K` : '-'}</div>
              <div className="text-[10px] text-slate-400">TPM Used</div>
            </div>
            <div className="bg-slate-50 rounded-lg px-3 py-2 text-center">
              <div className="font-bold text-slate-700">{'consecutive_errors' in key ? key.consecutive_errors : '-'}</div>
              <div className="text-[10px] text-slate-400">Errors</div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderKeyPool = (pool: KeyPoolStats | undefined, type: 'ocr' | 'llm', title: string, icon: React.ReactNode) => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h4 className="text-sm font-bold text-slate-700">{title}</h4>
          {pool?.enabled && (
            <span className="px-2 py-0.5 bg-green-100 text-green-700 text-[10px] font-bold rounded-full">
              Active
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              if (type === 'ocr') {
                loadKeysToEdit(multiKeyStats?.ocr, 'ocr');
              } else {
                loadKeysToEdit(multiKeyStats?.llm, 'llm');
              }
              setShowAddForm(true);
            }}
            className="flex items-center gap-1 px-3 py-1.5 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 transition-all"
          >
            <Plus className="w-3 h-3" />
            Add Key
          </button>
          <button
            onClick={loadMultiKeyStats}
            className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-slate-600 transition-all"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {pool?.keys && pool.keys.length > 0 && !showAddForm ? (
        <div className="space-y-2">
          {pool.keys.map((key: KeyStatsDisplay, index: number) => renderKeyCard(key, index, type))}
        </div>
      ) : (
        <div className="space-y-2">
          {(type === 'ocr' ? ocrKeys : llmKeys).map((key, index) => renderKeyCard(key, index, type))}
          {!showAddForm && (type === 'ocr' ? ocrKeys : llmKeys).length === 0 && (
            <div className="bg-slate-50 border border-dashed border-slate-300 rounded-xl p-8 text-center">
              <p className="text-xs text-slate-400">No keys configured</p>
              <button
                onClick={() => addKey(type)}
                className="mt-2 text-xs text-indigo-600 font-bold hover:underline"
              >
                Add your first key
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );

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
          className="relative w-full max-w-3xl bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-200"
        >
          <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-600 rounded-xl">
                <Settings className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Settings</h2>
                <p className="text-xs text-slate-400">Configure AI engines and API keys</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-full text-slate-400 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="px-8 py-4 border-b border-slate-100 flex gap-2">
            {renderTab('basic', 'Basic', <Database className="w-3 h-3" />)}
            {renderTab('ocr-keys', 'OCR Keys', <Cpu className="w-3 h-3" />)}
            {renderTab('llm-keys', 'LLM Keys', <Cpu className="w-3 h-3" />)}
          </div>

          <div className="p-8 max-h-[60vh] overflow-y-auto custom-scrollbar">
            {activeTab === 'basic' && (
              <section className="space-y-6">
                <div className="space-y-4">
                  <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Active Workspace</label>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-xs font-mono text-slate-600 truncate shadow-sm">
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
                  <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest">API Base URL</label>
                  <input
                    type="text"
                    defaultValue={config?.API_BASE}
                    onBlur={(e) => onSaveConfig('API_BASE', e.target.value)}
                    placeholder="https://api.siliconflow.cn/v1"
                    className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-xs focus:ring-4 focus:ring-indigo-50 focus:border-indigo-400 outline-none transition-all shadow-sm"
                  />
                </div>
              </section>
            )}

            {activeTab === 'ocr-keys' && (
              <section className="space-y-6">
                {errors.find(e => e.field === 'general') && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-600 text-xs">
                    <AlertCircle className="w-4 h-4" />
                    {errors.find(e => e.field === 'general')?.message}
                  </div>
                )}
                {renderKeyPool(multiKeyStats?.ocr, 'ocr', 'OCR API Keys (SiliconFlow)',
                  <Cpu className="w-4 h-4 text-indigo-600" />
                )}
              </section>
            )}

            {activeTab === 'llm-keys' && (
              <section className="space-y-6">
                {errors.find(e => e.field === 'general') && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-600 text-xs">
                    <AlertCircle className="w-4 h-4" />
                    {errors.find(e => e.field === 'general')?.message}
                  </div>
                )}
                {renderKeyPool(multiKeyStats?.llm, 'llm', 'LLM API Keys (General)',
                  <Cpu className="w-4 h-4 text-purple-600" />
                )}
              </section>
            )}
          </div>

          <div className="px-8 py-6 bg-slate-50 border-t border-slate-100 flex justify-between">
            <div className="flex items-center gap-4 text-xs text-slate-400">
              {config?.OCR_MULTI_KEY && (
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-green-500" /> OCR Multi-Key
                </span>
              )}
              {config?.LLM_MULTI_KEY && (
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-green-500" /> LLM Multi-Key
                </span>
              )}
            </div>
            <div className="flex gap-3">
              {showAddForm && (
                <button
                  onClick={() => {
                    setShowAddForm(false);
                    setErrors([]);
                  }}
                  className="flex items-center gap-2 px-6 py-3 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-100 transition-all"
                >
                  Cancel
                </button>
              )}
              {showAddForm && (
                <button
                  onClick={() => handleSaveKeys(activeTab === 'ocr-keys' ? 'ocr' : 'llm')}
                  disabled={isSaving}
                  className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 shadow-lg shadow-indigo-100 transition-all disabled:opacity-50"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Keys
                </button>
              )}
              {!showAddForm && (
                <button
                  onClick={onClose}
                  className="flex items-center gap-2 px-8 py-3 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 shadow-lg shadow-indigo-100 transition-all active:scale-95"
                >
                  Done
                </button>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
