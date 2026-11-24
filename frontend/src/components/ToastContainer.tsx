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
    <div
      aria-live="assertive"
      className="fixed inset-x-3 bottom-3 z-50 flex flex-col gap-3 sm:inset-x-auto sm:bottom-5 sm:end-5 sm:w-full sm:max-w-sm"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`flex items-start justify-between gap-3 border-2 border-black p-3.5 font-mono text-xs shadow-brutal ${
            toast.variant === "error" ? "bg-brutal-pink text-black" : "bg-brutal-lime text-black"
          }`}
        >
          <div className="min-w-0 flex-1 space-y-1">
            <p className="break-words font-black uppercase leading-snug">{toast.title}</p>
            {toast.hint && (
              <p className="break-words text-[11px] font-medium leading-relaxed">{toast.hint}</p>
            )}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss notification"
            className="shrink-0 border-2 border-black bg-white px-2 py-0.5 font-black text-black shadow-brutal-sm hover:bg-black hover:text-white"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
