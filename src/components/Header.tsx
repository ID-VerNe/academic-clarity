import React from 'react';
import { 
  School, 
  FolderOpen, 
  Search, 
  Bell, 
  Settings 
} from 'lucide-react';

interface HeaderProps {
  workspacePath: string;
  setView: (view: 'dashboard' | 'reader') => void;
  onOpenSettings: () => void;
}

export const Header = ({ workspacePath, setView, onOpenSettings }: HeaderProps) => (
  <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 sticky top-0 z-50 shadow-sm">
    <div className="flex items-center gap-8">
      <div 
        className="flex items-center gap-2 text-indigo-600 cursor-pointer"
        onClick={() => setView('dashboard')}
      >
        <School className="w-8 h-8" />
        <h1 className="font-bold text-xl tracking-tight text-slate-900">Academic Clarity</h1>
      </div>
      
      <div className="h-6 w-px bg-slate-200" />
      
      <div className="flex items-center gap-2 text-xs font-medium text-slate-400 max-w-md truncate">
        <FolderOpen className="w-3 h-3 shrink-0" />
        <span className="truncate">{workspacePath || 'Loading workspace...'}</span>
      </div>
    </div>

    <div className="flex items-center gap-3">
      <div className="relative w-64 mr-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
        <input 
          className="w-full h-9 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500/20 text-sm outline-none transition-all" 
          placeholder="Search library..." 
          type="text"
        />
      </div>
      <button className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-600">
        <Bell className="w-5 h-5" />
      </button>
      <button 
        onClick={onOpenSettings}
        aria-label="Open Settings"
        className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-600"
      >
        <Settings className="w-5 h-5" />
      </button>
      <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold text-xs">
        AC
      </div>
    </div>
  </header>
);
