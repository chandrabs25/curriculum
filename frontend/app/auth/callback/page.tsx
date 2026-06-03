"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createCurriculumPlan, fetchMyProfile } from "../../services/api";
import { completeOAuthCallback } from "../../services/auth";
import type { CurriculumQueryPayload } from "../../types/curriculum";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState("Completing sign in...");
  const [errorTitle, setErrorTitle] = useState("Sign in failed");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function finishAuth() {
      try {
        const session = await completeOAuthCallback(window.location.href);
        if (!session) {
          throw new Error("No Supabase session was found after sign in.");
        }
        setMessage("Syncing your profile...");
        await fetchMyProfile();

        const pendingQuery = sessionStorage.getItem("curriculum-pending-plan-query");
        if (pendingQuery) {
          setMessage("Creating your curriculum plan...");
          const query = JSON.parse(pendingQuery) as CurriculumQueryPayload;
          let plan;
          try {
            plan = await createCurriculumPlan(query);
          } catch (err: unknown) {
            setErrorTitle("Plan generation failed");
            throw err;
          }
          sessionStorage.removeItem("curriculum-pending-plan-query");
          localStorage.setItem("curriculum-current-plan-id", plan.curriculum_plan_id);
          router.replace(`/plan/${encodeURIComponent(plan.curriculum_plan_id)}`);
          return;
        }

        const returnTo = sessionStorage.getItem("curriculum-auth-return-to") || "/";
        sessionStorage.removeItem("curriculum-auth-return-to");
        router.replace(returnTo);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to complete sign in.");
      }
    }

    void finishAuth();
  }, [router]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white px-6 text-zinc-900">
        <main className="w-full max-w-sm rounded-xl border border-zinc-300 bg-white p-8 text-center">
          <h1 className="text-lg font-medium text-red-600">{errorTitle}</h1>
          <p className="mt-3 text-sm text-zinc-500">{error}</p>
          <Link
            href={errorTitle === "Plan generation failed" ? "/onboard/preview" : "/login"}
            className="mt-6 inline-flex rounded-full bg-zinc-900 px-5 py-2.5 text-xs font-semibold text-white"
          >
            {errorTitle === "Plan generation failed" ? "Retry Plan" : "Try Again"}
          </Link>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-6 text-zinc-900">
      <main className="text-center">
        <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent" />
        <p className="mt-4 text-xs text-zinc-500">{message}</p>
      </main>
    </div>
  );
}
