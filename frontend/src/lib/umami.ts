declare global {
  interface Window {
    umami?: {
      track: (eventName: string, data?: Record<string, string | number | boolean>) => void;
    };
  }
}

export function trackUmamiEvent(
  eventName: string,
  data?: Record<string, string | number | boolean>
): void {
  if (typeof window === "undefined") return;
  try {
    window.umami?.track(eventName, data);
  } catch {
    // Analytics must never interrupt user actions
  }
}
