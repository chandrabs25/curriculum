"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { RetryPanel } from "../../components/RetryPanel";
import { ApiError, createCurriculumPlan } from "../../services/api";
import {
  CurriculumQueryPayload,
  CurriculumPlanningPacket,
  PlanningPacketSection,
  RetrievalPreviewResponse,
} from "../../types/curriculum";

type GenerationPhase = "loading" | "reading" | "planning" | "done" | "error";

type ReadingItem = {
  id: string;
  title: string;
  summary: string;
  role: "Target" | "Prerequisite" | "Support";
  icon: string;
};

export default function OnboardPreviewPage() {
  const router = useRouter();
  const generationStarted = useRef(false);
  const progressTimer = useRef<number | null>(null);

  const [previewData, setPreviewData] = useState<RetrievalPreviewResponse | null>(null);
  const [query, setQuery] = useState<CurriculumQueryPayload | null>(null);
  const [phase, setPhase] = useState<GenerationPhase>("loading");
  const [progressWidth, setProgressWidth] = useState(8);
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [planAttemptCount, setPlanAttemptCount] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const storedPreview = localStorage.getItem("curriculum-onboard-preview");
    const storedQuery = localStorage.getItem("curriculum-onboard-query");

    if (!storedPreview || !storedQuery) {
      window.setTimeout(() => {
        setError("Onboarding query context not found. Please start again.");
        setPhase("error");
      }, 0);
      return;
    }

    try {
      const parsedPreview = JSON.parse(storedPreview) as RetrievalPreviewResponse;
      const parsedQuery = JSON.parse(storedQuery) as CurriculumQueryPayload;
      if (!parsedPreview.planning_packet?.main_path_section_ids?.length) {
        window.setTimeout(() => {
          setError("Stored preview is stale. Please run the query again.");
          setPhase("error");
        }, 0);
        return;
      }
      window.setTimeout(() => {
        setPreviewData(parsedPreview);
        setQuery(parsedQuery);
        setPhase("reading");
      }, 0);
    } catch {
      window.setTimeout(() => {
        setError("Failed to load retrieval preview details.");
        setPhase("error");
      }, 0);
    }
  }, []);

  const readingItems = useMemo(() => {
    if (!previewData) return [];
    return buildReadingItems(previewData.planning_packet);
  }, [previewData]);

  const visibleConcepts = useMemo(() => {
    const packet = previewData?.planning_packet;
    if (!packet) return [];
    const seen = new Set<string>();
    return packet.relationships.hard_dependencies
      .map((row) => row.bridge_concept_id)
      .filter((conceptId): conceptId is string => {
        if (!conceptId || seen.has(conceptId)) return false;
        seen.add(conceptId);
        return true;
      })
      .slice(0, 12)
      .map((conceptId) => conceptId.replace("concept:", "").replaceAll("_", " "));
  }, [previewData]);

  const generatePlan = useCallback(async () => {
    if (!query || !previewData || generationStarted.current) return;
    generationStarted.current = true;
    setPhase("planning");
    setError(null);
    setPlanAttemptCount((current) => current + 1);
    setProgressWidth(38);
    setActiveStep(1);

    progressTimer.current = window.setInterval(() => {
      setProgressWidth((current) => Math.min(94, current + 7));
      setActiveStep((current) => Math.min(2, current + 1));
    }, 900);

    const finalQuery: CurriculumQueryPayload = {
      ...query,
      prerequisite_check: {
        asked: false,
        answers: [],
      },
    };

    try {
      const plan = await createCurriculumPlan(finalQuery);
      if (progressTimer.current) window.clearInterval(progressTimer.current);
      setProgressWidth(100);
      setActiveStep(3);
      setPhase("done");

      const serializedPlan = JSON.stringify(plan);
      const encodedPlanId = encodeURIComponent(plan.curriculum_plan_id);
      localStorage.setItem(`curriculum-plan-${plan.curriculum_plan_id}`, serializedPlan);
      localStorage.setItem(`curriculum-plan-${encodedPlanId}`, serializedPlan);
      localStorage.setItem("curriculum-current-plan", serializedPlan);

      window.setTimeout(() => {
        router.push(`/plan/${encodeURIComponent(plan.curriculum_plan_id)}`);
      }, 600);
    } catch (err: unknown) {
      if (progressTimer.current) window.clearInterval(progressTimer.current);
      generationStarted.current = false;
      setPhase("error");
      setError(errorMessage(err, "Failed to generate curriculum. Please check backend connections."));
    }
  }, [previewData, query, router]);

  useEffect(() => {
    if (!previewData || !query || phase !== "reading" || generationStarted.current) return;

    const stepTimer = window.setInterval(() => {
      setActiveStep((current) => Math.min(2, current + 1));
      setProgressWidth((current) => Math.min(34, current + 9));
    }, 450);

    const generateTimer = window.setTimeout(() => {
      window.clearInterval(stepTimer);
      void generatePlan();
    }, 1200);

    return () => {
      window.clearInterval(stepTimer);
      window.clearTimeout(generateTimer);
    };
  }, [generatePlan, phase, previewData, query]);

  useEffect(() => {
    return () => {
      if (progressTimer.current) window.clearInterval(progressTimer.current);
    };
  }, []);

  if (phase === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-secondary border-t-transparent" />
          <p className="mt-4 text-sm text-on-surface-variant">Loading retrieval context...</p>
        </div>
      </div>
    );
  }

  if (phase === "error" || !previewData || !query) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-md">
          <RetryPanel
            title="Generation Paused"
            message={
              planAttemptCount > 1
                ? `${error || "Preview unavailable."} Attempted ${planAttemptCount} times.`
                : error || "Preview unavailable."
            }
            onRetry={previewData && query ? () => void generatePlan() : undefined}
            retryLabel="Retry Generation"
            isRetrying={phase === "planning"}
            fallbackHref="/onboard"
            fallbackLabel="Back to Onboarding"
          />
        </div>
      </div>
    );
  }

  const planningPacket = previewData.planning_packet;
  return (
    <div className="min-h-screen overflow-hidden bg-background font-public text-on-surface">
      <style>{`
        @keyframes readingRail {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }

        @keyframes floatIn {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }

        @keyframes pulseGlow {
          0%, 100% { opacity: 0.45; transform: scale(0.98); }
          50% { opacity: 1; transform: scale(1); }
        }

        .reading-rail {
          animation: readingRail 24s linear infinite;
        }

        .float-in {
          animation: floatIn 0.7s ease-out both;
        }

        .pulse-glow {
          animation: pulseGlow 1.6s ease-in-out infinite;
        }
      `}</style>

      <main className="mx-auto flex min-h-screen w-full max-w-[1180px] flex-col justify-center px-4 py-8 md:px-8">
        <header className="float-in mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-secondary">
              <span className="material-symbols-outlined text-base">auto_awesome</span>
              <span>Reading textbook graph</span>
            </div>
            <h1 className="font-hanken text-3xl font-extrabold text-on-background md:text-5xl">
              Building your curriculum for {query.onboarding.topic}
            </h1>
            <p className="mt-4 text-sm leading-6 text-on-surface-variant md:text-base">
              The planner is scanning matched sections, prerequisite links, and concept coverage before arranging the module sequence. The LLM planning call may take a little while.
            </p>
          </div>
          <Link
            href="/onboard"
            className="self-start rounded-xl border border-outline-variant bg-white px-5 py-3 font-hanken text-sm font-bold text-on-surface-variant shadow-sm hover:bg-surface-container-low md:self-auto"
          >
            Edit Query
          </Link>
        </header>

        <section className="float-in rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm md:p-7">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="font-hanken text-xl font-bold text-on-background">Live Reading Pass</h2>
              <p className="mt-1 text-sm text-on-surface-variant">
                {sectionCount(planningPacket)} sections selected for planning
                {visibleConcepts.length > 0 ? `, with ${visibleConcepts.length} prerequisite concept bridges.` : "."}
              </p>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full bg-secondary-container px-4 py-2 text-xs font-bold text-on-secondary-container">
              <span className="h-2 w-2 rounded-full bg-secondary pulse-glow" />
                {phase === "done" ? "Plan ready" : phase === "planning" ? "Calling planner" : "Reading context"}
            </span>
          </div>

          <div className="relative overflow-hidden py-3">
            <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-12 bg-gradient-to-r from-surface-container-lowest to-transparent" />
            <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-12 bg-gradient-to-l from-surface-container-lowest to-transparent" />
            {readingItems.length > 0 ? (
              <div className="flex flex-wrap gap-4">
                {readingItems.map((item, index) => (
                  <article
                    key={`${item.id}:${index}`}
                    className="h-[178px] w-[280px] rounded-xl border border-outline-variant bg-white p-4 shadow-sm md:w-[340px]"
                  >
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="flex items-center gap-2 rounded-full bg-surface-container-low px-3 py-1 text-[11px] font-bold text-secondary">
                        <span className="material-symbols-outlined text-sm">{item.icon}</span>
                        {item.role}
                      </span>
                      <span className="max-w-[130px] truncate font-mono text-[10px] text-outline">{item.id}</span>
                    </div>
                    <h3 className="line-clamp-2 font-hanken text-base font-bold text-on-background">{item.title}</h3>
                    <p className="mt-2 line-clamp-3 text-xs leading-5 text-on-surface-variant">{item.summary}</p>
                  </article>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-outline-variant bg-white p-6 text-center text-sm text-on-surface-variant">
                No matching sections were found for this query.
              </div>
            )}
          </div>

          {visibleConcepts.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {visibleConcepts.map((label, index) => (
                <span
                  key={`${label}:${index}`}
                  className="rounded-full border border-outline-variant bg-surface-container-low px-3 py-1 text-xs font-semibold text-on-surface-variant"
                >
                  {label}
                </span>
              ))}
            </div>
          )}
        </section>

        <section className="float-in mt-6 grid gap-4 md:grid-cols-3">
          {planningSteps.map((step, index) => (
            <div
              key={step.label}
              className={`rounded-xl border p-4 shadow-sm transition-all ${
                index <= activeStep
                  ? "border-secondary bg-surface-container-lowest"
                  : "border-outline-variant bg-surface-container-low text-on-surface-variant"
              }`}
            >
              <div className="mb-3 flex items-center gap-2">
                <span className={`material-symbols-outlined text-lg ${index <= activeStep ? "text-secondary" : "text-outline"}`}>
                  {step.icon}
                </span>
                <h3 className="font-hanken text-sm font-bold">{step.label}</h3>
              </div>
              <p className="text-xs leading-5 text-on-surface-variant">{step.body}</p>
            </div>
          ))}
        </section>

        <section className="float-in mt-8 rounded-2xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between text-xs font-bold uppercase tracking-wider text-on-surface-variant">
            <span>{phase === "done" ? "Opening plan" : phase === "planning" ? "Waiting for curriculum planner" : "Generating automatically"}</span>
            <span>{progressWidth}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-surface-container">
            <div
              className="h-full rounded-full bg-secondary transition-all duration-500 ease-out"
              style={{ width: `${progressWidth}%` }}
            />
          </div>
        </section>
      </main>
    </div>
  );
}

const planningSteps = [
  {
    label: "Read matched sections",
    body: "Scanning target sections and summaries selected by retrieval.",
    icon: "chrome_reader_mode",
  },
  {
    label: "Trace relationships",
    body: "Following prerequisite, support, reinforcement, and next-step links.",
    icon: "account_tree",
  },
  {
    label: "Order modules",
    body: "Calling the planner to arrange a compact learning sequence.",
    icon: "route",
  },
];

function buildReadingItems(packet: CurriculumPlanningPacket): ReadingItem[] {
  return packet.main_path_section_ids
    .map((sectionId) => packet.sections_by_id[sectionId])
    .filter((section): section is PlanningPacketSection => Boolean(section))
    .map((section) => itemFromPlanningSection(section));
}

function itemFromPlanningSection(section: PlanningPacketSection): ReadingItem {
  const role = section.role === "prerequisite" ? "Prerequisite" : "Target";
  return {
    id: section.section_id,
    title: section.title,
    summary: section.summary,
    role,
    icon: role === "Prerequisite" ? "foundation" : "my_location",
  };
}

function sectionCount(packet: CurriculumPlanningPacket): number {
  return packet.main_path_section_ids.length;
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError || err instanceof Error) return err.message;
  return fallback;
}
