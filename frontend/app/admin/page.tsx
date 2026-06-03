"use client";

import { useState, useEffect } from "react";
import { fetchAdminDashboard } from "../services/admin-api";
import type { AdminDashboard } from "../types/admin";

function StatCard({
  icon,
  label,
  value,
  accent,
}: {
  icon: string;
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="flex items-start gap-4 rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 transition-shadow hover:shadow-sm">
      <span
        className={`material-symbols-outlined mt-0.5 text-2xl ${accent || "text-secondary"}`}
      >
        {icon}
      </span>
      <div>
        <p className="font-hanken text-2xl font-extrabold text-on-surface">{value}</p>
        <p className="mt-0.5 text-xs font-semibold text-on-surface-variant">{label}</p>
      </div>
    </div>
  );
}

function HotspotStatusRow({
  status,
  count,
  color,
}: {
  status: string;
  count: number;
  color: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2">
        <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
        <span className="text-sm capitalize text-on-surface">{status}</span>
      </div>
      <span className="font-hanken text-sm font-bold text-on-surface">{count}</span>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  candidate: "bg-amber-400",
  active: "bg-emerald-500",
  rejected: "bg-red-400",
  resolved: "bg-blue-400",
  superseded: "bg-zinc-400",
};

export default function AdminDashboardPage() {
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAdminDashboard()
      .then(setData)
      .catch((err) => setError(err.message || "Failed to load dashboard"));
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <span className="material-symbols-outlined text-4xl text-error">error</span>
        <p className="text-sm text-error">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 rounded-lg bg-surface-container-high loading-pulse" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-24 rounded-2xl bg-surface-container-high loading-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  const hotspotEntries = Object.entries(data.hotspots_by_status);
  const totalHotspots = hotspotEntries.reduce((acc, [, v]) => acc + v, 0);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-hanken text-xl font-extrabold text-primary">Dashboard</h1>
        <p className="mt-1 text-sm text-on-surface-variant">
          System overview and key metrics
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon="group" label="Total Learners" value={data.learner_count} />
        <StatCard icon="auto_stories" label="Curriculum Plans" value={data.plan_count} />
        <StatCard
          icon="quiz"
          label="Checkpoint Attempts"
          value={data.checkpoint_attempt_count}
        />
        <StatCard
          icon="database"
          label="Section Embeddings"
          value={data.embedding_count}
        />
      </div>

      {/* Hotspot breakdown */}
      <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-hanken text-base font-bold text-on-surface">
              Misunderstanding Hotspots
            </h2>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              Breakdown by review status
            </p>
          </div>
          <span className="font-hanken text-2xl font-extrabold text-on-surface">
            {totalHotspots}
          </span>
        </div>
        <div className="mt-4 divide-y divide-outline-variant">
          {hotspotEntries.length === 0 ? (
            <p className="py-4 text-center text-sm text-on-surface-variant">
              No hotspots detected yet
            </p>
          ) : (
            hotspotEntries.map(([status, count]) => (
              <HotspotStatusRow
                key={status}
                status={status}
                count={count}
                color={STATUS_COLORS[status] || "bg-zinc-400"}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
