"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { RetryPanel } from "../../../../../components/RetryPanel";
import { designModule, submitCheckpoint } from "../../../../../services/api";
import { readCachedModuleDesign, writeCachedModuleDesign } from "../../../../../services/moduleDesignCache";
import { readLatestSectionInsights, sectionIdsFromMcqs, writeSectionInsights } from "../../../../../services/sectionInsights";
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
        existing_section_insights: readLatestSectionInsights(plan.learner_id, sectionIdsFromMcqs(mcqs)),
      });
      
      // Delay slightly to show grading shimmer state
      setTimeout(() => {
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
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="text-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent mx-auto"></div>
          <p className="mt-4 text-xs text-zinc-400 font-light">Loading checkpoint quiz...</p>
        </div>
      </div>
    );
  }

  if (error && !moduleData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white px-4">
        <div className="max-w-md w-full text-center bg-white p-8 rounded-xl border border-zinc-300">
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
      <div className="flex min-h-screen items-center justify-center bg-white px-4">
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
    <div className="bg-white text-zinc-900 font-sans min-h-screen selection:bg-zinc-100 selection:text-zinc-950 flex flex-col">
      {/* Navigation Header */}
      <header className="w-full max-w-4xl mx-auto px-6 h-14 flex items-center justify-between border-b border-zinc-300 bg-white">
        <div className="flex items-center gap-3">
          <Link href={moduleHref(id, moduleId)} className="text-zinc-500 hover:text-zinc-900 transition-colors text-sm font-medium">
            &larr; Module
          </Link>
          <span className="text-zinc-200">|</span>
          <span className="text-sm font-semibold tracking-tight text-zinc-900 truncate max-w-[200px] md:max-w-md">
            Checkpoint Quiz
          </span>
        </div>
        <span className="text-xs text-zinc-500 font-light hidden sm:inline">
          {answeredCount} of {mcqs.length} answered
        </span>
      </header>

      {/* Main Body */}
      <main className="mx-auto flex w-full max-w-3xl flex-col px-6 py-10 gap-8 flex-1">
        {/* Header & Progress Indicator */}
        <div className="w-full mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 block mb-1">
            {plan?.onboarding.topic}
          </span>
          <h1 className="text-2xl font-light tracking-tight text-zinc-950 leading-tight">
            Module Checkpoint
          </h1>
          <p className="mt-1 text-xs text-zinc-500 font-light leading-normal">
            {moduleData.title} &bull; comfort assessment
          </p>

          <div className="mt-6 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-zinc-400 mb-2">
            <span>Progress</span>
            <span>{answeredCount} of {mcqs.length} answered</span>
          </div>
          <div className="w-full h-1.5 bg-zinc-50 border border-zinc-300 rounded-full overflow-hidden">
            <div
              className="h-full bg-zinc-900 transition-all duration-500 ease-out"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
        </div>

        {error && (
          <div className="w-full p-4 bg-red-50 text-red-750 border border-red-200 rounded-xl text-xs font-semibold">
            {error}
          </div>
        )}

        {/* Dynamic Graded Results Summary */}
        {quizResult && (
          <div className="w-full p-6 rounded-xl bg-zinc-50 border border-zinc-300 flex flex-col gap-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-700 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-sm">verified</span>
              Checkpoint Graded
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
              <div className="bg-white p-3 rounded-lg border border-zinc-300">
                <span className="text-[9px] text-zinc-400 block uppercase font-medium tracking-wider">Score</span>
                <span className="text-lg font-normal text-zinc-900">
                  {Math.round(quizResult.score * 100)}%
                </span>
              </div>
              <div className="bg-white p-3 rounded-lg border border-zinc-300">
                <span className="text-[9px] text-zinc-400 block uppercase font-medium tracking-wider">Correct</span>
                <span className="text-lg font-normal text-zinc-900">
                  {quizResult.correct_count} / {quizResult.total_count}
                </span>
              </div>
              <div className="bg-white p-3 rounded-lg border border-zinc-300 col-span-2">
                <span className="text-[9px] text-zinc-400 block uppercase font-medium tracking-wider">AI Recommendation</span>
                <span className={`text-xs font-semibold block mt-1 uppercase ${
                  quizResult.recommendation === "continue" ? "text-emerald-600" : "text-amber-600"
                }`}>
                  {quizResult.recommendation === "continue" ? "Mastered • Continue" : "Review Recommended"}
                </span>
              </div>
            </div>

            {quizResult.weak_concept_ids && quizResult.weak_concept_ids.length > 0 && (
              <div className="pt-4 border-t border-zinc-200">
                <span className="text-[9px] font-semibold text-zinc-500 uppercase tracking-wider block mb-2">
                  Reviewing concepts recommended:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {quizResult.weak_concept_ids.map((concept: string) => (
                    <span
                      key={concept}
                      className="bg-zinc-100 border border-zinc-300 text-zinc-650 px-2.5 py-0.5 rounded-full text-xs font-light"
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
        <form onSubmit={handleQuizSubmit} className="w-full space-y-6" id="quiz-form">
          {mcqs.map((mcq: any, qIdx: number) => {
            const selectedVal = answers[mcq.question_id] || "";
            const isSelected = (optionPrefix: string) => selectedVal === optionPrefix;

            const isGraded = !!quizResult;
            const qr = quizResult?.question_results?.find(
              (res: any) => res.question_id === mcq.question_id
            );

            return (
              <div
                key={mcq.question_id}
                className={`border border-zinc-300 rounded-xl p-6 bg-white flex flex-col gap-4 ${
                  isGraded ? "opacity-90" : ""
                }`}
              >
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                    Question {String(qIdx + 1).padStart(2, "0")}
                  </span>
                  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider border ${
                    mcq.difficulty.toLowerCase() === "hard"
                      ? "border-red-200 bg-red-50 text-red-700"
                      : "border-zinc-200 bg-zinc-50 text-zinc-650"
                  }`}>
                    {mcq.difficulty}
                  </span>
                </div>

                <h3 className="text-base font-normal text-zinc-950 leading-relaxed">
                  {mcq.question}
                </h3>

                <div className="flex flex-col gap-3">
                  {mcq.options.map((option: string) => {
                    const optionPrefix = option.charAt(0);
                    const isThisSelected = isSelected(optionPrefix);
                    const isThisCorrect = mcq.correct_option === optionPrefix;

                    let optionStyle = "border-zinc-300 bg-white text-zinc-800 hover:border-zinc-950 hover:text-zinc-950";
                    if (isThisSelected) {
                      optionStyle = "bg-zinc-950 text-white border-zinc-955";
                    }

                    if (isGraded) {
                      if (isThisCorrect) {
                        optionStyle = "border-emerald-500 bg-emerald-50 text-emerald-800";
                      } else if (isThisSelected && !isThisCorrect) {
                        optionStyle = "border-red-500 bg-red-50 text-red-800";
                      } else {
                        optionStyle = "border-zinc-200 text-zinc-300 bg-zinc-50/50 cursor-not-allowed";
                      }
                    }

                    return (
                      <label
                        key={option}
                        onClick={() => handleSelectOption(mcq.question_id, optionPrefix)}
                        className={`flex items-center p-4 border rounded-xl cursor-pointer transition-colors text-sm font-light ${optionStyle}`}
                      >
                        <input
                          type="radio"
                          disabled={isGraded || submitting}
                          name={mcq.question_id}
                          checked={isThisSelected}
                          onChange={() => {}}
                          className="sr-only"
                        />
                        <span className="leading-snug">{option}</span>
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
                  <div className="mt-2 p-4 bg-zinc-50 rounded-xl border border-zinc-300 text-xs flex flex-col gap-2">
                    <span className={`font-semibold uppercase tracking-wider text-[10px] ${qr?.is_correct ? "text-emerald-700" : "text-red-700"}`}>
                      {qr?.is_correct ? "✓ Correct" : `✗ Incorrect (Correct Option is ${mcq.correct_option})`}
                    </span>
                    <p className="text-zinc-655 leading-relaxed font-light">{mcq.explanation}</p>
                    {mcq.diagnostic_purpose && (
                      <div className="pt-2 border-t border-zinc-200 text-zinc-400 font-light text-[11px]">
                        <span className="font-semibold text-zinc-500">Diagnostic Purpose:</span> {mcq.diagnostic_purpose}
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
                className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-8 py-3 text-xs font-semibold text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 disabled:bg-zinc-300 disabled:cursor-not-allowed"
              >
                Submit Answers
              </button>
            )}

            {/* Shimmer State */}
            {submitting && (
              <div className="flex flex-col items-center mt-4">
                <div className="flex items-center gap-2 text-zinc-900 animate-pulse font-medium text-xs uppercase tracking-wider">
                  <span className="material-symbols-outlined animate-spin text-sm">sync</span>
                  <span>Grading responses...</span>
                </div>
                <p className="text-[11px] text-zinc-400 mt-1.5 text-center font-light">
                  Analyzing your responses against the curriculum benchmarks.
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
                  className="flex-1 py-3 border border-zinc-300 bg-white text-zinc-650 hover:text-zinc-900 hover:border-zinc-900 rounded-full text-xs font-medium transition-colors"
                >
                  Reset Checkpoint
                </button>
                <Link
                  href={`/plan/${encodeURIComponent(id)}`}
                  className="flex-1 py-3 bg-zinc-900 text-white hover:bg-zinc-800 rounded-full text-xs font-medium block text-center transition-colors"
                >
                  Return to Pathway
                </Link>
              </div>
            )}
          </div>
        </form>
      </main>

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
        <span className="flex flex-col items-center justify-center text-zinc-950 font-semibold">
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
