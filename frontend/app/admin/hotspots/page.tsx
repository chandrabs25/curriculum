"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { fetchAdminHotspots } from "../../services/admin-api";
import type { HotspotRow, PaginatedHotspots } from "../../types/admin";

const STATUS_TABS = ["", "candidate", "active", "rejected", "resolved", "superseded"];
const STATUS_LABELS: Record<string, string> = {
  "": "All",
  candidate: "Candidate",
  active: "Active",
  rejected: "Rejected",
  resolved: "Resolved",
  superseded: "Superseded",
};
const STATUS_DOT: Record<string, string> = {
  candidate: "bg-amber-400",
  active: "bg-emerald-500",
  rejected: "bg-red-400",
  resolved: "bg-blue-400",
  superseded: "bg-zinc-400",
};

export default function AdminHotspotsPage() {
  const [data, setData] = useState<PaginatedHotspots | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const limit = 20;

  const load = useCallback(() => {
    setError("");
    fetchAdminHotspots({
      status: statusFilter || undefined,
      limit,
      offset: page * limit,
    })
      .then(setData)
      .catch((err) => setError(err.message || "Failed to load hotspots"));
  }, [statusFilter, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-hanken text-xl font-extrabold text-primary">
          Misunderstanding Hotspots
        </h1>
        <p className="mt-0.5 text-sm text-on-surface-variant">
          Review and manage detected misconception hotspots
        </p>
      </div>

      {/* Status filter tabs */}
      <div className="flex flex-wrap items-center gap-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setStatusFilter(tab);
              setPage(0);
            }}
            className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition-colors ${
              statusFilter === tab
                ? "bg-secondary-container text-on-secondary-container"
                : "text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            {tab && <span className={`inline-block h-1.5 w-1.5 rounded-full ${STATUS_DOT[tab] || "bg-zinc-400"}`} />}
            {STATUS_LABELS[tab]}
            {data && tab === statusFilter && (
              <span className="ml-1 text-[10px] opacity-70">({data.total})</span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-xl border border-error/20 bg-error-container px-4 py-3 text-sm text-on-error-container">
          {error}
        </div>
      )}

      {/* Hotspot list */}
      <div className="space-y-3">
        {!data
          ? [...Array(3)].map((_, i) => (
              <div key={i} className="h-24 rounded-2xl bg-surface-container-high loading-pulse" />
            ))
          : data.hotspots.length === 0
            ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <span className="material-symbols-outlined text-4xl text-on-surface-variant/40">
                  check_circle
                </span>
                <p className="text-sm text-on-surface-variant">
                  No hotspots found{statusFilter ? ` with status "${statusFilter}"` : ""}.
                </p>
              </div>
            )
            : data.hotspots.map((hotspot) => (
              <HotspotCard key={hotspot.hotspot_id} hotspot={hotspot} />
            ))}
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

function HotspotCard({ hotspot }: { hotspot: HotspotRow }) {
  const ratePct = Math.round(hotspot.misconception_rate * 100);
  const rateColor =
    ratePct >= 60 ? "text-red-600" : ratePct >= 40 ? "text-amber-600" : "text-on-surface";

  return (
    <Link
      href={`/admin/hotspots/${encodeURIComponent(hotspot.hotspot_id)}`}
      className="group block rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 transition-all hover:border-secondary/40 hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${STATUS_DOT[hotspot.status] || "bg-zinc-400"}`}
            />
            <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
              {hotspot.status}
            </span>
          </div>
          <h3 className="mt-1.5 truncate text-sm font-semibold text-on-surface group-hover:text-secondary">
            {hotspot.misconception_tag.replace(/_/g, " ")}
          </h3>
          <p className="mt-1 text-xs text-on-surface-variant">
            <span className="font-medium">Section:</span> {hotspot.section_id} ·{" "}
            <span className="font-medium">Concept:</span> {hotspot.concept_id}
          </p>
          {hotspot.diagnostic_summary && (
            <p className="mt-2 line-clamp-2 text-xs text-on-surface-variant/80">
              {hotspot.diagnostic_summary}
            </p>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1 text-right">
          <span className={`font-hanken text-xl font-extrabold ${rateColor}`}>{ratePct}%</span>
          <span className="text-[10px] text-on-surface-variant">misconception rate</span>
          <div className="mt-1 flex items-center gap-3 text-[10px] text-on-surface-variant">
            <span>{hotspot.attempt_count} attempts</span>
            <span>{hotspot.unique_learner_count} learners</span>
          </div>
        </div>
      </div>
    </Link>
  );
}
