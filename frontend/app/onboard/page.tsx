"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
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
      setError(errorMessage(err, "Failed to classify your learning intent. Check that the backend and Fireworks key are configured."));
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
      grounding_section_ids: option.grounding_section_ids,
    });
  };

  const buildPreview = async (intent: ConfirmedIntent) => {
    setFlowState("building_preview");
    setError(null);

    const onboarding: OnboardingPayload = {
      subject: "",
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
      intent_grounding_section_ids: intent.grounding_section_ids,
      subject: null,
      grade: null,
      chapter_id: null,
      max_modules: 10,
      retrieval_limit: 12,
    };

    try {
      const previewData = await previewRetrieval(queryPayload);
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
    <div className="min-h-screen bg-background text-on-surface font-public">
      <header className="sticky top-0 z-50 flex h-16 w-full items-center justify-between border-b border-outline-variant bg-surface px-6 md:px-10">
        <span className="font-hanken text-xl font-bold text-primary">AcademicFlow</span>
        <span className="rounded-full border border-outline-variant px-3 py-1 text-xs font-semibold text-on-surface-variant">
          Intent-first curriculum
        </span>
      </header>

      <main className="mx-auto flex w-full max-w-[820px] flex-col gap-8 px-4 py-12 md:px-0">
        <header className="mx-auto max-w-2xl text-center">
          <h1 className="mb-4 font-hanken text-4xl font-extrabold text-on-surface">
            What do you want to learn?
          </h1>
          <p className="mx-auto max-w-lg text-body-md text-on-surface-variant">
            Start with one query. We will confirm what you mean before retrieving textbook sections.
          </p>
        </header>

        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-error/20 bg-error-container p-4 text-on-error-container">
            <span className="material-symbols-outlined text-error">error</span>
            <p className="font-hanken text-sm font-semibold">{error}</p>
            <button
              type="button"
              onClick={() => setError(null)}
              className="material-symbols-outlined ml-auto text-on-error-container/60 hover:text-on-error-container"
              aria-label="Dismiss error"
            >
              close
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-5 rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm">
          <label className="flex flex-col gap-3">
            <span className="font-hanken text-sm font-bold text-on-surface">Learning query</span>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-4 text-on-surface-variant">
                search
              </span>
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
                className="min-h-[64px] max-h-[160px] w-full resize-none rounded-2xl border border-outline-variant bg-white py-4 pl-12 pr-4 text-body-md shadow-sm outline-none transition-all focus:border-secondary focus:bg-surface focus:ring-2 focus:ring-secondary"
                rows={1}
                disabled={isBusy}
              />
            </div>
          </label>

          <div className="flex flex-wrap gap-2">
            {["I want to learn acceleration", "I want to learn gravity", "Organic chemistry basics"].map((sample) => (
              <button
                key={sample}
                type="button"
                onClick={() => setQuery(sample)}
                disabled={isBusy}
                className="rounded-full border border-outline-variant bg-surface-container-low px-3 py-1 text-xs text-on-surface-variant transition-all hover:border-secondary hover:bg-surface-variant disabled:opacity-50"
              >
                {sample}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={isBusy}
            className="flex h-14 w-full items-center justify-center gap-2 rounded-full bg-primary px-10 font-hanken text-sm font-bold text-on-primary shadow-md transition-all hover:opacity-90 active:scale-95 disabled:opacity-50 sm:w-auto sm:self-center"
          >
            <span>{flowState === "classifying" ? "Analyzing topic..." : "Analyze Topic"}</span>
            <span className={`material-symbols-outlined ${flowState === "classifying" ? "animate-spin" : ""}`}>
              {flowState === "classifying" ? "sync" : "arrow_forward"}
            </span>
          </button>
        </form>

        {intentResult && (
          <section className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm">
            {intentResult.status === "confirmed" && intentResult.confirmed_intent ? (
              <div className="flex flex-col gap-5">
                <div className="flex items-start gap-3">
                  <span className="material-symbols-outlined mt-1 text-secondary">verified</span>
                  <div>
                    <h2 className="font-hanken text-xl font-bold text-on-surface">Confirm this learning goal</h2>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      {intentResult.confirmed_intent.user_facing_summary}
                    </p>
                  </div>
                </div>
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Refined query</p>
                  <p className="mt-1 font-hanken text-lg font-bold text-on-surface">
                    {intentResult.confirmed_intent.refined_query}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleUseConfirmedIntent}
                  disabled={flowState === "building_preview"}
                  className="flex h-12 items-center justify-center gap-2 rounded-xl bg-secondary px-5 font-hanken text-sm font-bold text-on-secondary shadow-sm transition-all hover:opacity-90 disabled:opacity-50"
                >
                  <span>{flowState === "building_preview" ? "Building preview..." : "Continue to prerequisite check"}</span>
                  <span className={`material-symbols-outlined ${flowState === "building_preview" ? "animate-spin" : ""}`}>
                    {flowState === "building_preview" ? "sync" : "arrow_forward"}
                  </span>
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-5">
                <div className="flex items-start gap-3">
                  <span className="material-symbols-outlined mt-1 text-secondary">help</span>
                  <div>
                    <h2 className="font-hanken text-xl font-bold text-on-surface">
                      {intentResult.question || "Which direction do you want to take?"}
                    </h2>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      Choose the meaning closest to your goal. These are learning intents, not raw textbook section titles.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {intentResult.options.map((option, index) => (
                    <button
                      key={intentOptionKey(option, index)}
                      type="button"
                      onClick={() => handleChooseOption(option)}
                      disabled={flowState === "building_preview"}
                      className="rounded-xl border border-outline-variant bg-white p-4 text-left transition-all hover:border-secondary hover:bg-surface-container-low disabled:opacity-50"
                    >
                      <span className="block font-hanken text-base font-bold text-on-surface">{option.label}</span>
                      <span className="mt-1 block text-sm text-on-surface-variant">
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

function intentOptionKey(option: IntentOption, index: number): string {
  return `${index}:${option.refined_query}:${option.grounding_section_ids.join("|")}`;
}
