import React, { useEffect, useState } from 'react';
import { X, Settings, Database, Save, Loader2, Layers } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { AppConfig } from '../types';
import { ConfirmDialog } from './ui/ConfirmDialog';
import { DimensionManager } from './settings/DimensionManager';
import { BasicSettingsTab } from './settings/BasicSettingsTab';
import { useSettingsDraft } from './settings/useSettingsDraft';
import { useModalFocusTrap } from '../hooks/useModalFocusTrap';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig | null;
  /** 返回 true 表示保存成功（调用方负责 toast 反馈） */
  onSaveConfig: (key: string, value: string) => Promise<boolean>;
  onSelectWorkspace: () => void;
}

type TabType = 'basic' | 'dimensions';

/**
 * 设置弹窗（外壳）：
 * - 多 Key 轮询已由本地代理承担，应用内只保留单 Key 配置（不再提供 Key 池编辑）
 * - 显式保存 + 保存反馈 + 空值保护（UX-29）
 * - ESC 关闭、焦点圈定、未保存提醒（UX-31）
 * 草稿编排见 settings/useSettingsDraft，字段行见 settings/SettingsField。
 */
export const SettingsModal = ({
  isOpen,
  onClose,
  config,
  onSaveConfig,
  onSelectWorkspace,
}: SettingsModalProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('basic');
  const [confirmClose, setConfirmClose] = useState(false);

  const {
    draft,
    errors,
    dirtyKeys,
    hasUnsaved,
    savingField,
    clearTarget,
    isDirty,
    setField,
    handleSave,
    requestClear,
    cancelClear,
    confirmClear,
  } = useSettingsDraft({ isOpen, config, onSaveConfig });

  // 打开时回到「基础配置」tab
  useEffect(() => {
    if (!isOpen || !config) return;
    setActiveTab('basic');
  }, [isOpen, config]);

  const requestClose = () => {
    if (hasUnsaved) setConfirmClose(true);
    else onClose();
  };

  // ESC 关闭 + 焦点圈定 + 关闭后归还焦点
  const dialogRef = useModalFocusTrap({ active: isOpen, onEscape: requestClose });

  if (!isOpen) return null;

  const renderTab = (tab: TabType, label: string, icon: React.ReactNode) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
        activeTab === tab ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:bg-slate-100'
      }`}
    >
      {icon}
      {label}
    </button>
  );

  return (
    <>
      <AnimatePresence>
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={requestClose}
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
          />

          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label="设置"
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
                  <h2 className="text-xl font-bold text-slate-900">设置</h2>
                  <p className="text-xs text-slate-400">配置 OCR 引擎与提取维度</p>
                </div>
              </div>
              <button
                onClick={requestClose}
                aria-label="关闭设置"
                className="p-2 hover:bg-slate-200 rounded-full text-slate-400 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-8 py-4 border-b border-slate-100 flex gap-2">
              {renderTab('basic', '基础配置', <Database className="w-3 h-3" />)}
              {renderTab('dimensions', '提取维度', <Layers className="w-3 h-3" />)}
            </div>

            <div className="p-8 max-h-[60vh] overflow-y-auto custom-scrollbar">
              {activeTab === 'basic' && (
                <BasicSettingsTab
                  config={config}
                  draft={draft}
                  errors={errors}
                  savingField={savingField}
                  isDirty={isDirty}
                  setField={setField}
                  requestClear={requestClear}
                  onSelectWorkspace={onSelectWorkspace}
                />
              )}

              {activeTab === 'dimensions' && <DimensionManager />}
            </div>

            <div className="px-8 py-6 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-4">
              <p className="text-xs text-slate-500">
                {hasUnsaved ? `有 ${dirtyKeys.length} 项未保存的修改` : '所有修改已保存'}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={requestClose}
                  className="px-6 py-3 text-slate-600 text-xs font-bold rounded-xl hover:bg-slate-100 transition-all"
                >
                  {hasUnsaved ? '放弃修改' : '关闭'}
                </button>
                <button
                  onClick={async () => {
                    if (await handleSave()) onClose();
                  }}
                  disabled={!hasUnsaved || !!savingField}
                  className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white text-xs font-bold rounded-xl hover:bg-indigo-700 shadow-lg shadow-indigo-100 transition-all disabled:opacity-40 disabled:shadow-none"
                >
                  {savingField ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {savingField ? '保存中…' : '保存'}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      </AnimatePresence>

      <ConfirmDialog
        open={confirmClose}
        danger
        title="放弃未保存的修改？"
        message="关闭后本次修改将丢失。"
        confirmText="放弃修改"
        cancelText="继续编辑"
        onConfirm={() => {
          setConfirmClose(false);
          onClose();
        }}
        onCancel={() => setConfirmClose(false)}
      />

      <ConfirmDialog
        open={!!clearTarget}
        danger
        busy={!!savingField}
        title={`清空「${clearTarget?.label ?? ''}」？`}
        message="清空后该配置将变为空值，相关功能可能不可用。"
        confirmText="清空"
        cancelText="取消"
        onConfirm={confirmClear}
        onCancel={cancelClear}
      />
    </>
  );
};
