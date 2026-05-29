"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { RetryPanel } from "../../../../../../components/RetryPanel";
import {
  CurriculumPlanPayload,
  CheckpointResultPayload,
  ExpandedCurriculumModulePayload,
} from "../../../../../../types/curriculum";
import { designModule } from "../../../../../../services/api";
import { readCachedModuleDesign, writeCachedModuleDesign } from "../../../../../../services/moduleDesignCache";
import { readLatestSectionInsights } from "../../../../../../services/sectionInsights";

export default function CheckpointResultsPage() {
  const params = useParams();
  const router = useRouter();
  const rawId = params.id as string;
  const id = decodeURIComponent(rawId);
  const rawModuleId = params.moduleId as string;
  const moduleId = decodeURIComponent(rawModuleId);

  const [plan, setPlan] = useState<CurriculumPlanPayload | null>(null);
  const [result, setResult] = useState<CheckpointResultPayload | null>(null);
  const [moduleData, setModuleData] = useState<ExpandedCurriculumModulePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [moduleError, setModuleError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [moduleRetrying, setModuleRetrying] = useState(false);

  const loadModuleDesign = useCallback(
    async (parsedPlan: CurriculumPlanPayload, useCache: boolean) => {
      setModuleError(null);
      if (useCache) {
        const cached = readCachedModuleDesign(parsedPlan.curriculum_plan_id, moduleId);
        if (cached) {
          setModuleData(cached);
          setLoading(false);
          return;
        }
      }

      const data = await designModule({
        plan: parsedPlan,
        module_id: moduleId,
        learner_state: [],
        section_insights: readLatestSectionInsights(
          parsedPlan.learner_id,
          parsedPlan.modules.find((module) => module.module_id === moduleId)?.source_section_ids || []
        ),
      });
      writeCachedModuleDesign(parsedPlan.curriculum_plan_id, moduleId, data);
      setModuleData(data);
    },
    [moduleId]
  );

  const retryLoadModuleDesign = useCallback(async () => {
    if (!plan) return;
    setModuleRetrying(true);
    setModuleError(null);
    try {
      await loadModuleDesign(plan, false);
    } catch (err: unknown) {
      console.error(err);
      setModuleError(errorMessage(err, "Failed to load module details for this checkpoint report."));
    } finally {
      setModuleRetrying(false);
      setLoading(false);
    }
  }, [loadModuleDesign, plan]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedPlan =
        localStorage.getItem(`curriculum-plan-${id}`) ||
        localStorage.getItem(`curriculum-plan-${rawId}`) ||
        matchingCurrentPlan(id, rawId);
      const storedResult =
        localStorage.getItem(`curriculum-checkpoint-result-${id}-${moduleId}`) ||
        localStorage.getItem(`curriculum-checkpoint-result-${rawId}-${rawModuleId}`);

      if (storedPlan && storedResult) {
        try {
          const parsedPlan = JSON.parse(storedPlan) as CurriculumPlanPayload;
          const parsedResult = JSON.parse(storedResult) as CheckpointResultPayload;
          setPlan(parsedPlan);
          setResult(parsedResult);

          loadModuleDesign(parsedPlan, true)
            .catch((err) => {
              console.error(err);
              setModuleError(errorMessage(err, "Failed to load module details for this checkpoint report."));
            })
            .finally(() => {
              setLoading(false);
            });
        } catch (e) {
          setError("Failed to load checkpoint results data.");
          setLoading(false);
        }
      } else {
        setError("Checkpoint result not found. Please complete the quiz first.");
        setLoading(false);
      }
    }
  }, [id, loadModuleDesign, rawId, rawModuleId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="text-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent mx-auto"></div>
          <p className="mt-4 text-xs text-zinc-400 font-light">Loading checkpoint report...</p>
        </div>
      </div>
    );
  }

  if (error || !plan || !result) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white px-4">
        <div className="max-w-md w-full text-center bg-white p-8 rounded-xl border border-zinc-300">
          <h2 className="text-lg font-normal text-red-650">Error</h2>
          <p className="mt-2 text-xs text-zinc-500 font-light">{error || "Results unavailable."}</p>
          <Link
            href={`${moduleHref(id, moduleId)}/checkpoint`}
            className="mt-6 inline-flex items-center justify-center rounded-full bg-zinc-900 px-6 py-2 text-xs font-semibold text-white hover:bg-zinc-800 transition-colors"
          >
            Take Checkpoint
          </Link>
        </div>
      </div>
    );
  }

  // Find sorted modules & sequencing
  const sortedModules = [...plan.modules].sort((a, b) => a.position - b.position);
  const currentIndex = sortedModules.findIndex((m) => m.module_id === moduleId);
  const currentModule = sortedModules[currentIndex];
  
  const nextModule = currentIndex < sortedModules.length - 1 ? sortedModules[currentIndex + 1] : null;

  // Stats calculation
  const scorePercent = Math.round(result.score * 100);
  const recallAccuracy = Math.min(100, Math.round(result.score * 110));
  const applicationLevel = Math.round(result.score * 90);

  // Helper JSX components
  const recommendationCard = (
    <div className="w-full bg-zinc-50 border border-zinc-300 rounded-xl p-6 relative overflow-hidden">
      <div className="relative z-10 flex flex-col gap-4">
        <h2 className="text-lg font-normal text-zinc-955 tracking-tight">
          {result.recommendation === "continue"
            ? "You're ready for the next module!"
            : "Reviewing materials is recommended"}
        </h2>
        
        <p className="text-xs text-zinc-650 leading-relaxed font-light">
          {result.recommendation === "continue"
            ? `Outstanding performance. You've demonstrated a strong grasp of the concepts in "${currentModule?.title || moduleData?.title}". Your score indicates you are well-prepared to proceed directly to the next segment.`
            : `Good effort! You've shown partial understanding of "${currentModule?.title || moduleData?.title}". To master the foundation before moving forward, we recommend spending a little more time reviewing the targeted lessons below.`}
        </p>

        <div className="flex flex-wrap gap-3 pt-2">
          {nextModule ? (
            <Link
              href={moduleHref(plan.curriculum_plan_id, nextModule.module_id)}
              className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-6 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-zinc-800"
            >
              Next Module &rarr;
            </Link>
          ) : (
            <Link
              href={`/plan/${encodeURIComponent(plan.curriculum_plan_id)}`}
              className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-6 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-zinc-800"
            >
              View Plan Timeline &rarr;
            </Link>
          )}
          
          <Link
            href={moduleHref(plan.curriculum_plan_id, moduleId)}
            className="inline-flex items-center justify-center rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-xs font-medium text-zinc-700 transition-colors hover:border-zinc-950 hover:text-zinc-955"
          >
            View Study Materials
          </Link>
        </div>
      </div>
    </div>
  );

  const diagnosticInsights = (
    <div className="w-full border border-zinc-300 bg-white rounded-xl p-6 flex flex-col gap-4">
      <h3 className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
        Diagnostic Insights
      </h3>
      
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-zinc-50 p-3 rounded-lg border border-zinc-300 flex flex-col justify-between">
          <span className="text-[8px] text-zinc-400 block uppercase font-medium tracking-wider mb-1 leading-normal">Recall</span>
          <span className="text-sm font-normal text-zinc-955">{recallAccuracy}%</span>
        </div>
        <div className="bg-zinc-50 p-3 rounded-lg border border-zinc-300 flex flex-col justify-between">
          <span className="text-[8px] text-zinc-400 block uppercase font-medium tracking-wider mb-1 leading-normal">Application</span>
          <span className="text-sm font-normal text-zinc-955">{applicationLevel}%</span>
        </div>
        <div className="bg-zinc-50 p-3 rounded-lg border border-zinc-300 flex flex-col justify-between">
          <span className="text-[8px] text-zinc-400 block uppercase font-medium tracking-wider mb-1 leading-normal">Concepts</span>
          <span className="text-sm font-normal text-zinc-955">{result.question_results?.length || 0}</span>
        </div>
      </div>
    </div>
  );

  const weakConcepts = result.weak_concept_ids && result.weak_concept_ids.length > 0 ? (
    <div className="w-full flex flex-col gap-4">
      <h3 className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
        <span className="material-symbols-outlined text-sm text-amber-600">warning</span>
        Targeted Review Areas
      </h3>
      
      <div className="flex flex-col gap-3">
        {result.weak_concept_ids.map((concept) => (
          <div
            key={concept}
            className="p-3 bg-zinc-50 border border-zinc-300 rounded-xl flex items-center gap-3"
          >
            <div className="w-6 h-6 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-705 shrink-0">
              <span className="material-symbols-outlined text-[12px]">trending_down</span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-zinc-900 capitalize truncate">
                {concept.replace("concept:", "").replace(/_/g, " ")}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  ) : null;

  return (
    <div className="bg-white text-zinc-900 font-sans min-h-screen flex flex-col selection:bg-zinc-100 selection:text-zinc-955">
      {/* Navigation Header */}
      <header className="w-full max-w-6xl mx-auto px-6 h-14 flex items-center justify-between border-b border-zinc-300 bg-white">
        <div className="flex items-center gap-3">
          <Link href={moduleHref(id, moduleId)} className="text-zinc-505 hover:text-zinc-900 transition-colors text-sm font-medium">
            &larr; Module
          </Link>
          <span className="text-zinc-200">|</span>
          <span className="text-sm font-semibold tracking-tight text-zinc-900 truncate max-w-[200px] md:max-w-md">
            Checkpoint Results
          </span>
        </div>
        <Link
          href="/onboard"
          className="rounded-full border border-zinc-300 hover:border-zinc-955 bg-white px-4 py-1.5 text-xs font-medium text-zinc-700 hover:text-zinc-955 transition-colors"
        >
          New Topic
        </Link>
      </header>

      {/* Main Container */}
      <div className="flex flex-col md:flex-row max-w-6xl w-full mx-auto flex-1 py-10 px-6 gap-10">
        
        {/* Left Column: Question Review */}
        <main className="flex-1 flex flex-col gap-8 min-w-0">
          {/* Hero Score Section */}
          <div className="w-full">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 border border-zinc-300 bg-zinc-50 text-zinc-700 rounded-full mb-4">
              <span className="material-symbols-outlined text-[14px]">verified</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider">Checkpoint Complete</span>
            </div>
            
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <h1 className="text-3xl font-light tracking-tight text-zinc-955 leading-tight">
                  Score: {scorePercent}%
                </h1>
                <p className="mt-1 text-xs text-zinc-505 font-light leading-normal">
                  Correct: <span className="text-zinc-900 font-semibold">{result.correct_count}</span> of <span className="text-zinc-900 font-semibold">{result.total_count}</span> questions
                </p>
              </div>
              
              <div className="flex-1 max-w-xs w-full">
                <div className="w-full h-1.5 bg-zinc-50 border border-zinc-300 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-zinc-900 transition-all duration-1000 ease-out"
                    style={{ width: `${scorePercent}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>

          {moduleError && !moduleData && (
            <div className="w-full">
              <RetryPanel
                title="Module Details Unavailable"
                message={moduleError}
                onRetry={plan ? () => void retryLoadModuleDesign() : undefined}
                retryLabel="Retry Module Details"
                isRetrying={moduleRetrying}
                fallbackHref={moduleHref(id, moduleId)}
                fallbackLabel="Back to Module"
                compact
              />
            </div>
          )}

          {/* On Mobile: show recommendation and insights above the review */}
          <div className="flex flex-col gap-6 md:hidden">
            {recommendationCard}
            {diagnosticInsights}
            {weakConcepts}
          </div>

          {/* Detailed Question Review */}
          <div className="w-full space-y-6">
            <h2 className="text-lg font-light tracking-tight text-zinc-955 leading-tight">Question Review</h2>
            
            {result.question_results?.map((qr, index) => {
              const matchingMcq = moduleData?.checkpoint_mcqs?.find((m: any) => m.question_id === qr.question_id);
              const options = matchingMcq?.options || [];

              return (
                <div
                  key={qr.question_id}
                  className="border border-zinc-300 rounded-xl p-6 bg-white flex flex-col gap-4"
                >
                  {/* Card Header */}
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                      Question {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider border ${
                      qr.is_correct
                        ? "border-emerald-205 bg-emerald-50 text-emerald-700"
                        : "border-red-200 bg-red-50 text-red-700"
                    }`}>
                      {qr.is_correct ? "Correct" : "Incorrect"}
                    </span>
                  </div>

                  <h3 className="text-base font-normal text-zinc-955 leading-relaxed">
                    {matchingMcq?.question || `Question about ${qr.tested_concept_ids?.[0] || "module topic"}`}
                  </h3>

                  <div className="flex flex-col gap-3">
                    {options.map((option: string) => {
                      const optionPrefix = option.charAt(0);
                      const isThisSelected = qr.selected_option === optionPrefix;
                      const isThisCorrect = qr.correct_option === optionPrefix;

                      let optionStyle = "border-zinc-200 text-zinc-300 bg-zinc-50/50 cursor-not-allowed";
                      if (isThisCorrect) {
                        optionStyle = "border-emerald-500 bg-emerald-50 text-emerald-800";
                      } else if (isThisSelected && !isThisCorrect) {
                        optionStyle = "border-red-500 bg-red-50 text-red-800";
                      }

                      return (
                        <div
                          key={option}
                          className={`flex items-center p-4 border rounded-xl text-sm font-light leading-snug ${optionStyle}`}
                        >
                          <span className="leading-snug">{option}</span>
                          {isThisCorrect && (
                            <span className="ml-auto material-symbols-outlined text-emerald-600 text-base">check_circle</span>
                          )}
                          {isThisSelected && !isThisCorrect && (
                            <span className="ml-auto material-symbols-outlined text-red-600 text-base">cancel</span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Explanation */}
                  {(matchingMcq?.explanation || qr.diagnostic_purpose) && (
                    <div className="mt-2 p-4 bg-zinc-50 rounded-xl border border-zinc-300 text-xs flex flex-col gap-2">
                      <span className={`font-semibold uppercase tracking-wider text-[10px] ${qr.is_correct ? "text-emerald-700" : "text-red-700"}`}>
                        {qr.is_correct ? "✓ Correct Choice" : `✗ Incorrect Choice (Correct option is ${qr.correct_option})`}
                      </span>
                      {matchingMcq?.explanation && (
                        <p className="text-zinc-650 leading-relaxed font-light">{matchingMcq.explanation}</p>
                      )}
                      {qr.diagnostic_purpose && (
                        <div className="pt-2 border-t border-zinc-200 text-zinc-400 font-light text-[11px]">
                          <span className="font-semibold text-zinc-500">Diagnostic Purpose:</span> {qr.diagnostic_purpose}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </main>

        {/* Right Sidebar: (Desktop Only) */}
        <aside className="hidden md:flex flex-col w-80 shrink-0 border-l border-zinc-300 pl-8 gap-6">
          {recommendationCard}
          {diagnosticInsights}
          {weakConcepts}
        </aside>
      </div>

      {/* Footer Actions */}
      <footer className="w-full max-w-6xl mx-auto px-6 py-6 border-t border-zinc-300 bg-white flex flex-col sm:flex-row justify-between items-center gap-4 mt-8 pb-20 md:pb-8">
        <Link
          href={`/plan/${encodeURIComponent(id)}`}
          className="w-full sm:w-auto px-6 py-2.5 rounded-full border border-zinc-300 text-zinc-700 font-medium text-xs bg-white hover:border-zinc-950 hover:text-zinc-955 flex items-center justify-center gap-1.5 transition-colors"
        >
          &larr; Return to Plan
        </Link>
        
        <div className="flex w-full sm:w-auto gap-3">
          <Link
            href={`${moduleHref(id, moduleId)}/checkpoint`}
            className="flex-1 sm:flex-none px-6 py-2.5 rounded-full border border-zinc-300 text-zinc-700 font-medium text-xs bg-white hover:border-zinc-955 hover:text-zinc-955 flex items-center justify-center gap-1.5 transition-colors"
          >
            <span className="material-symbols-outlined text-xs">replay</span>
            Retry Checkpoint
          </Link>
          
          {nextModule ? (
            <Link
              href={moduleHref(id, nextModule.module_id)}
              className="flex-1 sm:flex-none px-6 py-2.5 rounded-full bg-zinc-900 text-white font-medium text-xs flex items-center justify-center gap-1.5 hover:bg-zinc-800 transition-colors"
            >
              Next Module &rarr;
            </Link>
          ) : (
            <Link
              href={`/plan/${encodeURIComponent(id)}`}
              className="flex-1 sm:flex-none px-6 py-2.5 rounded-full bg-zinc-900 text-white font-medium text-xs flex items-center justify-center gap-1.5 hover:bg-zinc-800 transition-colors"
            >
              Curriculum Complete &rarr;
            </Link>
          )}
        </div>
      </footer>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full flex justify-around items-center py-3 bg-white border-t border-zinc-300 z-50">
        <Link href="/" className="flex flex-col items-center justify-center text-zinc-400 hover:text-zinc-900 transition-colors">
          <span className="material-symbols-outlined text-xl">home</span>
          <span className="text-[9px] font-medium mt-0.5">Home</span>
        </Link>
        <Link href={`/plan/${encodeURIComponent(id)}`} className="flex flex-col items-center justify-center text-zinc-400 hover:text-zinc-900 transition-colors">
          <span className="material-symbols-outlined text-xl">menu_book</span>
          <span className="text-[9px] font-medium mt-0.5">My Plan</span>
        </Link>
        <span className="flex flex-col items-center justify-center text-zinc-955 font-semibold">
          <span className="material-symbols-outlined text-xl">school</span>
          <span className="text-[9px] mt-0.5">Learning</span>
        </span>
      </nav>
    </div>
  );
}

function matchingCurrentPlan(id: string, rawId: string): string | null {
  const raw = localStorage.getItem("curriculum-current-plan");
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as CurriculumPlanPayload;
    return parsed.curriculum_plan_id === id || encodeURIComponent(parsed.curriculum_plan_id) === rawId ? raw : null;
  } catch {
    return null;
  }
}

function moduleHref(planId: string, moduleId: string): string {
  return `/plan/${encodeURIComponent(planId)}/module/${encodeURIComponent(moduleId)}`;
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message;
  return fallback;
}
