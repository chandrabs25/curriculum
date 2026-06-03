"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { checkAdminAccess } from "../services/admin-api";
import { getCurrentUser, signOut } from "../services/auth";

const NAV_ITEMS = [
  { href: "/admin", label: "Dashboard", icon: "dashboard" },
  { href: "/admin/learners", label: "Learners", icon: "group" },
  { href: "/admin/hotspots", label: "Hotspots", icon: "warning" },
  { href: "/admin/content", label: "Content", icon: "library_books" },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [status, setStatus] = useState<"loading" | "allowed" | "denied">("loading");

  useEffect(() => {
    getCurrentUser()
      .then((user) => {
        if (!user) {
          setStatus("denied");
          return;
        }
        return checkAdminAccess();
      })
      .then((isAdmin) => {
        setStatus(isAdmin ? "allowed" : "denied");
      })
      .catch(() => setStatus("denied"));
  }, []);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <div className="flex flex-col items-center gap-3">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant loading-pulse">
            admin_panel_settings
          </span>
          <p className="text-sm text-on-surface-variant">Verifying access…</p>
        </div>
      </div>
    );
  }

  if (status === "denied") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="material-symbols-outlined text-5xl text-error">lock</span>
          <h1 className="font-hanken text-xl font-bold text-on-surface">
            Access Denied
          </h1>
          <p className="max-w-xs text-sm text-on-surface-variant">
            You don&rsquo;t have admin privileges. Contact the system administrator.
          </p>
          <Link
            href="/"
            className="mt-2 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-on-primary transition-colors hover:bg-primary/90"
          >
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  function isActive(href: string) {
    if (href === "/admin") return pathname === "/admin";
    return pathname.startsWith(href);
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-outline-variant bg-surface px-4 md:px-10">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 transition-opacity hover:opacity-80">
              <span className="material-symbols-outlined text-xl text-secondary">arrow_back</span>
            </Link>
            <span className="font-hanken text-lg font-extrabold text-primary">
              Admin
            </span>
          </div>

          {/* Navigation tabs */}
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-colors ${
                  isActive(item.href)
                    ? "bg-secondary-container text-on-secondary-container"
                    : "text-on-surface-variant hover:bg-surface-container-high"
                }`}
              >
                <span className="material-symbols-outlined text-base">{item.icon}</span>
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            ))}
          </nav>

          <button
            type="button"
            onClick={() => void signOut().then(() => (window.location.href = "/"))}
            className="text-xs font-semibold text-on-surface-variant transition-colors hover:text-error"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 md:px-10">
        {children}
      </main>
    </div>
  );
}
