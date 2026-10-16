import { useMemo, useState } from 'react';
import { Document } from '../types';
import { safeParseJson } from '../utils/json';
import { BasicInsight, SortKey } from '../components/dashboard/constants';

/**
 * 文献库筛选与排序：
 * - 检索词（searchQuery）与 Header 共享，由上层传入；
 * - 期刊 / 年份 / 排序为本地状态；
 * - 返回过滤后的文档列表、派生筛选项与重置动作。
 */
export const useLibraryFilter = (
  docs: Document[],
  searchQuery: string,
  onSearchChange: (value: string) => void
) => {
  const [selectedJournal, setSelectedJournal] = useState<string>('all');
  const [selectedYear, setSelectedYear] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortKey>('added_desc');

  // Intelligence Parsing & Filtering（检索覆盖标题 / 作者 / 期刊 / 洞察字段）
  const filteredDocs = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase();
    const matched = docs.filter((doc) => {
      const insight = safeParseJson<BasicInsight>(doc.basic_insight_json) || {};
      const matchesSearch =
        !needle ||
        [
          doc.title,
          doc.filename,
          doc.authors,
          insight.journal_or_conference,
          insight.date,
          JSON.stringify(insight),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(needle);
      const matchesJournal = selectedJournal === 'all' || insight.journal_or_conference === selectedJournal;
      const matchesYear = selectedYear === 'all' || (insight.date && insight.date.toString().includes(selectedYear));

      return matchesSearch && matchesJournal && matchesYear;
    });

    const sorted = [...matched];
    sorted.sort((a, b) => {
      const ia = safeParseJson<BasicInsight>(a.basic_insight_json) || {};
      const ib = safeParseJson<BasicInsight>(b.basic_insight_json) || {};
      switch (sortBy) {
        case 'added_asc':
          return String(a.added_at || '').localeCompare(String(b.added_at || ''));
        case 'title_asc':
          return (a.title || a.filename).localeCompare(b.title || b.filename, 'zh-CN');
        case 'year_desc': {
          const ya = parseInt(String(ia.date || '').match(/\d{4}/)?.[0] || '0', 10);
          const yb = parseInt(String(ib.date || '').match(/\d{4}/)?.[0] || '0', 10);
          return yb - ya;
        }
        case 'added_desc':
        default:
          return String(b.added_at || '').localeCompare(String(a.added_at || ''));
      }
    });
    return sorted;
  }, [docs, searchQuery, selectedJournal, selectedYear, sortBy]);

  // Derived Filter Options
  const filterOptions = useMemo(() => {
    const journals = new Set<string>();
    const years = new Set<string>();

    docs.forEach((doc) => {
      const insight = safeParseJson<BasicInsight>(doc.basic_insight_json);
      if (!insight) return;
      if (insight.journal_or_conference) journals.add(insight.journal_or_conference);
      if (insight.date) {
        const yearMatch = insight.date.toString().match(/\d{4}/);
        if (yearMatch) years.add(yearMatch[0]);
      }
    });

    return {
      journals: Array.from(journals).sort(),
      years: Array.from(years).sort((a, b) => b.localeCompare(a)),
    };
  }, [docs]);

  const hasActiveFilters = selectedJournal !== 'all' || selectedYear !== 'all' || !!searchQuery.trim();

  const resetFilters = () => {
    setSelectedJournal('all');
    setSelectedYear('all');
    onSearchChange('');
  };

  return {
    filteredDocs,
    filterOptions,
    hasActiveFilters,
    resetFilters,
    selectedJournal,
    setSelectedJournal,
    selectedYear,
    setSelectedYear,
    sortBy,
    setSortBy,
  };
};
