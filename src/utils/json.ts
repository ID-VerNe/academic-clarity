/**
 * 容错 JSON 解析：坏数据返回 null，绝不抛异常。
 * 全项目统一使用此函数处理 LLM 返回 / DB 中的 JSON 字符串。
 */
export const safeParseJson = <T = unknown>(raw?: string | null): T | null => {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
};
