import React from 'react';
import { Loader2 } from 'lucide-react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger';

const VARIANT_STYLE: Record<ButtonVariant, string> = {
  primary: 'bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed',
  secondary: 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-60 disabled:cursor-not-allowed',
  danger: 'bg-rose-50 border border-rose-100 text-rose-600 hover:bg-rose-100 disabled:opacity-60 disabled:cursor-not-allowed',
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** 加载中：自动替换为 spinner 并禁用点击（防重复提交） */
  loading?: boolean;
  /** 非加载态显示的图标（加载态自动换成 spinner） */
  icon?: React.ReactNode;
}

/**
 * 统一按钮：消除各处的「Loader2 ↔ 业务图标」条件渲染样板。
 * className / aria-* / title / children / disabled 等原生属性全部透传。
 */
export const Button = ({
  variant = 'primary',
  loading = false,
  icon,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) => (
  <button
    type={type}
    disabled={disabled || loading}
    className={`inline-flex items-center gap-2 text-sm font-semibold rounded-xl transition-colors ${VARIANT_STYLE[variant]} ${className}`}
    {...rest}
  >
    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : icon}
    {children}
  </button>
);
