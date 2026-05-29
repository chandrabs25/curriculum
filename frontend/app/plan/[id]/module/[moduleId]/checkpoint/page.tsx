"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { RetryPanel } from "../../../../../components/RetryPanel";
import { designModule, submitCheckpoint } from "../../../../../services/api";
import { readCachedModuleDesign, writeCachedModuleDesign } from "../../../../../services/moduleDesignCache";
import { readSectionInsights, sectionIdsFromMcqs, writeSectionInsights } from "../../../../../services/sectionInsights";
import {
  CurriculumPlanPayload,
  CheckpointAnswerPayload,
  ExpandedCurriculumModulePayload,
} from "../../../../../types/curriculum";

export default function CheckpointQuizPage() {
  const params = useParams();
  const router = useRouter();
  const rawId = params.id as string;
  const id = decodeURIComponent(rawId);
  const rawModuleId = params.moduleId as string;
  const moduleId = decodeURIComponent(rawModuleId);

  const [plan, setPlan] = useState<CurriculumPlanPayload | null>(null);
  const [moduleData, setModuleData] = useState<ExpandedCurriculumModulePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selection states
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [quizResult, setQuizResult] = useState<any | null>(null);

  const loadModuleDesign = useCallback(
    async (parsedPlan: CurriculumPlanPayload, useCache: boolean) => {
      setError(null);
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
        section_insights: readSectionInsights(
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
    setRetrying(true);
    setError(null);
    try {
      await loadModuleDesign(plan, false);
    } catch (err: unknown) {
      console.error(err);
      setError(errorMessage(err, "Failed to load checkpoint MCQs from backend."));
    } finally {
      setRetrying(false);
      setLoading(false);
    }
  }, [loadModuleDesign, plan]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedPlan =
        localStorage.getItem(`curriculum-plan-${id}`) ||
        localStorage.getItem(`curriculum-plan-${rawId}`) ||
        matchingCurrentPlan(id, rawId);
      if (!storedPlan) {
        setError("Plan not found. Please regenerate onboarding.");
        setLoading(false);
        return;
      }

      try {
        const parsedPlan = JSON.parse(storedPlan) as CurriculumPlanPayload;
        setPlan(parsedPlan);

        loadModuleDesign(parsedPlan, true)
          .catch((err) => {
            console.error(err);
            setError(errorMessage(err, "Failed to load checkpoint MCQs from backend."));
          })
          .finally(() => {
            setLoading(false);
          });
      } catch (e) {
        setError("Invalid curriculum plan file format.");
        setLoading(false);
      }
    }
  }, [id, loadModuleDesign, rawId]);

  const handleSelectOption = (questionId: string, optionPrefix: string) => {
    if (quizResult || submitting) return;
    setAnswers((prev) => ({
      ...prev,
      [questionId]: optionPrefix,
    }));
  };

  const handleQuizSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!plan || !moduleData) return;

    const mcqs = moduleData.checkpoint_mcqs || [];
    if (Object.keys(answers).length < mcqs.length) {
      setError("Please answer all questions before submitting.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const answerPayloads: CheckpointAnswerPayload[] = Object.entries(answers).map(
      ([qId, opt]) => ({
        question_id: qId,
        selected_option: opt,
      })
    );

    try {
      const result = await submitCheckpoint({
        learner_id: plan.learner_id,
        curriculum_plan_id: plan.curriculum_plan_id,
        module_id: moduleId,
        checkpoint_mcqs: mcqs,
        answers: answerPayloads,
        existing_section_insights: readSectionInsights(plan.learner_id, sectionIdsFromMcqs(mcqs)),
      });
      
      // Delay slightly to show "Grading your submission..." shimmer state
      setTimeout(() => {
        // Save completed module score to localStorage
        localStorage.setItem(`curriculum-checkpoint-score-${id}-${moduleId}`, String(result.score));
        localStorage.setItem(`curriculum-checkpoint-score-${rawId}-${rawModuleId}`, String(result.score));
        localStorage.setItem(`curriculum-checkpoint-result-${id}-${moduleId}`, JSON.stringify(result));
        localStorage.setItem(`curriculum-checkpoint-result-${rawId}-${rawModuleId}`, JSON.stringify(result));
        writeSectionInsights(result.section_insights || []);
        setSubmitting(false);
        router.push(`${moduleHref(id, moduleId)}/checkpoint/results`);
      }, 1500);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to submit checkpoint responses.");
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-secondary border-t-transparent mx-auto"></div>
          <p className="mt-4 text-on-surface-variant text-sm">Loading checkpoint MCQs...</p>
        </div>
      </div>
    );
  }

  if (error && !moduleData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="max-w-md w-full text-center bg-surface-container-lowest p-8 rounded-2xl border border-outline-variant shadow-md">
          <RetryPanel
            title="Checkpoint Load Failed"
            message={error}
            onRetry={plan ? () => void retryLoadModuleDesign() : undefined}
            retryLabel="Retry Checkpoint"
            isRetrying={retrying}
            fallbackHref={moduleHref(id, moduleId)}
            fallbackLabel="Back to Module"
          />
        </div>
      </div>
    );
  }

  if (!moduleData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="max-w-md w-full">
          <RetryPanel
            title="Checkpoint Unavailable"
            message="The checkpoint questions were not loaded."
            onRetry={plan ? () => void retryLoadModuleDesign() : undefined}
            retryLabel="Retry Checkpoint"
            isRetrying={retrying}
            fallbackHref={moduleHref(id, moduleId)}
            fallbackLabel="Back to Module"
          />
        </div>
      </div>
    );
  }

  const mcqs = moduleData.checkpoint_mcqs || [];
  const answeredCount = Object.keys(answers).length;
  const progressPercent = mcqs.length > 0 ? Math.round((answeredCount / mcqs.length) * 100) : 0;
  const allAnswered = answeredCount === mcqs.length;

  return (
    <div className="bg-surface text-on-surface font-body-md min-h-screen selection:bg-surface-variant flex flex-col">
      
      {/* Top Navigation Bar */}
      <header className="bg-surface border-b border-outline-variant flex justify-between items-center w-full px-10 h-16 sticky top-0 z-40">
        <div className="flex items-center gap-2">
          <span className="text-headline-md font-hanken font-bold text-primary">AcademicFlow</span>
        </div>
        <div className="hidden md:flex items-center gap-6">
          <Link
            href="/"
            className="text-on-surface-variant hover:text-secondary transition-colors font-hanken font-bold text-sm"
          >
            Dashboard
          </Link>
          <Link
            href={`/plan/${encodeURIComponent(id)}`}
            className="text-on-surface-variant hover:text-secondary transition-colors font-hanken font-bold text-sm"
          >
            Curriculum Plan
          </Link>
          <Link
            href={moduleHref(id, moduleId)}
            className="text-secondary border-b-2 border-secondary font-hanken font-bold text-sm h-16 flex items-center px-1"
          >
            Active Module
          </Link>
        </div>
        <div className="flex items-center gap-6">
          <button className="material-symbols-outlined text-on-surface-variant p-2 hover:bg-surface-container rounded-full transition-all cursor-pointer">
            notifications
          </button>
          <button className="material-symbols-outlined text-on-surface-variant p-2 hover:bg-surface-container rounded-full transition-all cursor-pointer">
            account_circle
          </button>
        </div>
      </header>

      {/* Main Body */}
      <main className="max-w-[1280px] w-full mx-auto px-4 md:px-10 py-10 flex flex-col items-center flex-1">
        
        {/* Header & Progress Indicator */}
        <div className="w-full max-w-3xl mb-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-3">
            <div>
              <span className="text-xs text-secondary font-bold uppercase tracking-wider block mb-1">
                {plan?.onboarding.topic}
              </span>
              <h1 className="font-hanken text-2xl md:text-3xl font-extrabold text-primary mb-1">
                Module {moduleData.checkpoint_mcqs ? "" : ""} Checkpoint
              </h1>
              <p className="text-sm text-on-surface-variant">
                {moduleData.title} • comfort assessment
              </p>
            </div>
            
            <span className="font-hanken font-bold text-sm text-secondary mt-3 md:mt-0" id="progress-text">
              {answeredCount} of {mcqs.length} questions answered
            </span>
          </div>

          <div className="w-full h-2 bg-surface-container rounded-full overflow-hidden">
            <div
              className="h-full bg-secondary-container transition-all duration-500 ease-out"
              id="progress-bar"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
        </div>

        {error && (
          <div className="w-full max-w-3xl mb-6 p-4 bg-error-container text-on-error-container border border-error/20 rounded-xl text-xs font-semibold">
            {error}
          </div>
        )}

        {/* Dynamic Graded Results Summary */}
        {quizResult && (
          <div className="w-full max-w-3xl mb-8 p-6 rounded-xl bg-[#EFF6FF] border border-secondary/20 shadow-md animate-fadeIn">
            <h3 className="font-hanken text-lg font-bold text-secondary mb-2 flex items-center gap-2">
              <span className="material-symbols-outlined">verified</span>
              Checkpoint Graded successfully!
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-center">
              <div className="bg-white p-3 rounded-lg border border-outline-variant/40">
                <span className="text-[10px] text-on-surface-variant block uppercase font-bold tracking-wider">Score</span>
                <span className="text-xl font-extrabold text-on-background">
                  {Math.round(quizResult.score * 100)}%
                </span>
              </div>
              <div className="bg-white p-3 rounded-lg border border-outline-variant/40">
                <span className="text-[10px] text-on-surface-variant block uppercase font-bold tracking-wider">Correct</span>
                <span className="text-xl font-extrabold text-on-background">
                  {quizResult.correct_count} / {quizResult.total_count}
                </span>
              </div>
              <div className="bg-white p-3 rounded-lg border border-outline-variant/40 col-span-2">
                <span className="text-[10px] text-on-surface-variant block uppercase font-bold tracking-wider">AI Recommendation</span>
                <span className={`text-sm font-bold block mt-1 uppercase ${
                  quizResult.recommendation === "continue" ? "text-emerald-600" : "text-amber-600"
                }`}>
                  {quizResult.recommendation === "continue" ? "Mastered • Continue" : "Review Recommended"}
                </span>
              </div>
            </div>

            {quizResult.weak_concept_ids && quizResult.weak_concept_ids.length > 0 && (
              <div className="mt-4 pt-4 border-t border-secondary/25">
                <span className="text-[10px] font-bold text-secondary uppercase tracking-wider block mb-2">
                  Reviewing concepts recommended:
                </span>
                <div className="flex flex-wrap gap-2">
                  {quizResult.weak_concept_ids.map((concept: string) => (
                    <span
                      key={concept}
                      className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded text-xs font-semibold"
                    >
                      {concept.replace("concept:", "").replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Quiz Form */}
        <form onSubmit={handleQuizSubmit} className="w-full max-w-3xl space-y-6" id="quiz-form">
          {mcqs.map((mcq: any, qIdx: number) => {
            const selectedVal = answers[mcq.question_id] || "";
            const isSelected = (prefix: string) => selectedVal === prefix;

            const isGraded = !!quizResult;
            const qr = quizResult?.question_results?.find(
              (res: any) => res.question_id === mcq.question_id
            );

            return (
              <div
                key={mcq.question_id}
                className={`bg-surface-container-lowest border border-outline-variant rounded-xl p-6 shadow-[0px_4px_20px_rgba(15,23,42,0.05)] transition-all ${
                  isGraded ? "opacity-90" : ""
                }`}
              >
                <div className="flex justify-between items-start mb-4">
                  <span className="font-hanken font-bold text-xs text-on-surface-variant uppercase tracking-wider">
                    Question {String(qIdx + 1).padStart(2, "0")}
                  </span>
                  <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${
                    mcq.difficulty.toLowerCase() === "hard"
                      ? "bg-error-container text-on-error-container"
                      : "bg-surface-container-high text-on-primary-fixed-variant"
                  }`}>
                    {mcq.difficulty}
                  </span>
                </div>

                <h3 className="font-hanken font-bold text-base text-on-surface mb-6 leading-relaxed">
                  {mcq.question}
                </h3>

                <div className="space-y-3">
                  {mcq.options.map((option: string) => {
                    const optionPrefix = option.charAt(0);
                    const isThisSelected = isSelected(optionPrefix);
                    const isThisCorrect = mcq.correct_option === optionPrefix;

                    let optionStyle = "border-outline-variant bg-surface-container-lowest hover:border-secondary";
                    if (isThisSelected) {
                      optionStyle = "bg-[#EFF6FF] border-secondary border-2 ring-1 ring-secondary";
                    }

                    if (isGraded) {
                      if (isThisCorrect) {
                        optionStyle = "border-emerald-500 bg-emerald-50/75 text-emerald-800 border-2";
                      } else if (isThisSelected && !isThisCorrect) {
                        optionStyle = "border-red-500 bg-red-50/75 text-red-800 border-2";
                      } else {
                        optionStyle = "border-outline-variant/40 text-on-surface-variant/40 bg-white/40 cursor-not-allowed";
                      }
                    }

                    return (
                      <label
                        key={option}
                        onClick={() => handleSelectOption(mcq.question_id, optionPrefix)}
                        className={`flex items-center p-4 border rounded-lg cursor-pointer transition-all group quiz-option ${optionStyle}`}
                      >
                        <input
                          type="radio"
                          disabled={isGraded || submitting}
                          name={mcq.question_id}
                          checked={isThisSelected}
                          onChange={() => {}} // Controlled click handles this
                          className="w-4 h-4 text-secondary focus:ring-secondary border-outline-variant cursor-pointer disabled:opacity-50"
                        />
                        <span className="ml-4 text-sm text-on-surface leading-tight">
                          {option}
                        </span>
                        
                        {isGraded && isThisCorrect && (
                          <span className="ml-auto material-symbols-outlined text-emerald-600 text-base">check_circle</span>
                        )}
                        {isGraded && isThisSelected && !isThisCorrect && (
                          <span className="ml-auto material-symbols-outlined text-red-600 text-base">cancel</span>
                        )}
                      </label>
                    );
                  })}
                </div>

                {/* Show Explanations on Graded */}
                {isGraded && (
                  <div className="mt-4 p-4 bg-surface-container-low rounded-lg border border-outline-variant/60 text-xs">
                    <span className={`font-bold block mb-1 uppercase ${qr?.is_correct ? "text-emerald-700" : "text-red-700"}`}>
                      {qr?.is_correct ? "✓ Correct!" : `✗ Incorrect (Correct Option is ${mcq.correct_option})`}
                    </span>
                    <p className="text-on-surface-variant leading-relaxed mb-2">{mcq.explanation}</p>
                    {mcq.diagnostic_purpose && (
                      <div className="pt-2 border-t border-outline-variant/30 text-gray-500">
                        <span className="font-semibold">Diagnostic Purpose:</span> {mcq.diagnostic_purpose}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Action Area */}
          <div className="flex flex-col items-center pt-6 pb-12">
            {!submitting && !quizResult && (
              <button
                type="submit"
                disabled={!allAnswered || submitting}
                className="w-full md:w-64 py-4 bg-primary text-on-primary font-hanken font-bold text-sm rounded-lg hover:opacity-90 active:scale-95 transition-all shadow-md flex justify-center items-center gap-2 cursor-pointer disabled:bg-outline-variant disabled:cursor-not-allowed disabled:opacity-50"
              >
                Submit Answers
              </button>
            )}

            {/* Shimmer State */}
            {submitting && (
              <div className="flex flex-col items-center mt-4" id="grading-state">
                <div className="flex items-center gap-3 text-secondary animate-pulse">
                  <span className="material-symbols-outlined animate-spin text-xl">sync</span>
                  <span className="font-hanken font-bold text-sm">Grading your submission...</span>
                </div>
                <p className="text-xs text-on-surface-variant mt-2 text-center max-w-xs">
                  Our AI is analyzing your responses against the curriculum benchmarks.
                </p>
              </div>
            )}

            {/* Final navigation button */}
            {quizResult && (
              <div className="flex gap-4 w-full max-w-md mt-4">
                <button
                  type="button"
                  onClick={() => {
                    setAnswers({});
                    setQuizResult(null);
                    setError(null);
                  }}
                  className="flex-1 py-3 border border-outline-variant bg-white text-on-surface-variant hover:bg-surface-container rounded-lg font-hanken font-bold text-sm cursor-pointer shadow-sm"
                >
                  Reset Checkpoint
                </button>
                <Link
                  href={`/plan/${encodeURIComponent(id)}`}
                  className="flex-1 py-3 bg-primary text-on-primary hover:opacity-90 rounded-lg font-hanken font-bold text-sm shadow-md block text-center"
                >
                  Return to Pathway
                </Link>
              </div>
            )}
          </div>
        </form>

        {/* Illustration / Decor */}
        <div className="mt-8 w-full max-w-3xl opacity-40 hidden md:block">
          <div className="h-40 w-full rounded-xl overflow-hidden grayscale border border-outline-variant/30">
            <img
              alt="academic study decoration"
              className="w-full h-full object-cover"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAen1gCc3HOgrdq6YXY8kd0KHt5uNf3fN7vu3dv5VUGW1LvhAkDiuCzTzu055B_r0VpnEn2173RjFCDOMxZEkrDGEmDk5U68tA9AxnSNR-hFtUb4UDIyaaXAertazwO0LBZpQREOxITrT0Bf_AagNrt4a5NJ-OohNGkSzZqYDde6hmGx9hX8kVCrk0oxoBexJadVoO2H5VLQXsNFzxH0wWU9kg9UE63Qlek5HDroE_bchI0aFPyOHM_OsWDzM7Q2m8QMpCQoTgc-2ZA"
            />
          </div>
        </div>
      </main>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full flex justify-around items-center py-2 bg-surface-container-lowest border-t border-outline-variant shadow-lg z-50 rounded-t-xl">
        <Link href="/" className="flex flex-col items-center justify-center text-on-surface-variant hover:text-secondary">
          <span className="material-symbols-outlined">home</span>
          <span className="text-[10px]">Home</span>
        </Link>
        <Link href={`/plan/${encodeURIComponent(id)}`} className="flex flex-col items-center justify-center text-on-surface-variant hover:text-secondary">
          <span className="material-symbols-outlined">menu_book</span>
          <span className="text-[10px]">My Plan</span>
        </Link>
        <span className="flex flex-col items-center justify-center text-secondary font-bold">
          <span className="material-symbols-outlined">school</span>
          <span className="text-[10px]">Learning</span>
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
