import Link from "next/link";
import type { ReactNode } from "react";

type AppHeaderProps = {
  eyebrow?: string;
  title: string;
  backHref?: string;
  actions?: ReactNode;
  meta?: ReactNode;
};

export function AppHeader({ eyebrow, title, backHref, actions, meta }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-50 flex h-16 w-full items-center justify-between gap-4 border-b border-outline-variant bg-surface px-4 md:px-10">
      <div className="flex min-w-0 items-center gap-3">
        {backHref && (
          <Link
            href={backHref}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container hover:text-secondary"
            aria-label="Go back"
          >
            <span className="material-symbols-outlined text-xl">arrow_back</span>
          </Link>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <p className="truncate text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              {eyebrow}
            </p>
          )}
          <h1 className="truncate font-hanken text-lg font-extrabold text-primary md:text-xl">
            {title}
          </h1>
        </div>
      </div>

      {(meta || actions) && (
        <div className="flex shrink-0 items-center gap-3">
          {meta && (
            <div className="hidden items-center gap-3 text-xs font-semibold text-on-surface-variant sm:flex">
              {meta}
            </div>
          )}
          {actions}
        </div>
      )}
    </header>
  );
}
