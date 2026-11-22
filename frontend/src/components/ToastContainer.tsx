"use client";

import React from "react";

export interface ToastMessage {
  id: string;
  title: string;
  hint?: string;
  variant: "error" | "info";
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div aria-live="assertive" className="fixed bottom-4 end-4 z-50 flex max-w-sm flex-col gap-3">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`flex items-start justify-between gap-3 border-2 border-black p-3.5 font-mono text-xs shadow-brutal ${
            toast.variant === "error" ? "bg-brutal-pink text-black" : "bg-brutal-lime text-black"
          }`}
        >
          <div className="space-y-1">
            <p className="font-black uppercase">{toast.title}</p>
            {toast.hint && <p className="text-[11px] font-medium">{toast.hint}</p>}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss notification"
            className="border-2 border-black bg-white px-1.5 py-0.5 font-black text-black shadow-brutal-sm hover:bg-black hover:text-white"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
