import React from 'react';

/**
 * IME 安全的 Enter 判断：中文输入法组词回车不应触发提交。
 * 全项目统一使用此函数，禁止手写 e.key === 'Enter' && !e.nativeEvent.isComposing。
 */
export const isImeEnter = (e: React.KeyboardEvent): boolean =>
  e.key === 'Enter' && !e.nativeEvent.isComposing;
