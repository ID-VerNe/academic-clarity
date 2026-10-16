import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { ChatMessage } from '../types';
import { toast } from '../components/ui/Toast';
import { usePersistentState } from './usePersistentState';

/** 会话历史上限（持久化时截断，仅影响写入不影响内存态） */
export const MAX_CHAT_HISTORY = 60;

const NO_QUOTES_HINT =
  '引用模式下没有找到可引用段落。\n\n可以：\n1. 到「文献库 → 知识库检索」先摄入本文档；\n2. 或关闭引用模式，改为按全文提问。';
const EMPTY_REPLY_HINT = 'AI 没有返回内容。请稍后重试；若持续失败，请检查设置中的模型配置。';
const CONNECT_FAIL_HINT =
  '连接失败：无法连接后端服务。\n\n请确认应用已完全启动；问题已放回输入框，恢复后可再次回车重试。';
const DEFAULT_ANALYSIS_QUESTION = '请概括这篇论文的研究问题、方法、主要结论与局限性。';

/**
 * Reader 会话编排：会话状态 + 引用模式发送（知识库检索 → 仅本文档逐字引文喂 LLM）+ 错误回退。
 * 会话按文档持久化（UX-19 / FE-17）：key `ac:chat:{docId}`、JSON 数组、写前 slice(-MAX_CHAT_HISTORY)。
 */
export const useReaderChat = (docId: number) => {
  const [chatHistory, setChatHistory] = usePersistentState<ChatMessage[]>(`ac:chat:${docId}`, [], {
    beforeWrite: (value) => value.slice(-MAX_CHAT_HISTORY),
  });
  const [chatQuery, setChatQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  // Phase 2：引用模式（知识库逐字引文 → LLM，全文不外溢）
  const [citeMode, setCiteMode] = useState(false);
  const [focusSignal, setFocusSignal] = useState(0);

  // 切换文档时清空输入草稿（历史由 usePersistentState 按 key 重读）
  useEffect(() => {
    setChatQuery('');
  }, [docId]);

  const sendMessage = useCallback(async () => {
    const userMsg = chatQuery.trim();
    if (!userMsg) return;

    setChatQuery('');
    setChatHistory((prev) => [...prev, { role: 'user', content: userMsg }]);
    setIsTyping(true);

    try {
      let data;
      if (citeMode) {
        // 引用模式：先跨库检索，只把本文档的逐字引文喂给 LLM
        // （limit 20 再按 doc_id 过滤；无命中不调 LLM，避免幻觉引文）
        const search = await api.searchKnowledge(userMsg, 20);
        const quotes = ((search.results || []) as any[])
          .filter((r) => r.doc_id === docId)
          .map((r) => r.quote);
        if (quotes.length === 0) {
          setChatHistory((prev) => [...prev, { role: 'ai', content: NO_QUOTES_HINT }]);
          return;
        }
        data = await api.chat(docId, userMsg, quotes);
      } else {
        data = await api.chat(docId, userMsg);
      }
      if (data?.response) {
        setChatHistory((prev) => [...prev, { role: 'ai', content: data.response }]);
      } else {
        setChatHistory((prev) => [...prev, { role: 'ai', content: EMPTY_REPLY_HINT }]);
        setChatQuery(userMsg);
      }
    } catch (e) {
      console.error('Chat failed:', e);
      // UX-18：连接失败给出可操作指引，并把问题放回输入框便于重试
      setChatHistory((prev) => [...prev, { role: 'ai', content: CONNECT_FAIL_HINT }]);
      setChatQuery(userMsg);
    } finally {
      setIsTyping(false);
    }
  }, [chatQuery, citeMode, docId, setChatHistory]);

  const clearHistory = useCallback(() => {
    setChatHistory([]);
    toast.success('对话已清空');
  }, [setChatHistory]);

  /** 划词引用：以引用块前缀插入提问框（不覆盖已输入内容） */
  const insertQuote = useCallback((text: string) => {
    const quoted = text
      .split('\n')
      .map((line) => `> ${line}`)
      .join('\n');
    setChatQuery((prev) => (prev.trim() ? `${quoted}\n\n${prev}` : `${quoted}\n\n`));
  }, []);

  /** AI 分析（UX-04）：输入框为空时预填默认问题，聚焦由 focusChat 负责 */
  const prefillDefaultQuestion = useCallback(() => {
    setChatQuery((prev) => (prev.trim() ? prev : DEFAULT_ANALYSIS_QUESTION));
  }, []);

  /** 递增聚焦信号：ChatSidebar 切到「对话」页并聚焦输入框 */
  const focusChat = useCallback(() => setFocusSignal((n) => n + 1), []);

  return {
    chatHistory,
    chatQuery,
    setChatQuery,
    isTyping,
    citeMode,
    setCiteMode,
    focusSignal,
    sendMessage,
    clearHistory,
    insertQuote,
    prefillDefaultQuestion,
    focusChat,
  };
};
