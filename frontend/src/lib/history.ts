import type { Platform } from "./api";

export interface HistoryItem {
  id: string;
  url: string;
  platform: Platform;
  title: string;
  thumbnailUrl: string | null;
  filename: string | null;
  filesizeBytes: number | null;
  createdAt: number;
}

const STORAGE_KEY = "fastdl_history_v1";
const MAX_ITEMS = 25;

export function loadHistory(): HistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function addHistoryItem(item: HistoryItem): HistoryItem[] {
  if (typeof window === "undefined") return [];
  const current = loadHistory().filter((x) => x.id !== item.id);
  const next = [item, ...current].slice(0, MAX_ITEMS);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Ignore storage quota errors
  }
  return next;
}

export function clearHistory(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore
  }
}
