export const truncateForTitle = (s: string | null | undefined, max = 80): string | null => {
  if (!s) return null;
  const t = s.trim();
  if (!t) return null;
  return t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t;
};
