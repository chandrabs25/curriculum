"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { fetchAdminHotspot, updateAdminHotspot } from "../../../services/admin-api";
import type { HotspotRow } from "../../../types/admin";

const STATUS_DOT: Record<string, string> = {
  candidate: "bg-amber-400",
  active: "bg-emerald-500",
  rejected: "bg-red-400",
  resolved: "bg-blue-400",
  superseded: "bg-zinc-400",
};

function InfoRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <span className="text-xs font-semibold text-on-surface-variant">{label}</span>
      <span className="text-right text-sm text-on-surface">{value || "—"}</span>
    </div>
  );
}

export default function HotspotDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const hotspotId = params.id;

  const [hotspot, setHotspot] = useState<HotspotRow | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Form state for review
  const [reviewedGuidance, setReviewedGuidance] = useState("");
  const [activityAdj, setActivityAdj] = useState("");
  const [checkpointFocus, setCheckpointFocus] = useState("");

  useEffect(() => {
    if (!hotspotId) return;
    fetchAdminHotspot(hotspotId)
      .then((data) => {
        setHotspot(data);
        setReviewedGuidance(data.reviewed_guidance || data.proposed_guidance || "");
        setActivityAdj(data.suggested_activity_adjustment || "");
        setCheckpointFocus(data.suggested_checkpoint_focus || "");
      })
      .catch((err) => setError(err.message || "Failed to load hotspot"));
  }, [hotspotId]);

  async function handleStatusUpdate(newStatus: string) {
    if (!hotspotId) return;
    if (newStatus === "active" && !reviewedGuidance.trim()) {
      setError("Reviewed guidance is required to activate a hotspot.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const updated = await updateAdminHotspot(hotspotId, {
        status: newStatus,
        reviewed_guidance: reviewedGuidance.trim(),
        suggested_activity_adjustment: activityAdj.trim() || undefined,
        suggested_checkpoint_focus: checkpointFocus.trim() || undefined,
      });
      setHotspot(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  if (error && !hotspot) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <span className="material-symbols-outlined text-4xl text-error">error</span>
        <p className="text-sm text-error">{error}</p>
        <Link
          href="/admin/hotspots"
          className="mt-2 text-xs font-semibold text-secondary hover:underline"
        >
          &larr; Back to hotspots
        </Link>
      </div>
    );
  }

  if (!hotspot) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-32 rounded bg-surface-container-high loading-pulse" />
        <div className="h-48 rounded-2xl bg-surface-container-high loading-pulse" />
        <div className="h-64 rounded-2xl bg-surface-container-high loading-pulse" />
      </div>
    );
  }

  const ratePct = Math.round(hotspot.misconception_rate * 100);
  const isReviewable = hotspot.status === "candidate";

  return (
    <div className="space-y-8">
      {/* Back */}
      <Link
        href="/admin/hotspots"
        className="inline-flex items-center gap-1 text-xs font-semibold text-on-surface-variant transition-colors hover:text-secondary"
      >
        <span className="material-symbols-outlined text-base">arrow_back</span>
        All hotspots
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${STATUS_DOT[hotspot.status] || "bg-zinc-400"}`} />
            <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              {hotspot.status}
            </span>
          </div>
          <h1 className="mt-2 font-hanken text-xl font-extrabold text-primary">
            {hotspot.misconception_tag.replace(/_/g, " ")}
          </h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Section: {hotspot.section_id} · Concept: {hotspot.concept_id}
          </p>
        </div>
        <div className="flex flex-col items-end gap-0.5 text-right">
          <span className="font-hanken text-3xl font-extrabold text-on-surface">{ratePct}%</span>
          <span className="text-xs text-on-surface-variant">misconception rate</span>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-error/20 bg-error-container px-4 py-3 text-sm text-on-error-container">
          {error}
        </div>
      )}

      {/* Evidence stats */}
      <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
        <h2 className="font-hanken text-base font-bold text-on-surface">Evidence Summary</h2>
        <div className="mt-3 divide-y divide-outline-variant">
          <InfoRow label="Total attempts" value={hotspot.attempt_count} />
          <InfoRow label="Wrong answers" value={hotspot.wrong_count} />
          <InfoRow label="Unique learners" value={hotspot.unique_learner_count} />
          <InfoRow label="Distinct questions" value={hotspot.distinct_question_count} />
          <InfoRow label="Evidence window" value={`${hotspot.evidence_window_start || "?"} → ${hotspot.evidence_window_end || "?"}`} />
          <InfoRow label="Created" value={hotspot.created_at} />
          <InfoRow label="Last updated" value={hotspot.updated_at} />
        </div>
      </div>

      {/* AI-proposed guidance */}
      <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
        <h2 className="flex items-center gap-2 font-hanken text-base font-bold text-on-surface">
          <span className="material-symbols-outlined text-lg text-secondary">auto_awesome</span>
          AI-Proposed Guidance
        </h2>
        <div className="mt-4 space-y-4">
          <GuidanceBlock label="Diagnostic Summary" text={hotspot.diagnostic_summary} />
          <GuidanceBlock label="Proposed Guidance" text={hotspot.proposed_guidance} />
          <GuidanceBlock label="Activity Adjustment" text={hotspot.suggested_activity_adjustment} />
          <GuidanceBlock label="Checkpoint Focus" text={hotspot.suggested_checkpoint_focus} />
        </div>
      </div>

      {/* Review form */}
      {isReviewable && (
        <div className="rounded-2xl border-2 border-secondary/30 bg-surface-container-lowest p-6">
          <h2 className="flex items-center gap-2 font-hanken text-base font-bold text-on-surface">
            <span className="material-symbols-outlined text-lg text-secondary">rate_review</span>
            Review & Decide
          </h2>
          <p className="mt-1 text-xs text-on-surface-variant">
            Edit the guidance if needed, then activate or reject this hotspot.
          </p>

          <div className="mt-5 space-y-4">
            <FieldTextarea
              label="Reviewed Guidance (required to activate)"
              value={reviewedGuidance}
              onChange={setReviewedGuidance}
            />
            <FieldTextarea
              label="Activity Adjustment"
              value={activityAdj}
              onChange={setActivityAdj}
            />
            <FieldTextarea
              label="Checkpoint Focus"
              value={checkpointFocus}
              onChange={setCheckpointFocus}
            />
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={() => handleStatusUpdate("active")}
              disabled={saving}
              className="rounded-full bg-emerald-600 px-5 py-2 text-xs font-bold text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Activate"}
            </button>
            <button
              onClick={() => handleStatusUpdate("rejected")}
              disabled={saving}
              className="rounded-full border border-red-300 px-5 py-2 text-xs font-bold text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </div>
      )}

      {/* Active hotspot: resolve option */}
      {hotspot.status === "active" && (
        <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-6">
          <h2 className="font-hanken text-base font-bold text-on-surface">
            Reviewed Guidance (Active)
          </h2>
          <p className="mt-2 text-sm text-on-surface">{hotspot.reviewed_guidance || "—"}</p>
          <button
            onClick={() => handleStatusUpdate("resolved")}
            disabled={saving}
            className="mt-4 rounded-full border border-blue-300 px-5 py-2 text-xs font-bold text-blue-600 transition-colors hover:bg-blue-50 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Mark as Resolved"}
          </button>
        </div>
      )}
    </div>
  );
}

function GuidanceBlock({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">{label}</p>
      <p className="mt-1 text-sm leading-relaxed text-on-surface">{text || "—"}</p>
    </div>
  );
}

function FieldTextarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-bold text-on-surface-variant">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className="w-full rounded-xl border border-outline-variant bg-surface px-3 py-2 text-sm text-on-surface outline-none transition-colors focus:border-secondary"
      />
    </div>
  );
}
