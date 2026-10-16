import React from 'react';
import { ArrowUpDown, Building2, Calendar, Filter, Search, X } from 'lucide-react';
import { useLibraryFilter } from '../../hooks/useLibraryFilter';
import { SORT_OPTIONS, SortKey } from './constants';

interface FilterBarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  /** useLibraryFilter 的返回值（期刊 / 年份 / 排序状态与派生筛选项） */
  filter: ReturnType<typeof useLibraryFilter>;
}

/** Intelligence Filter Bar（仅论文库模式）：搜索 / 期刊 / 年份 / 排序 */
export const FilterBar = ({ searchQuery, onSearchChange, filter }: FilterBarProps) => (
  <div className="bg-white border border-slate-200 rounded-3xl p-3 shadow-sm flex flex-wrap items-center gap-4">
    <div className="flex-1 min-w-[260px] relative group">
      <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
      <input
        type="text"
        placeholder="搜索标题、作者、期刊或洞察字段…"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        aria-label="搜索文献"
        className="w-full pl-11 pr-10 py-2.5 bg-slate-50 border-none rounded-2xl text-sm focus:ring-2 focus:ring-indigo-100 transition-all outline-none"
      />
      {searchQuery && (
        <button
          onClick={() => onSearchChange('')}
          aria-label="清空搜索"
          className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>

    <div className="flex items-center gap-3">
      <div className="relative">
        <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
        <select
          value={filter.selectedJournal}
          onChange={(e) => filter.setSelectedJournal(e.target.value)}
          aria-label="按期刊筛选"
          className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-xs font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
        >
          <option value="all">全部期刊</option>
          {filter.filterOptions.journals.map((j) => (
            <option key={j} value={j}>
              {j}
            </option>
          ))}
        </select>
      </div>

      <div className="relative">
        <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
        <select
          value={filter.selectedYear}
          onChange={(e) => filter.setSelectedYear(e.target.value)}
          aria-label="按年份筛选"
          className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-xs font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
        >
          <option value="all">全部年份</option>
          {filter.filterOptions.years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      <div className="relative">
        <ArrowUpDown className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
        <select
          value={filter.sortBy}
          onChange={(e) => filter.setSortBy(e.target.value as SortKey)}
          aria-label="排序方式"
          className="pl-9 pr-8 py-2.5 bg-slate-50 border-none rounded-2xl text-xs font-bold text-slate-600 appearance-none focus:ring-2 focus:ring-indigo-100 outline-none cursor-pointer"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {filter.hasActiveFilters && (
        <button
          onClick={filter.resetFilters}
          className="p-2 text-rose-500 hover:bg-rose-50 rounded-xl transition-colors"
          title="清除筛选条件"
          aria-label="清除筛选条件"
        >
          <Filter className="w-4 h-4" />
        </button>
      )}
    </div>
  </div>
);
