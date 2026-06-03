"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchAdminLearnerDetail } from "../../../services/admin-api";
import type { LearnerDetail } from "../../../types/admin";

function formatDate(iso: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 70
      ? "bg-emerald-100 text-emerald-700"
      : pct >= 40
        ? "bg-amber-100 text-amber-700"
        : "bg-red-100 text-red-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${color}`}>
      {pct}%
    </span>
  );
}

export default function LearnerDetailPage() {
  const params = useParams<{ id: string }>();
  const userId = params.id;
  const [data, setData] = useState<LearnerDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!userId) return;
    fetchAdminLearnerDetail(userId)
      .then(setData)
      .catch((err) => setError(err.message || "Failed to load learner"));
  }, [userId]);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <span className="material-symbols-outlined text-4xl text-error">error</span>
        <p className="text-sm text-error">{error}</p>
        <Link href="/admin/learners" className="mt-2 text-xs font-semibold text-secondary hover:underline">
          &larr; Back to learners
        </Link>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-32 rounded bg-surface-container-high loading-pulse" />
        <div className="h-28 rounded-2xl bg-surface-container-high loading-pulse" />
        <div className="h-48 rounded-2xl bg-surface-container-high loading-pulse" />
      </div>
    );
  }

  const { profile, plans, checkpoints } = data;

  return (
    <div className="space-y-8">
      {/* Back link */}
      <Link
        href="/admin/learners"
        className="inline-flex items-center gap-1 text-xs font-semibold text-on-surface-variant transition-colors hover:text-secondary"
      >
        <span className="material-symbols-outlined text-base">arrow_back</span>
        All learners
      </Link>

      {/* Profile card */}
      <div className="flex items-start gap-5 rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
        {profile.avatar_url ? (
          <img
            src={profile.avatar_url}
            alt=""
            className="h-14 w-14 rounded-full object-cover"
          />
        ) : (
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-surface-container-high font-hanken text-xl font-bold text-on-surface-variant">
            {(profile.display_name || profile.email || "?")[0]?.toUpperCase()}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="font-hanken text-xl font-extrabold text-primary">
            {profile.display_name || "Unnamed"}
          </h1>
          <p className="mt-0.5 text-sm text-on-surface-variant">{profile.email || "No email"}</p>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-on-surface-variant">
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">badge</span>
              {profile.provider}
            </span>
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">admin_panel_settings</span>
              {profile.role}
            </span>
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">calendar_today</span>
              Joined {formatDate(profile.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">schedule</span>
              Last seen {formatDate(profile.last_seen_at)}
            </span>
          </div>
        </div>
      </div>

      {/* Plans */}
      <section>
        <h2 className="flex items-center gap-2 font-hanken text-base font-bold text-on-surface">
          <span className="material-symbols-outlined text-lg text-secondary">auto_stories</span>
          Curriculum Plans
          <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-[10px] font-bold text-on-surface-variant">
            {plans.length}
          </span>
        </h2>
        {plans.length === 0 ? (
          <p className="mt-3 text-sm text-on-surface-variant">No plans created yet.</p>
        ) : (
          <div className="mt-3 divide-y divide-outline-variant rounded-2xl border border-outline-variant bg-surface-container-lowest">
            {plans.map((plan) => (
              <div
                key={plan.curriculum_plan_id}
                className="flex items-center justify-between px-5 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-on-surface">
                    {plan.topic || "Untitled"}
                  </p>
                  <p className="mt-0.5 text-xs text-on-surface-variant">
                    {plan.subject || "General"} · {plan.module_count} modules · {formatDate(plan.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Checkpoints */}
      <section>
        <h2 className="flex items-center gap-2 font-hanken text-base font-bold text-on-surface">
          <span className="material-symbols-outlined text-lg text-secondary">quiz</span>
          Checkpoint History
          <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-[10px] font-bold text-on-surface-variant">
            {checkpoints.length}
          </span>
        </h2>
        {checkpoints.length === 0 ? (
          <p className="mt-3 text-sm text-on-surface-variant">No checkpoint attempts yet.</p>
        ) : (
          <div className="mt-3 overflow-x-auto rounded-2xl border border-outline-variant bg-surface-container-lowest">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-outline-variant text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                  <th className="px-5 py-3">Module</th>
                  <th className="px-5 py-3 text-right">Score</th>
                  <th className="px-5 py-3 text-right">Correct</th>
                  <th className="px-5 py-3">Recommendation</th>
                  <th className="px-5 py-3 text-right">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {checkpoints.map((cp) => (
                  <tr key={cp.checkpoint_attempt_id} className="hover:bg-surface-container-low">
                    <td className="px-5 py-3 text-sm text-on-surface">
                      {cp.module_id.replace(/^module:/, "").slice(0, 16)}…
                    </td>
                    <td className="px-5 py-3 text-right">
                      <ScoreBadge score={cp.score} />
                    </td>
                    <td className="px-5 py-3 text-right text-sm text-on-surface">
                      {cp.correct_count}/{cp.total_count}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                          cp.recommendation === "continue"
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {cp.recommendation}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right text-xs text-on-surface-variant">
                      {formatDate(cp.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
