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

interface TraceStep {
  type: "info" | "section" | "concept" | "relationship";
  text: string;
  meta?: {
    role?: string;
    summary?: string;
    reason?: string;
  };
}

type ReadingItem = {
  id: string;
  title: string;
  summary: string;
  role: "Target" | "Prerequisite";
  icon: string;
};

export default function OnboardPreviewPage() {
  const router = useRouter();
  const generationStarted = useRef(false);
  const progressTimer = useRef<number | null>(null);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  const [previewData, setPreviewData] = useState<RetrievalPreviewResponse | null>(null);
  const [query, setQuery] = useState<CurriculumQueryPayload | null>(null);
  const [phase, setPhase] = useState<GenerationPhase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [planAttemptCount, setPlanAttemptCount] = useState(0);

  // Streaming Trace State
  const [traceSteps, setTraceSteps] = useState<TraceStep[]>([]);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [plannerTick, setPlannerTick] = useState(0);

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
        
        // Generate the trace steps sequence from actual retrieval data
        const generatedSteps = generateTraceSteps(parsedPreview.planning_packet);
        setTraceSteps(generatedSteps);
        
        setPhase("reading");
      }, 0);
    } catch {
      window.setTimeout(() => {
        setError("Failed to load retrieval preview details.");
        setPhase("error");
      }, 0);
    }
  }, []);

  // Streaming Log Ticker
  useEffect(() => {
    if (phase === "loading" || phase === "error" || traceSteps.length === 0) return;
    if (currentStepIndex >= traceSteps.length - 1) return;

    const timer = window.setInterval(() => {
      setCurrentStepIndex((prev) => {
        if (prev >= traceSteps.length - 1) {
          window.clearInterval(timer);
          return prev;
        }
        return prev + 1;
      });
    }, 850);

    return () => window.clearInterval(timer);
  }, [phase, traceSteps, currentStepIndex]);

  // Slowly tick up progress bar once trace completes and LLM call is running
  useEffect(() => {
    if (phase !== "planning" || currentStepIndex < traceSteps.length - 1) return;
    const interval = window.setInterval(() => {
      setPlannerTick((t) => t + 1);
    }, 1000);
    return () => window.clearInterval(interval);
  }, [phase, currentStepIndex, traceSteps]);

  // Auto-scroll terminal log into view
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [currentStepIndex]);

  const generatePlan = useCallback(async () => {
    if (!query || !previewData || generationStarted.current) return;
    generationStarted.current = true;
    setPhase("planning");
    setError(null);
    setPlanAttemptCount((current) => current + 1);

    try {
      const plan = await createCurriculumPlan(query);
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
      generationStarted.current = false;
      setPhase("error");
      setError(errorMessage(err, "Failed to generate curriculum. Please check backend connections."));
    }
  }, [previewData, query, router]);

  // Trigger actual planning call immediately when matching context loads
  useEffect(() => {
    if (previewData && query && phase === "reading" && !generationStarted.current) {
      void generatePlan();
    }
  }, [previewData, query, phase, generatePlan]);

  // Dynamically calculate active navigation step
  const activeStep = useMemo(() => {
    if (traceSteps.length === 0) return 0;
    if (phase === "planning" && currentStepIndex >= traceSteps.length - 1) return 2;
    
    const half = Math.floor(traceSteps.length / 2);
    if (currentStepIndex < half) return 0;
    return 1;
  }, [currentStepIndex, traceSteps, phase]);

  // Dynamically calculate loading progress width
  const progressWidth = useMemo(() => {
    if (phase === "done") return 100;
    if (traceSteps.length === 0) return 8;

    if (currentStepIndex < traceSteps.length - 1) {
      const fraction = (currentStepIndex + 1) / traceSteps.length;
      return Math.round(8 + fraction * 52); // Streams from 8% to 60%
    }

    return Math.min(95, 60 + plannerTick * 2); // Slow tick from 60% to 95%
  }, [currentStepIndex, traceSteps, phase, plannerTick]);

  if (phase === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="text-center">
          <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent" />
          <p className="mt-4 text-xs text-zinc-400 font-light">Loading retrieval context...</p>
        </div>
      </div>
    );
  }

  if (phase === "error" || !previewData || !query) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white px-4">
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

  return (
    <div className="min-h-screen bg-white font-sans text-zinc-900 selection:bg-zinc-100 selection:text-zinc-950">
      {/* Navigation Header */}
      <header className="w-full max-w-4xl mx-auto px-6 h-14 flex items-center justify-between border-b border-zinc-300">
        <div className="flex items-center gap-3">
          <Link href="/onboard" className="text-zinc-500 hover:text-zinc-900 transition-colors text-sm font-medium">
            &larr; Back
          </Link>
          <span className="text-zinc-200">|</span>
          <span className="text-sm font-semibold tracking-tight text-zinc-900 truncate max-w-[200px] md:max-w-md">
            {query.onboarding.topic}
          </span>
        </div>
        <Link
          href="/onboard"
          className="text-xs font-medium text-zinc-500 hover:text-zinc-950 transition-colors border border-zinc-300 rounded-full px-4 py-1.5 hover:border-zinc-950"
        >
          Edit Query
        </Link>
      </header>

      <style>{`
        @keyframes floatIn {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulseGlow {
          0%, 100% { opacity: 0.45; transform: scale(0.98); }
          50% { opacity: 1; transform: scale(1); }
        }
        .float-in {
          animation: floatIn 0.7s ease-out both;
        }
        .pulse-glow {
          animation: pulseGlow 1.6s ease-in-out infinite;
        }
      `}</style>

      {/* Main Content */}
      <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-10 gap-8">
        <header className="float-in flex flex-col gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-500">
            <span className="material-symbols-outlined text-sm">auto_awesome</span>
            <span>Traversing textbook graph</span>
          </div>
          <h1 className="text-2xl font-light tracking-tight text-zinc-950 leading-tight">
            Building curriculum for {query.onboarding.topic}
          </h1>
          <p className="text-xs text-zinc-500 leading-normal font-light">
            Analyzing target topics, scanning matched sections, and mapping prerequisite concept bridges.
          </p>
        </header>

        {/* Streaming Reasoning Trace Console */}
        <section className="float-in border-t border-zinc-300 pt-8 flex flex-col gap-4">
          <div className="flex flex-col border border-zinc-300 rounded-xl bg-zinc-50 overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-300 bg-white px-4 py-2.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-650">Reasoning Trace</span>
              <span className="inline-flex items-center gap-1 text-[9px] text-zinc-500 font-mono">
                <span className="h-1.5 w-1.5 rounded-full bg-zinc-900 pulse-glow" />
                {phase === "done" ? "completed" : "active"}
              </span>
            </div>
            <div className="h-[380px] overflow-y-auto p-5 flex flex-col gap-4 font-sans text-xs">
              {traceSteps.slice(0, currentStepIndex + 1).map((step, idx) => {
                if (step.type === "info") {
                  return (
                    <div key={idx} className="text-zinc-500 italic py-1 font-light">
                      {step.text}
                    </div>
                  );
                }
                if (step.type === "section") {
                  return (
                    <div key={idx} className="flex flex-col gap-1.5 border-b border-zinc-200 pb-3">
                      <div className="flex items-start gap-2 text-zinc-900 font-medium">
                        <span className="material-symbols-outlined text-sm mt-0.5">import_contacts</span>
                        <span>
                          <span className="text-[9px] uppercase tracking-wider text-zinc-400 mr-2 font-mono">[{step.meta?.role}]</span>
                          {step.text}
                        </span>
                      </div>
                      {step.meta?.summary && (
                        <p className="text-zinc-600 font-light leading-relaxed pl-6 text-xs">
                          {step.meta.summary}
                        </p>
                      )}
                    </div>
                  );
                }
                if (step.type === "relationship") {
                  return (
                    <div key={idx} className="flex items-center gap-2 text-zinc-700 py-1 font-light">
                      <span className="material-symbols-outlined text-xs text-zinc-400">link</span>
                      <span>{step.text}</span>
                    </div>
                  );
                }
                if (step.type === "concept") {
                  return (
                    <div key={idx} className="flex flex-col gap-1.5 bg-white border border-zinc-200 rounded-lg p-3">
                      <div className="flex items-center gap-1.5 text-zinc-900 font-medium">
                        <span className="material-symbols-outlined text-sm text-zinc-900">psychology</span>
                        <span>{step.text}</span>
                      </div>
                      {step.meta?.reason && (
                        <p className="text-zinc-500 font-light text-[11px] leading-normal pl-5">
                          Evidence: {step.meta.reason}
                        </p>
                      )}
                    </div>
                  );
                }
                return null;
              })}
              <div ref={terminalEndRef} />
            </div>
          </div>
        </section>

        {/* Planning Steps Navigation */}
        <section className="float-in mt-2 grid gap-4 md:grid-cols-3 border-t border-zinc-300 pt-8">
          {planningSteps.map((step, index) => {
            const isActive = index <= activeStep;
            return (
              <div
                key={step.label}
                className={`rounded-xl border p-4 transition-colors ${
                  isActive
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-300 bg-white text-zinc-500"
                }`}
              >
                <div className="mb-2 flex items-center gap-2">
                  <span className={`material-symbols-outlined text-sm ${isActive ? "text-white" : "text-zinc-550"}`}>
                    {step.icon}
                  </span>
                  <h3 className="text-xs font-semibold uppercase tracking-wider">{step.label}</h3>
                </div>
                <p className={`text-xs leading-normal font-light ${isActive ? "text-zinc-300" : "text-zinc-550"}`}>
                  {step.body}
                </p>
              </div>
            );
          })}
        </section>

        {/* Progress Bar */}
        <section className="float-in border-t border-zinc-300 pt-6">
          <div className="mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
            <span>{phase === "done" ? "Opening plan" : phase === "planning" ? "Structuring modules" : "Analyzing textbook graph"}</span>
            <span>{progressWidth}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-zinc-50 border border-zinc-300">
            <div
              className="h-full rounded-full bg-zinc-900 transition-all duration-500 ease-out"
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

// Trace Generator Function
function generateTraceSteps(packet: CurriculumPlanningPacket): TraceStep[] {
  const steps: TraceStep[] = [];

  steps.push({
    type: "info",
    text: `Initializing textbook graph traversal for "${packet.onboarding.topic}"...`,
  });

  const mainSections = packet.main_path_section_ids
    .map((id) => packet.sections_by_id[id])
    .filter((s): s is PlanningPacketSection => Boolean(s));

  mainSections.forEach((section) => {
    const roleLabel = section.role === "prerequisite" ? "Prerequisite" : "Target";
    steps.push({
      type: "section",
      text: `Reading: "${section.title}"`,
      meta: {
        role: roleLabel,
        summary: section.summary,
      },
    });
  });

  const hardDeps = packet.relationships?.hard_dependencies || [];
  if (hardDeps.length > 0) {
    steps.push({
      type: "info",
      text: "Tracing prerequisite dependencies between concepts and sections...",
    });

    hardDeps.forEach((dep) => {
      const fromSec = packet.sections_by_id[dep.from_section_id || ""];
      const toSec = packet.sections_by_id[dep.to_section_id || ""];
      const concept = dep.bridge_concept_id?.replace("concept:", "").replaceAll("_", " ");

      if (fromSec && toSec) {
        steps.push({
          type: "relationship",
          text: `Link: section "${fromSec.title}" provides prerequisites for "${toSec.title}"`,
        });
      }

      if (concept) {
        steps.push({
          type: "concept",
          text: `Extracted concept bridge: "${concept}"`,
          meta: {
            reason: dep.evidence_reason || "Identified as a critical learning step.",
          },
        });
      }
    });
  }

  steps.push({
    type: "info",
    text: "Context compilation complete. Structuring module sequence...",
  });

  return steps;
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError || err instanceof Error) return err.message;
  return fallback;
}
