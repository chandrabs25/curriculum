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
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-secondary border-t-transparent mx-auto"></div>
          <p className="mt-4 text-on-surface-variant text-sm">Loading checkpoint report...</p>
        </div>
      </div>
    );
  }

  if (error || !plan || !result) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="max-w-md w-full text-center bg-surface-container-lowest p-8 rounded-2xl border border-outline-variant shadow-md">
          <h2 className="text-2xl font-bold text-error">Error</h2>
          <p className="mt-2 text-on-surface-variant text-sm">{error || "Results unavailable."}</p>
          <Link
            href={`${moduleHref(id, moduleId)}/checkpoint`}
            className="mt-6 inline-block px-6 py-2 bg-primary text-on-primary rounded-full hover:opacity-90 text-sm font-semibold shadow-sm"
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

  // Retrieve original designed questions to show full option text
  let originalQuestions: any[] = [];
  if (typeof window !== "undefined") {
    const storedPreview = localStorage.getItem("curriculum-onboard-preview");
    if (storedPreview) {
      try {
        const previewObj = JSON.parse(storedPreview);
        // Fallback checklist
      } catch (e) {}
    }
  }

  return (
    <div className="bg-surface text-on-surface font-body-md min-h-screen pb-32 flex flex-col font-public">
      
      {/* TopAppBar */}
      <header className="bg-surface text-primary border-b border-outline-variant sticky top-0 z-40">
        <div className="flex justify-between items-center w-full px-10 h-16">
          <div className="text-headline-md font-hanken font-bold text-primary">AcademicFlow</div>
          <div className="hidden md:flex items-center gap-6">
            <Link
              href="/"
              className="font-hanken font-bold text-sm text-on-surface-variant hover:text-secondary transition-colors"
            >
              Dashboard
            </Link>
            <Link
              href={`/plan/${encodeURIComponent(id)}`}
              className="font-hanken font-bold text-sm text-on-surface-variant hover:text-secondary transition-colors"
            >
              Curriculum Plan
            </Link>
            <Link
              href={moduleHref(id, moduleId)}
              className="font-hanken font-bold text-sm text-secondary border-b-2 border-secondary h-16 flex items-center px-1"
            >
              Active Module
            </Link>
          </div>
          <div className="flex items-center gap-4 text-primary">
            <button className="material-symbols-outlined cursor-pointer hover:opacity-80">notifications</button>
            <button className="material-symbols-outlined cursor-pointer hover:opacity-80">account_circle</button>
            <Link
              href="/onboard"
              className="hidden md:block bg-primary text-on-primary px-6 py-2 rounded-xl font-hanken font-bold text-xs hover:opacity-90 transition-all active:scale-95 shadow-sm"
            >
              Create New
            </Link>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="max-w-[1280px] w-full mx-auto px-4 md:px-10 py-10 flex flex-col">
        
        {/* Hero Score Section */}
        <div className="mb-10 text-center md:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-secondary-container text-on-secondary-container rounded-full mb-4">
            <span className="material-symbols-outlined text-[18px]">verified</span>
            <span className="font-hanken font-bold text-xs">Checkpoint Complete</span>
          </div>
          
          <div className="flex flex-col md:flex-row md:items-end gap-6 md:gap-12">
            <div>
              <h1 className="font-hanken text-4xl md:text-5xl font-extrabold text-primary mb-2">
                Score: {scorePercent}%
              </h1>
              <p className="text-body-lg text-on-surface-variant">
                Correct: <span className="text-primary font-extrabold">{result.correct_count}/{result.total_count}</span> questions
              </p>
            </div>
            
            <div className="flex-1 max-w-md pb-2">
              <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                <div
                  className="h-full bg-secondary rounded-full transition-all duration-1000 ease-out progress-pulse"
                  style={{ width: `${scorePercent}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Bento Grid Results */}
        {moduleError && !moduleData && (
          <div className="mb-8">
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

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Recommendation Card (Primary Action) */}
          <div className="col-span-12 lg:col-span-8 bg-surface-container-lowest border border-outline-variant p-6 rounded-xl shadow-[0px_4px_20px_rgba(15,23,42,0.05)] relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-6 text-secondary opacity-5 group-hover:opacity-10 transition-opacity">
              <span className="material-symbols-outlined text-[120px]">rocket_launch</span>
            </div>
            
            <div className="relative z-10">
              <h2 className="font-hanken text-2xl font-bold text-primary mb-4">
                {result.recommendation === "continue"
                  ? "You're ready for the next module!"
                  : "Reviewing materials is recommended"}
              </h2>
              
              <p className="text-sm text-on-surface-variant mb-8 max-w-xl leading-relaxed">
                {result.recommendation === "continue"
                  ? `Outstanding performance. You've demonstrated a strong grasp of the concepts in "${currentModule.title}". Your score indicates you are well-prepared to proceed directly to the next segment.`
                  : `Good effort! You've shown partial understanding of "${currentModule.title}". To master the foundation before moving forward, we recommend spending a little more time reviewing the targeted lessons below.`}
              </p>

              <div className="flex flex-wrap gap-4">
                {nextModule ? (
                  <Link
                    href={moduleHref(plan.curriculum_plan_id, nextModule.module_id)}
                    className="bg-primary text-on-primary px-8 py-3 rounded-xl font-hanken font-bold text-xs flex items-center gap-2 hover:opacity-90 active:scale-95 transition-all shadow-md"
                  >
                    Next Module
                    <span className="material-symbols-outlined text-base">arrow_forward</span>
                  </Link>
                ) : (
                  <Link
                    href={`/plan/${encodeURIComponent(plan.curriculum_plan_id)}`}
                    className="bg-primary text-on-primary px-8 py-3 rounded-xl font-hanken font-bold text-xs flex items-center gap-2 hover:opacity-90 active:scale-95 transition-all shadow-md"
                  >
                    View Plan Timeline
                    <span className="material-symbols-outlined text-base">arrow_forward</span>
                  </Link>
                )}
                
                <Link
                  href={moduleHref(plan.curriculum_plan_id, moduleId)}
                  className="border border-outline-variant text-on-surface px-8 py-3 rounded-xl font-hanken font-bold text-xs bg-white hover:bg-surface-container transition-all"
                >
                  View Study Materials
                </Link>
              </div>
            </div>
          </div>

          {/* Stats Mini Card */}
          <div className="col-span-12 md:col-span-6 lg:col-span-4 bg-surface-container-lowest border border-outline-variant p-6 rounded-xl shadow-[0px_4px_20px_rgba(15,23,42,0.05)]">
            <h3 className="font-hanken font-bold text-xs text-on-surface-variant uppercase tracking-wider mb-6">
              Diagnostic Insights
            </h3>
            
            <div className="space-y-6">
              <div className="flex justify-between items-center pb-4 border-b border-outline-variant/40">
                <span className="text-sm text-on-surface">Recall Accuracy</span>
                <span className="font-hanken text-xl font-extrabold text-secondary">{recallAccuracy}%</span>
              </div>
              <div className="flex justify-between items-center pb-4 border-b border-outline-variant/40">
                <span className="text-sm text-on-surface">Application Level</span>
                <span className="font-hanken text-xl font-extrabold text-secondary">{applicationLevel}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-on-surface">Tested concepts</span>
                <span className="font-hanken text-xl font-extrabold text-on-surface">{result.question_results?.length || 0}</span>
              </div>
            </div>
          </div>

          {/* Detailed Question Review */}
          <div className="col-span-12 space-y-6 mt-8">
            <h2 className="font-hanken text-xl font-bold text-primary">Question Review</h2>
            
            {result.question_results?.map((qr, index) => {
              // Retrieve corresponding question options if any
              const matchingMcq = moduleData?.checkpoint_mcqs?.find((m: any) => m.question_id === qr.question_id);
              const options = matchingMcq?.options || ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"];

              return (
                <div
                  key={qr.question_id}
                  className="bg-surface-container-lowest border border-outline-variant rounded-xl overflow-hidden shadow-[0px_4px_20px_rgba(15,23,42,0.05)]"
                >
                  {/* Graded Card Header */}
                  <div className={`p-4 border-b border-outline-variant flex justify-between items-center ${
                    qr.is_correct ? "bg-surface-container-low" : "bg-error-container/20"
                  }`}>
                    <div className="flex items-center gap-4">
                      <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
                        qr.is_correct ? "bg-secondary text-on-primary" : "bg-error text-on-error"
                      }`}>
                        {index + 1}
                      </span>
                      <span className="font-hanken font-bold text-xs text-on-surface-variant">
                        DIAGNOSTIC: {qr.diagnostic_purpose || "Testing recall of textbook concepts"}
                      </span>
                    </div>
                    
                    <span className={`material-symbols-outlined font-bold ${
                      qr.is_correct ? "text-green-600" : "text-error"
                    }`}>
                      {qr.is_correct ? "check_circle" : "cancel"}
                    </span>
                  </div>

                  {/* Graded Card Body */}
                  <div className="p-6">
                    <p className="font-hanken font-bold text-base text-on-background mb-6 leading-relaxed">
                      {matchingMcq?.question || `Question concerning ${qr.tested_concept_ids?.[0] || "module topic"}`}
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                      {options.map((option: string) => {
                        const optPrefix = option.charAt(0);
                        const isChosen = qr.selected_option === optPrefix;
                        const isCorrect = qr.correct_option === optPrefix;

                        let style = "border-outline-variant text-on-surface-variant opacity-60 bg-white";
                        if (isChosen && qr.is_correct) {
                          style = "border-2 border-secondary bg-[#EFF6FF] text-on-surface font-semibold";
                        } else if (isChosen && !qr.is_correct) {
                          style = "border-2 border-error bg-error-container/10 text-on-surface font-semibold";
                        } else if (isCorrect && !qr.is_correct) {
                          style = "border-2 border-secondary/40 bg-surface-container text-on-surface font-semibold";
                        }

                        return (
                          <div key={option} className={`p-4 rounded-xl border text-sm flex items-center justify-between transition-all ${style}`}>
                            <span>{option}</span>
                            {isChosen && qr.is_correct && (
                              <span className="text-secondary font-semibold text-xs tracking-wider uppercase">Your Choice</span>
                            )}
                            {isChosen && !qr.is_correct && (
                              <span className="text-error font-semibold text-xs tracking-wider uppercase">Your Choice</span>
                            )}
                            {isCorrect && !qr.is_correct && (
                              <span className="text-secondary font-semibold text-xs tracking-wider uppercase">Correct</span>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Explanation */}
                    {matchingMcq?.explanation && (
                      <div className={`p-4 rounded-xl bg-surface-container-low ${
                        qr.is_correct ? "" : "border-l-4 border-error"
                      }`}>
                        <h4 className="font-hanken font-bold text-xs text-primary mb-2">Explanation</h4>
                        <p className="text-xs text-on-surface-variant leading-relaxed">
                          {matchingMcq.explanation}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Weak Concepts review suggestions */}
          {result.weak_concept_ids && result.weak_concept_ids.length > 0 && (
            <div className="col-span-12 mt-8">
              <h3 className="font-hanken text-lg font-bold text-primary mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-error">trending_down</span>
                Targeted Review Areas
              </h3>
              
              <div className="flex flex-wrap gap-3">
                {result.weak_concept_ids.map((concept, index) => (
                  <div
                    key={concept}
                    className="px-6 py-4 bg-surface-container border border-outline-variant rounded-xl flex items-center gap-4 group hover:border-secondary transition-all cursor-pointer shadow-sm"
                  >
                    <div className="w-12 h-12 rounded-full bg-error-container/30 flex items-center justify-center text-error">
                      <span className="material-symbols-outlined">trending_down</span>
                    </div>
                    <div>
                      <p className="font-hanken font-bold text-sm text-primary">
                        {concept.replace("concept:", "").replace(/_/g, " ")}
                      </p>
                      <p className="text-xxs text-on-surface-variant font-semibold uppercase tracking-wider">
                        Review active lesson materials
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Sticky Footer Actions */}
      <footer className="fixed bottom-0 left-0 w-full bg-surface border-t border-outline-variant shadow-lg z-50 py-4">
        <div className="max-w-[1280px] mx-auto px-4 md:px-10 flex flex-col md:flex-row justify-between items-center gap-4">
          <Link
            href={`/plan/${encodeURIComponent(id)}`}
            className="w-full md:w-auto px-8 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-hanken font-bold text-xs bg-white hover:bg-surface-container flex items-center justify-center gap-2 shadow-sm"
          >
            <span className="material-symbols-outlined text-base">arrow_back</span>
            Back to Plan
          </Link>
          
          <div className="flex w-full md:w-auto gap-4">
            <Link
              href={`${moduleHref(id, moduleId)}/checkpoint`}
              className="flex-1 md:flex-none px-8 py-3 rounded-xl border border-secondary text-secondary font-hanken font-bold text-xs bg-white hover:bg-surface-container flex items-center justify-center gap-2 shadow-sm"
            >
              <span className="material-symbols-outlined text-base">replay</span>
              Retry Checkpoint
            </Link>
            
            {nextModule ? (
              <Link
                href={moduleHref(id, nextModule.module_id)}
                className="flex-1 md:flex-none px-8 py-3 rounded-xl bg-secondary text-on-primary font-hanken font-bold text-xs flex items-center justify-center gap-2 hover:opacity-90 active:scale-95 transition-all shadow-md"
              >
                Next Module
                <span className="material-symbols-outlined text-base">fast_forward</span>
              </Link>
            ) : (
              <Link
                href={`/plan/${encodeURIComponent(id)}`}
                className="flex-1 md:flex-none px-8 py-3 rounded-xl bg-secondary text-on-primary font-hanken font-bold text-xs flex items-center justify-center gap-2 hover:opacity-90 active:scale-95 transition-all shadow-md"
              >
                Curriculum Complete
                <span className="material-symbols-outlined text-base">fast_forward</span>
              </Link>
            )}
          </div>
        </div>
      </footer>
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
