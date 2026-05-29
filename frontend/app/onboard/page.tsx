"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, classifyIntent, previewRetrieval } from "../services/api";
import {
  ConfirmedIntent,
  CurriculumQueryPayload,
  IntentClassificationResponse,
  IntentOption,
  OnboardingPayload,
} from "../types/curriculum";

type FlowState = "idle" | "classifying" | "ready" | "building_preview";

export default function OnboardPage() {
  const router = useRouter();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [topic, setTopic] = useState("");
  const [subject, setSubject] = useState("biology");
  const [flowState, setFlowState] = useState<FlowState>("idle");
  const [intentResult, setIntentResult] = useState<IntentClassificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isBusy = flowState === "classifying" || flowState === "building_preview";

  const setQuery = (text: string) => {
    setTopic(text);
    setIntentResult(null);
    setError(null);
    resizeTextarea();
  };

  const resizeTextarea = () => {
    window.requestAnimationFrame(() => {
      if (!textareaRef.current) return;
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedQuery = topic.trim();
    if (!trimmedQuery) {
      setError("Tell us what you want to learn first.");
      setIntentResult(null);
      return;
    }

    setFlowState("classifying");
    setError(null);
    setIntentResult(null);

    try {
      const classification = await classifyIntent({
        query: trimmedQuery,
        subject: null,
        grade: null,
        chapter_id: null,
        candidate_limit: 12,
      });
      setIntentResult(classification);
      setFlowState("ready");
    } catch (err: unknown) {
      console.error(err);
      setError(errorMessage(err, "Failed to classify your learning intent. Check that the backend is configured."));
      setFlowState("idle");
    }
  };

  const handleUseConfirmedIntent = async () => {
    if (!intentResult?.confirmed_intent) return;
    await buildPreview(intentResult.confirmed_intent);
  };

  const handleChooseOption = async (option: IntentOption) => {
    await buildPreview({
      label: option.label,
      user_facing_summary: option.user_facing_description,
      refined_query: option.refined_query,
    });
  };

  const buildPreview = async (intent: ConfirmedIntent) => {
    setFlowState("building_preview");
    setError(null);

    const onboarding: OnboardingPayload = {
      subject,
      topic: intent.refined_query,
      current_level: "",
      confidence: "",
      learning_goal: intent.label || `Learn ${intent.refined_query}`,
      available_time: "",
      preferred_learning_style: "",
      deadline_or_pace: "",
    };

    const queryPayload: CurriculumQueryPayload = {
      learner_id: "anonymous",
      onboarding,
      learner_state: [],
      prerequisite_check: null,
      subject,
      grade: null,
      chapter_id: null,
      max_modules: 10,
      retrieval_limit: 12,
    };

    try {
      const previewData = await previewRetrieval(queryPayload);
      clearGeneratedCurriculumState();
      localStorage.setItem("curriculum-onboard-preview", JSON.stringify(previewData));
      localStorage.setItem("curriculum-onboard-query", JSON.stringify(queryPayload));
      localStorage.setItem("curriculum-onboard-intent", JSON.stringify(intent));
      router.push("/onboard/preview");
    } catch (err: unknown) {
      console.error(err);
      setError(errorMessage(err, "Failed to build curriculum preview from the confirmed intent."));
      setFlowState("ready");
    }
  };

  return (
    <div className="min-h-screen bg-white font-sans text-zinc-900 selection:bg-zinc-100 selection:text-zinc-950">
      {/* Navigation Header */}
      <header className="w-full max-w-4xl mx-auto px-6 h-14 flex items-center justify-between border-b border-zinc-300">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-zinc-500 hover:text-zinc-900 transition-colors text-sm font-medium">
            &larr; Home
          </Link>
          <span className="text-zinc-300">|</span>
          <span className="text-sm font-semibold tracking-tight text-zinc-900">
            Start a Curriculum
          </span>
        </div>
        <span className="text-xs text-zinc-500 font-light hidden sm:inline">
          Intent-first curriculum
        </span>
      </header>

      {/* Main Content */}
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-6 pt-6 pb-12">
        <header className="max-w-xl">
          <h1 className="text-2xl font-light tracking-tight text-zinc-950 leading-tight">
            What do you want to learn?
          </h1>
          <p className="mt-1 text-xs text-zinc-500 font-light leading-normal">
            Start with a query. We will confirm your learning goal before retrieving textbook sections.
          </p>
        </header>

        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
            <span className="material-symbols-outlined text-sm">error</span>
            <p className="text-xs font-medium">{error}</p>
            <button
              type="button"
              onClick={() => setError(null)}
              className="material-symbols-outlined ml-auto text-sm text-red-500 hover:text-red-700"
              aria-label="Dismiss error"
            >
              close
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {/* 1. Learning Query */}
          <label className="flex flex-col gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-650">Learning query</span>
            <div className="relative flex items-center">
              <textarea
                ref={textareaRef}
                value={topic}
                onChange={(event) => {
                  setTopic(event.target.value);
                  setIntentResult(null);
                  resizeTextarea();
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="Example: I want to learn acceleration"
                className="w-full resize-none border border-zinc-300 rounded-xl p-3.5 text-sm font-light outline-none transition-all focus:border-zinc-950 focus:ring-1 focus:ring-zinc-950 placeholder:text-zinc-400 bg-white min-h-[72px]"
                rows={1}
                disabled={isBusy}
              />
            </div>
          </label>

          {/* 2. Sample Queries */}
          <div className="flex flex-wrap gap-2">
            {sampleQueries.map((sample) => (
              <button
                key={sample.query}
                type="button"
                onClick={() => {
                  setSubject(sample.subject);
                  setQuery(sample.query);
                }}
                disabled={isBusy}
                className="rounded-full border border-zinc-300 bg-zinc-50 px-3 py-0.5 text-[10px] font-medium text-zinc-650 transition-colors hover:border-zinc-950 hover:bg-white hover:text-zinc-950 disabled:opacity-50"
              >
                {sample.query}
              </button>
            ))}
          </div>

          {/* 3. Subject Selector */}
          <fieldset className="flex flex-col gap-2">
            <legend className="text-[10px] font-semibold uppercase tracking-wider text-zinc-650">Subject</legend>
            <div className="grid grid-cols-3 gap-2.5 max-w-sm">
              {subjectOptions.map((option) => {
                const selected = subject === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      setSubject(option.value);
                      setIntentResult(null);
                      setError(null);
                    }}
                    disabled={isBusy}
                    className={`rounded-full px-4 py-1.5 text-center text-xs font-medium border transition-colors disabled:opacity-50 ${
                      selected
                        ? "border-zinc-900 bg-zinc-900 text-white"
                        : "border-zinc-300 bg-white text-zinc-700 hover:border-zinc-950 hover:text-zinc-950"
                    }`}
                    aria-pressed={selected}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* 4. Action Button */}
          <div className="flex pt-1">
            <button
              type="submit"
              disabled={isBusy}
              className="inline-flex items-center justify-center gap-1.5 rounded-full bg-zinc-900 px-5 py-2 text-xs font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50"
            >
              <span>{flowState === "classifying" ? "Analyzing..." : "Analyze"}</span>
              <span className={`material-symbols-outlined text-xs ${flowState === "classifying" ? "animate-spin" : ""}`}>
                {flowState === "classifying" ? "sync" : "arrow_forward"}
              </span>
            </button>
          </div>
        </form>

        {intentResult && (
          <section className="border-t border-zinc-300 pt-10 mt-6">
            {intentResult.status === "confirmed" && intentResult.confirmed_intent ? (
              <div className="flex flex-col gap-6">
                <div className="flex items-start gap-2.5">
                  <span className="material-symbols-outlined text-zinc-900 text-sm mt-0.5">verified</span>
                  <div>
                    <h2 className="text-sm font-medium text-zinc-900">Confirm learning goal</h2>
                    <p className="mt-1 text-xs text-zinc-650 leading-normal font-light">
                      {intentResult.confirmed_intent.user_facing_summary}
                    </p>
                  </div>
                </div>
                <div className="border border-zinc-300 rounded-xl p-4 bg-white">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">Refined query</p>
                  <p className="mt-1 text-base font-normal text-zinc-900">
                    {intentResult.confirmed_intent.refined_query}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleUseConfirmedIntent}
                  disabled={flowState === "building_preview"}
                  className="inline-flex items-center justify-center gap-1.5 self-start rounded-full bg-zinc-900 px-6 py-2.5 text-xs font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50"
                >
                  <span>{flowState === "building_preview" ? "Building..." : "Continue"}</span>
                  <span className={`material-symbols-outlined text-xs ${flowState === "building_preview" ? "animate-spin" : ""}`}>
                    {flowState === "building_preview" ? "sync" : "arrow_forward"}
                  </span>
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-6">
                <div className="flex items-start gap-2.5">
                  <span className="material-symbols-outlined text-zinc-900 text-sm mt-0.5">help</span>
                  <div>
                    <h2 className="text-sm font-medium text-zinc-900">
                      {intentResult.question || "Choose a path"}
                    </h2>
                    <p className="mt-1 text-xs text-zinc-650 leading-normal font-light">
                      Select the meaning closest to your goal.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  {intentResult.options.map((option, index) => (
                    <button
                      key={intentOptionKey(option, index)}
                      type="button"
                      onClick={() => handleChooseOption(option)}
                      disabled={flowState === "building_preview"}
                      className="group rounded-xl border border-zinc-300 bg-white p-4 text-left transition-colors hover:border-zinc-950 disabled:opacity-50"
                    >
                      <span className="block text-sm font-normal text-zinc-900 group-hover:text-zinc-650 transition-colors">
                        {option.label}
                      </span>
                      <span className="mt-1 block text-xs text-zinc-550 font-light">
                        {option.user_facing_description}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError || err instanceof Error) return err.message;
  return fallback;
}

function clearGeneratedCurriculumState(): void {
  const prefixes = [
    "curriculum-plan-",
    "curriculum-current-plan",
    "curriculum-module-design-",
    "curriculum-checkpoint-score-",
    "curriculum-checkpoint-result-",
  ];
  for (const key of Object.keys(localStorage)) {
    if (prefixes.some((prefix) => key === prefix || key.startsWith(prefix))) {
      localStorage.removeItem(key);
    }
  }
}

function intentOptionKey(option: IntentOption, index: number): string {
  return `${index}:${option.refined_query}`;
}

const subjectOptions = [
  { value: "biology", label: "Biology" },
  { value: "physics", label: "Physics" },
  { value: "chemistry", label: "Chemistry" },
];

const sampleQueries = [
  { subject: "physics", query: "I want to learn acceleration" },
  { subject: "physics", query: "I want to learn gravity" },
  { subject: "biology", query: "I want to learn photosynthesis" },
  { subject: "chemistry", query: "Organic chemistry basics" },
];

