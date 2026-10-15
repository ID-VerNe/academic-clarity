import React, { useState } from 'react';
import { api } from '../api/client';
import { toast } from '../components/ui/Toast';
import { Document } from '../types';
import { FetchData } from './useBackendHealth';

interface UseDocumentActionsOptions {
  /** 标记后端不可达（统一失败处理用） */
  markUnhealthy: () => void;
  /** 数据重取（成功后刷新列表） */
  fetchData: FetchData;
  setDocs: React.Dispatch<React.SetStateAction<Document[]>>;
}

/**
 * 文档动作：导入 / 删除（含确认目标状态）/ 重新处理 / 保存配置。
 * 所有 catch 走统一 markUnhealthy 帮助函数（日志 + 标记断连 + toast），
 * 消除重构前的 catch 三连重复。
 */
export function useDocumentActions({ markUnhealthy, fetchData, setDocs }: UseDocumentActionsOptions) {
  const [isUploading, setIsUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  /** 统一的「后端不可达」失败处理 */
  const handleBackendFailure = (label: string, message: string, e: unknown) => {
    console.error(`${label}:`, e);
    markUnhealthy();
    toast.error(message);
  };

  const handleUpload = async (file: File) => {
    if (isUploading) return;
    setIsUploading(true);
    try {
      const res = await api.uploadDocument(file);
      if (res?.success) {
        toast.success(`已导入「${file.name}」，正在后台处理`);
        await fetchData({ silent: true });
      } else {
        toast.error(`导入失败：${res?.detail || '服务器未接受该文件'}`);
      }
    } catch (e) {
      handleBackendFailure('Upload failed', '导入失败：无法连接后端服务，请稍后重试。', e);
    } finally {
      setIsUploading(false);
    }
  };

  /** 删除：先弹应用内确认框（UX-15），确认后执行并给出反馈 */
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setIsDeleting(true);
    try {
      const res = await api.deleteDocument(target.id);
      if (res?.success) {
        setDocs((prev) => prev.filter((d) => d.id !== target.id));
        toast.success(`已删除「${target.title || target.filename}」`);
        setDeleteTarget(null);
      } else {
        toast.error('删除失败：该文档可能已被移除，请刷新后重试。');
      }
    } catch (e) {
      handleBackendFailure('Delete failed', '删除失败：无法连接后端服务。', e);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReprocess = async (id: number) => {
    try {
      await api.reprocessDocument(id);
      toast.success('已重新加入处理队列');
      await fetchData({ silent: true });
    } catch (e) {
      handleBackendFailure('Reprocess failed', '重新处理失败：无法连接后端服务。', e);
    }
  };

  const saveConfig = async (key: string, value: string): Promise<boolean> => {
    try {
      await api.setConfig(key, value);
      await fetchData({ silent: true });
      toast.success('配置已保存');
      return true;
    } catch (e) {
      handleBackendFailure('Save config failed', '保存失败：无法连接后端服务。', e);
      return false;
    }
  };

  return {
    isUploading,
    deleteTarget,
    setDeleteTarget,
    isDeleting,
    handleUpload,
    confirmDelete,
    handleReprocess,
    saveConfig,
  };
}
