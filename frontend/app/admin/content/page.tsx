"use client";

import { useState, useEffect } from "react";
import {
  fetchAdminContentStats,
  fetchAdminCheckpointAnalytics,
} from "../../services/admin-api";
import type { ContentStats, CheckpointAnalytics } from "../../types/admin";

function StatCard({
  icon,
  label,
  value,
}: {
  icon: string;
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex items-start gap-4 rounded-2xl border border-outline-variant bg-surface-container-lowest p-5">
      <span className="material-symbols-outlined mt-0.5 text-2xl text-secondary">{icon}</span>
      <div>
        <p className="font-hanken text-2xl font-extrabold text-on-surface">{value}</p>
        <p className="mt-0.5 text-xs font-semibold text-on-surface-variant">{label}</p>
      </div>
    </div>
  );
}

function ScoreBar({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? Math.round((score / max) * 100) : 0;
  const color =
    score >= 0.7 ? "bg-emerald-500" : score >= 0.4 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-surface-container-high">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-[10px] font-bold text-on-surface-variant">
        {Math.round(score * 100)}%
      </span>
    </div>
  );
}

export default function AdminContentPage() {
  const [content, setContent] = useState<ContentStats | null>(null);
  const [analytics, setAnalytics] = useState<CheckpointAnalytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([fetchAdminContentStats(), fetchAdminCheckpointAnalytics()])
      .then(([c, a]) => {
        setContent(c);
        setAnalytics(a);
      })
      .catch((err) => setError(err.message || "Failed to load data"));
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <span className="material-symbols-outlined text-4xl text-error">error</span>
        <p className="text-sm text-error">{error}</p>
      </div>
    );
  }

  const loading = !content || !analytics;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-hanken text-xl font-extrabold text-primary">
          Content &amp; Analytics
        </h1>
        <p className="mt-0.5 text-sm text-on-surface-variant">
          Embedding coverage and checkpoint performance
        </p>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-2xl bg-surface-container-high loading-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon="library_books"
              label="Total Sections"
              value={content.total_sections}
            />
            <StatCard
              icon="menu_book"
              label="Chapters"
              value={content.total_chapters}
            />
            <StatCard
              icon="quiz"
              label="Total Attempts"
              value={analytics.total_attempts}
            />
            <StatCard
              icon="trending_up"
              label="Pass Rate"
              value={`${Math.round(analytics.pass_rate * 100)}%`}
            />
          </div>

          {/* Embedding coverage by subject/grade */}
          <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
            <h2 className="font-hanken text-base font-bold text-on-surface">
              Embedding Coverage by Subject &amp; Grade
            </h2>
            {content.by_subject_grade.length === 0 ? (
              <p className="mt-3 text-sm text-on-surface-variant">No embeddings found.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-outline-variant text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                      <th className="px-4 py-2">Subject</th>
                      <th className="px-4 py-2 text-right">Grade</th>
                      <th className="px-4 py-2 text-right">Sections</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant">
                    {content.by_subject_grade.map((row, i) => (
                      <tr key={i} className="hover:bg-surface-container-low">
                        <td className="px-4 py-2 capitalize text-on-surface">{row.subject}</td>
                        <td className="px-4 py-2 text-right text-on-surface">
                          {row.grade || "—"}
                        </td>
                        <td className="px-4 py-2 text-right font-hanken font-bold text-on-surface">
                          {row.section_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Checkpoint analytics */}
          <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
            <h2 className="font-hanken text-base font-bold text-on-surface">
              Checkpoint Performance by Module
            </h2>
            <p className="mt-1 text-xs text-on-surface-variant">
              Sorted by average score (lowest first)
            </p>
            {analytics.by_module.length === 0 ? (
              <p className="mt-3 text-sm text-on-surface-variant">No checkpoint data yet.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {analytics.by_module.map((mod) => (
                  <div key={mod.module_id} className="rounded-xl border border-outline-variant p-4">
                    <div className="flex items-center justify-between gap-4">
                      <p className="min-w-0 truncate text-xs font-semibold text-on-surface">
                        {mod.module_id.replace(/^module:/, "").slice(0, 24)}
                      </p>
                      <span className="shrink-0 text-xs text-on-surface-variant">
                        {mod.attempt_count} attempt{mod.attempt_count !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <div className="mt-2">
                      <ScoreBar score={mod.avg_score} max={1} />
                    </div>
                    <div className="mt-1 flex gap-4 text-[10px] text-on-surface-variant">
                      <span>Avg: {Math.round(mod.avg_score * 100)}%</span>
                      <span>Min: {Math.round(mod.min_score * 100)}%</span>
                      <span>Max: {Math.round(mod.max_score * 100)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Daily trends */}
          {analytics.daily.length > 0 && (
            <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
              <h2 className="font-hanken text-base font-bold text-on-surface">
                Daily Checkpoint Activity
              </h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-outline-variant text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                      <th className="px-4 py-2">Date</th>
                      <th className="px-4 py-2 text-right">Attempts</th>
                      <th className="px-4 py-2 text-right">Avg Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant">
                    {analytics.daily.map((row) => (
                      <tr key={row.day} className="hover:bg-surface-container-low">
                        <td className="px-4 py-2 text-on-surface">{row.day}</td>
                        <td className="px-4 py-2 text-right font-hanken font-bold text-on-surface">
                          {row.attempts}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                              row.avg_score >= 0.7
                                ? "bg-emerald-100 text-emerald-700"
                                : row.avg_score >= 0.4
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-red-100 text-red-700"
                            }`}
                          >
                            {Math.round(row.avg_score * 100)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
