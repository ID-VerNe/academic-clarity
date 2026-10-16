import { useState } from 'react';
import { KnowledgeClaim } from '../types';
import { api } from '../api/client';

const SEARCH_ERROR_MESSAGE = '检索失败：无法连接后端服务。请确认应用已启动后重试。';

/**
 * Phase 2：跨库检索 claims（limit 取 20，引用模式同样口径）。
 * 失败时保留 searched 标记并给出可重试的错误态（UX-16：与「无结果」区分）。
 */
export const useClaimsSearch = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<KnowledgeClaim[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.searchKnowledge(query.trim(), 20);
      setResults(data?.results || []);
      setSearched(true);
    } catch (e) {
      console.error('Knowledge search failed', e);
      setResults([]);
      setSearched(true);
      setError(SEARCH_ERROR_MESSAGE);
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setQuery('');
    setResults([]);
    setSearched(false);
    setError(null);
  };

  /** 失败后以当前查询词重试 */
  const retry = () => search();

  return { query, setQuery, results, loading, searched, error, search, clear, retry };
};
