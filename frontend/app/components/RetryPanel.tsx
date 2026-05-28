"use client";

import Link from "next/link";

type RetryPanelProps = {
  title: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  isRetrying?: boolean;
  fallbackHref?: string;
  fallbackLabel?: string;
  compact?: boolean;
};

export function RetryPanel({
  title,
  message,
  onRetry,
  retryLabel = "Retry",
  isRetrying = false,
  fallbackHref,
  fallbackLabel = "Go Back",
  compact = false,
}: RetryPanelProps) {
  return (
    <div
      className={`rounded-2xl border border-error/20 bg-error-container/15 text-center shadow-sm ${
        compact ? "p-5" : "p-8"
      }`}
    >
      <span className="material-symbols-outlined text-4xl text-error">error</span>
      <h2 className="mt-3 font-hanken text-2xl font-bold text-error">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-on-surface-variant">{message}</p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="rounded-xl bg-primary px-6 py-3 font-hanken text-sm font-bold text-on-primary shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRetrying ? "Retrying..." : retryLabel}
          </button>
        )}
        {fallbackHref && (
          <Link
            href={fallbackHref}
            className="rounded-xl border border-outline-variant bg-white px-6 py-3 font-hanken text-sm font-bold text-on-surface-variant hover:bg-surface-container-low"
          >
            {fallbackLabel}
          </Link>
        )}
      </div>
    </div>
  );
}
