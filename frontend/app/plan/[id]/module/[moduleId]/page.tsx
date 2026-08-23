"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { RetryPanel } from "../../../../components/RetryPanel";
import { fetchCurriculumProgress } from "../../../../services/api";
import { moduleHref } from "../../../../services/curriculum-session";
import { useModuleWorkspace } from "../../../../hooks/useModuleWorkspace";

export default function ModuleReadingPage() {
  const params = useParams();
  const rawId = params.id as string;
  const id = decodeURIComponent(rawId);
  const rawModuleId = params.moduleId as string;
  const moduleId = decodeURIComponent(rawModuleId);

  const [completedCount, setCompletedCount] = useState(0);
  const workspace = useModuleWorkspace({
    planId: id,
    moduleId,
    returnTo: moduleHref(id, moduleId),
    mode: "fetch-or-design",
    fallbackError: "Failed to load module details from API backend.",
  });
  const { plan, moduleData, loading, retrying, error, retry } = workspace;

  useEffect(() => {
    if (!plan || !moduleData) return;
    fetchCurriculumProgress(plan.curriculum_plan_id)
      .then((progress) => setCompletedCount(progress.completed_count))
      .catch(() => setCompletedCount(0));
  }, [moduleData, plan]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="text-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent mx-auto"></div>
          <p className="mt-4 text-xs text-zinc-400 font-light">Loading module content...</p>
        </div>
      </div>
    );
  }

  if (error && !moduleData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white px-4">
        <div className="max-w-md w-full text-center bg-white p-8 rounded-xl border border-zinc-300">
          <RetryPanel
            title="Module Load Failed"
            message={error}
            onRetry={() => void retry()}
            retryLabel="Retry Module"
            isRetrying={retrying}
            fallbackHref={`/plan/${encodeURIComponent(id)}`}
            fallbackLabel="Back to Plan"
          />
        </div>
      </div>
    );
  }

  if (!moduleData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white px-4">
        <div className="max-w-md w-full">
          <RetryPanel
            title="Module Unavailable"
            message="The module content was not loaded."
            onRetry={() => void retry()}
            retryLabel="Retry Module"
            isRetrying={retrying}
            fallbackHref={`/plan/${encodeURIComponent(id)}`}
            fallbackLabel="Back to Plan"
          />
        </div>
      </div>
    );
  }

  // Find previous and next modules for navigation
  const sortedModules = plan ? [...plan.modules].sort((a, b) => a.position - b.position) : [];
  const currentIndex = sortedModules.findIndex((m) => m.module_id === moduleId);
  
  const prevModule = currentIndex > 0 ? sortedModules[currentIndex - 1] : null;
  const nextModule = currentIndex < sortedModules.length - 1 ? sortedModules[currentIndex + 1] : null;

  const progressPercent = sortedModules.length > 0 
    ? Math.round((completedCount / sortedModules.length) * 100) 
    : 0;
  const checkpointCount = moduleData.checkpoint_mcqs?.length || 0;

  return (
    <div className="bg-white text-zinc-900 font-sans min-h-screen flex flex-col selection:bg-zinc-100 selection:text-zinc-950">
      {/* Navigation Header */}
      <header className="w-full max-w-4xl mx-auto px-6 h-14 flex items-center justify-between border-b border-zinc-300">
        <div className="flex items-center gap-3">
          <Link href={`/plan/${encodeURIComponent(id)}`} className="text-zinc-500 hover:text-zinc-900 transition-colors text-sm font-medium">
            &larr; Plan
          </Link>
          <span className="text-zinc-200">|</span>
          <span className="text-sm font-semibold tracking-tight text-zinc-900 truncate max-w-[200px] md:max-w-md">
            {moduleData.title}
          </span>
        </div>
        <span className="text-xs text-zinc-500 font-light hidden sm:inline">
          {checkpointCount > 0 ? `${checkpointCount} quiz questions` : "Reading Lesson"}
        </span>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto px-6 py-10 custom-scrollbar">
        <div className="max-w-3xl mx-auto flex flex-col gap-10 pb-20">
          
          {/* Breadcrumbs & Progress Indicator */}
          <nav className="flex items-center gap-2 text-xs font-light text-zinc-400">
            <span className="font-normal text-zinc-500">{plan?.onboarding.topic}</span>
            <span>&middot;</span>
            <span className="font-normal text-zinc-800">{moduleData.title}</span>
            
            <div className="ml-auto flex items-center gap-3 shrink-0">
              <span className="font-medium text-zinc-700">{progressPercent}% Complete</span>
              <div className="w-20 h-1 bg-zinc-50 border border-zinc-300 rounded-full overflow-hidden">
                <div
                  className="h-full bg-zinc-900 rounded-full transition-all duration-1000"
                  style={{ width: `${progressPercent}%` }}
                ></div>
              </div>
            </div>
          </nav>

          {/* Module Title Header */}
          <section className="flex flex-col gap-4 border-b border-zinc-300 pb-8">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              Module {currentIndex + 1}
            </span>
            <h1 className="text-3xl font-light tracking-tight text-zinc-950 leading-tight">
              {moduleData.title}
            </h1>
            <p className="text-sm text-zinc-700 leading-relaxed font-light mt-1">
              {moduleData.module_goal}
            </p>
            {moduleData.larger_goal_alignment && (
              <div className="mt-4 p-4 border border-zinc-300 bg-zinc-50 rounded-xl">
                <p className="text-[9px] text-zinc-400 uppercase font-medium tracking-wider mb-1">
                  Goal Alignment
                </p>
                <p className="text-xs text-zinc-650 leading-normal font-light italic">
                  &ldquo;{moduleData.larger_goal_alignment}&rdquo;
                </p>
              </div>
            )}
          </section>

          {/* Navigation Controls (Previous/Next) */}
          <section className="grid grid-cols-2 gap-4 border-b border-zinc-300 pb-8">
            {prevModule ? (
              <Link
                href={moduleHref(id, prevModule.module_id)}
                className="flex flex-col items-start gap-1 p-3 border border-zinc-300 rounded-xl hover:border-zinc-950 transition-colors text-left"
              >
                <span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">&larr; Previous</span>
                <span className="text-xs font-normal text-zinc-900 truncate max-w-full">{prevModule.title}</span>
              </Link>
            ) : (
              <Link
                href={`/plan/${encodeURIComponent(id)}`}
                className="flex flex-col items-start gap-1 p-3 border border-zinc-300 rounded-xl hover:border-zinc-950 transition-colors text-left"
              >
                <span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">&larr; Previous</span>
                <span className="text-xs font-normal text-zinc-900">Timeline Dashboard</span>
              </Link>
            )}

            {nextModule ? (
              <Link
                href={moduleHref(id, nextModule.module_id)}
                className="flex flex-col items-end gap-1 p-3 border border-zinc-300 rounded-xl hover:border-zinc-950 transition-colors text-right"
              >
                <span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">Next &rarr;</span>
                <span className="text-xs font-normal text-zinc-900 truncate max-w-full">{nextModule.title}</span>
              </Link>
            ) : (
              <Link
                href={`/plan/${encodeURIComponent(id)}`}
                className="flex flex-col items-end gap-1 p-3 border border-zinc-300 rounded-xl hover:border-zinc-950 transition-colors text-right"
              >
                <span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-400">Next &rarr;</span>
                <span className="text-xs font-normal text-zinc-900">Curriculum Dashboard</span>
              </Link>
            )}
          </section>

          {/* Lesson Content Sections */}
          <section className="flex flex-col gap-10">
            {moduleData.lesson_sections?.map((section, idx) => (
              <article key={idx} className="flex flex-col gap-4">
                <h2 className="text-xl font-normal text-zinc-950">
                  {section.heading}
                </h2>
                <div className="text-sm text-zinc-705 leading-relaxed font-light whitespace-pre-line space-y-4">
                  {section.body}
                </div>
              </article>
            ))}
          </section>

          {/* Guided Activity Section */}
          {moduleData.guided_activity && (
            <section className="p-5 border-l-2 border-zinc-900 bg-zinc-50 rounded-r-xl flex flex-col gap-3">
              <div className="flex items-center gap-1.5 text-zinc-950">
                <span className="material-symbols-outlined text-sm">explore</span>
                <h3 className="text-xs font-semibold uppercase tracking-wider m-0">
                  Guided Activity
                </h3>
              </div>
              <div className="text-xs text-zinc-650 leading-relaxed whitespace-pre-line font-light">
                {moduleData.guided_activity}
              </div>
            </section>
          )}

          {/* Common Misconceptions Section */}
          {moduleData.common_misconceptions && moduleData.common_misconceptions.length > 0 && (
            <section className="p-5 border border-red-200 bg-red-50 rounded-xl flex flex-col gap-3">
              <div className="flex items-center gap-1.5 text-red-700">
                <span className="material-symbols-outlined text-sm">warning</span>
                <h3 className="text-xs font-semibold uppercase tracking-wider m-0">
                  Common Misconceptions
                </h3>
              </div>
              <ul className="list-disc list-inside flex flex-col gap-1.5 text-xs text-red-800 leading-normal font-light">
                {moduleData.common_misconceptions.map((misconception: string, mIdx: number) => (
                  <li key={mIdx}>{misconception}</li>
                ))}
              </ul>
            </section>
          )}

          {/* Checkpoint Quiz Section */}
          {checkpointCount > 0 && (
            <section className="border-t border-zinc-200 pt-10 text-center flex flex-col items-center gap-4">
              <p className="text-[10px] font-semibold text-zinc-450 uppercase tracking-wider">
                Check your understanding of this module
              </p>
              <Link
                href={`${moduleHref(id, moduleId)}/checkpoint`}
                className="inline-flex items-center justify-center gap-1.5 rounded-full bg-zinc-900 px-6 py-3 text-xs font-medium text-white transition-colors hover:bg-zinc-800"
              >
                <span className="material-symbols-outlined text-sm">quiz</span>
                <span>Checkpoint Quiz</span>
              </Link>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
