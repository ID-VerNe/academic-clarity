import React from 'react';
import { Copy, Quote } from 'lucide-react';
import { SelectionMenuState } from '../../hooks/useSelectionMenu';

interface SelectionToolbarProps {
  menu: SelectionMenuState;
  onCopy: () => void;
  onQuote: () => void;
}

/** 划词工具条：复制 / 引用到提问（定位与关闭由 useSelectionMenu 负责） */
export const SelectionToolbar = ({ menu, onCopy, onQuote }: SelectionToolbarProps) => {
  return (
    <div
      data-selection-menu
      style={{ left: menu.x, top: menu.y }}
      className="fixed -translate-x-1/2 -translate-y-[calc(100%+8px)] z-[130] flex items-center gap-1 bg-slate-900 text-white rounded-xl shadow-xl px-1.5 py-1.5 select-none"
    >
      <button
        onClick={onCopy}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold hover:bg-white/10 transition-colors"
      >
        <Copy className="w-3.5 h-3.5" />
        复制
      </button>
      <div className="w-px h-4 bg-white/20" />
      <button
        onClick={onQuote}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold hover:bg-white/10 transition-colors"
      >
        <Quote className="w-3.5 h-3.5" />
        引用到提问
      </button>
    </div>
  );
};
