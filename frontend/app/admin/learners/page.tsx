"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { fetchAdminLearners } from "../../services/admin-api";
import type { AdminLearnerRow, PaginatedLearners } from "../../types/admin";

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function AdminLearnersPage() {
  const [data, setData] = useState<PaginatedLearners | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const limit = 20;

  const load = useCallback(() => {
    setError("");
    fetchAdminLearners({ limit, offset: page * limit, search })
      .then(setData)
      .catch((err) => setError(err.message || "Failed to load learners"));
  }, [page, search]);

  useEffect(() => {
    load();
  }, [load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(0);
    load();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-hanken text-xl font-extrabold text-primary">Learners</h1>
          <p className="mt-0.5 text-sm text-on-surface-variant">
            {data ? `${data.total} registered learner${data.total !== 1 ? "s" : ""}` : "Loading…"}
          </p>
        </div>
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-full border border-outline-variant bg-surface-container-lowest px-3 py-1.5">
            <span className="material-symbols-outlined text-base text-on-surface-variant">search</span>
            <input
              type="text"
              placeholder="Search by name or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 bg-transparent text-xs text-on-surface outline-none placeholder:text-on-surface-variant/50"
            />
          </div>
        </form>
      </div>

      {error && (
        <div className="rounded-xl border border-error/20 bg-error-container px-4 py-3 text-sm text-on-error-container">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-2xl border border-outline-variant bg-surface-container-lowest">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-outline-variant text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              <th className="px-5 py-3">Learner</th>
              <th className="px-5 py-3">Provider</th>
              <th className="px-5 py-3 text-right">Plans</th>
              <th className="px-5 py-3 text-right">Attempts</th>
              <th className="px-5 py-3 text-right">Last Seen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {!data
              ? [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    <td colSpan={5} className="px-5 py-4">
                      <div className="h-4 w-full rounded bg-surface-container-high loading-pulse" />
                    </td>
                  </tr>
                ))
              : data.learners.length === 0
                ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-on-surface-variant">
                      No learners found.
                    </td>
                  </tr>
                )
                : data.learners.map((learner) => (
                  <LearnerRow key={learner.user_id} learner={learner} />
                ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.total > limit && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-1 rounded-full px-4 py-2 text-xs font-semibold text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-base">chevron_left</span>
            Previous
          </button>
          <span className="text-xs text-on-surface-variant">
            Page {page + 1} of {Math.ceil(data.total / limit)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={(page + 1) * limit >= data.total}
            className="flex items-center gap-1 rounded-full px-4 py-2 text-xs font-semibold text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:opacity-40"
          >
            Next
            <span className="material-symbols-outlined text-base">chevron_right</span>
          </button>
        </div>
      )}
    </div>
  );
}

function LearnerRow({ learner }: { learner: AdminLearnerRow }) {
  return (
    <tr className="group transition-colors hover:bg-surface-container-low">
      <td className="px-5 py-3">
        <Link
          href={`/admin/learners/${encodeURIComponent(learner.user_id)}`}
          className="flex items-center gap-3"
        >
          {learner.avatar_url ? (
            <img
              src={learner.avatar_url}
              alt=""
              className="h-8 w-8 rounded-full object-cover"
            />
          ) : (
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-container-high text-xs font-bold text-on-surface-variant">
              {(learner.display_name || learner.email || "?")[0]?.toUpperCase()}
            </span>
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-on-surface group-hover:text-secondary">
              {learner.display_name || "Unnamed"}
            </p>
            <p className="truncate text-xs text-on-surface-variant">
              {learner.email || learner.user_id.slice(0, 12) + "…"}
            </p>
          </div>
        </Link>
      </td>
      <td className="px-5 py-3">
        <span className="rounded-full bg-surface-container-high px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
          {learner.provider}
        </span>
      </td>
      <td className="px-5 py-3 text-right font-hanken font-bold text-on-surface">
        {learner.plan_count}
      </td>
      <td className="px-5 py-3 text-right font-hanken font-bold text-on-surface">
        {learner.attempt_count}
      </td>
      <td className="px-5 py-3 text-right text-xs text-on-surface-variant">
        {timeAgo(learner.last_seen_at)}
      </td>
    </tr>
  );
}
