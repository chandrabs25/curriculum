"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { designModule } from "../../services/api";
import { writeCachedModuleDesign } from "../../services/moduleDesignCache";
import { readLatestSectionInsights } from "../../services/sectionInsights";
import { CurriculumPlanPayload, PlannedModulePayload } from "../../types/curriculum";

export default function PlanDashboardPage() {
  const params = useParams();
  const rawId = params.id as string;
  const id = decodeURIComponent(rawId);

  const [plan, setPlan] = useState<CurriculumPlanPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Track completed module IDs locally
  const [completedModuleIds, setCompletedModuleIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [moduleInsightCounts, setModuleInsightCounts] = useState<Record<string, number>>({});
  const [regeneratingModuleIds, setRegeneratingModuleIds] = useState<Record<string, boolean>>({});
  const [regeneratedModuleIds, setRegeneratedModuleIds] = useState<Record<string, boolean>>({});
  const [regenerationError, setRegenerationError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const loadTimer = window.setTimeout(() => {
      const storedPlan =
        localStorage.getItem(`curriculum-plan-${id}`) ||
        localStorage.getItem(`curriculum-plan-${rawId}`) ||
        matchingCurrentPlan(id, rawId);
      if (storedPlan) {
        try {
          const parsedPlan = JSON.parse(storedPlan) as CurriculumPlanPayload;
          const serializedPlan = JSON.stringify(parsedPlan);
          localStorage.setItem(`curriculum-plan-${parsedPlan.curriculum_plan_id}`, serializedPlan);
          localStorage.setItem(`curriculum-plan-${encodeURIComponent(parsedPlan.curriculum_plan_id)}`, serializedPlan);
          setPlan(parsedPlan);
          setModuleInsightCounts(moduleInsightCountsForPlan(parsedPlan));
          
          // Check localStorage to find which modules have finished quizzes
          const completed: string[] = [];
          parsedPlan.modules.forEach((m) => {
            const quizScoreKey = `curriculum-checkpoint-score-${id}-${m.module_id}`;
            if (localStorage.getItem(quizScoreKey) !== null) {
              completed.push(m.module_id);
            }
          });
          setCompletedModuleIds(completed);
        } catch {
          setError("Failed to parse the saved curriculum plan.");
        }
      } else {
        setError("Curriculum plan not found. Please create a new one.");
      }
    }, 0);

    return () => window.clearTimeout(loadTimer);
  }, [id, rawId]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white px-4">
        <div className="max-w-md w-full text-center bg-white p-8 rounded-xl border border-zinc-300">
          <h2 className="text-lg font-medium text-red-600">Error</h2>
          <p className="mt-2 text-zinc-500 text-xs font-light">{error}</p>
          <Link
            href="/onboard"
            className="mt-6 inline-flex items-center justify-center rounded-full bg-zinc-900 px-6 py-2.5 text-xs font-medium text-white transition-colors hover:bg-zinc-800"
          >
            Go to Onboarding
          </Link>
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="text-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent mx-auto"></div>
          <p className="mt-4 text-xs text-zinc-400 font-light">Loading plan dashboard...</p>
        </div>
      </div>
    );
  }

  // Chronological sort
  const sortedModules = [...plan.modules].sort((a, b) => a.position - b.position);

  // Compute active module: The first module in sequence that is NOT completed
  const activeModule = sortedModules.find((m) => !completedModuleIds.includes(m.module_id)) || sortedModules[sortedModules.length - 1];
  const activeModuleId = activeModule?.module_id || "";

  // Progress percentage
  const progressPercentage = sortedModules.length > 0
    ? Math.round((completedModuleIds.length / sortedModules.length) * 100)
    : 0;

  // Filter modules based on search
  const displayedModules = sortedModules.filter((m) =>
    m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.module_goal.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const labels = buildPlanLabelResolver(plan);
  const planDetails = planDetailRows(plan);

  const handleRegenerateWithInsights = async (module: PlannedModulePayload) => {
    const sectionInsights = readLatestSectionInsights(plan.learner_id, module.source_section_ids);
    if (sectionInsights.length === 0) {
      setModuleInsightCounts(moduleInsightCountsForPlan(plan));
      return;
    }

    setRegenerationError(null);
    setRegeneratingModuleIds((current) => ({ ...current, [module.module_id]: true }));
    try {
      const moduleDesign = await designModule({
        plan,
        module_id: module.module_id,
        learner_state: [],
        section_insights: sectionInsights,
      });
      writeCachedModuleDesign(plan.curriculum_plan_id, module.module_id, moduleDesign);
      setRegeneratedModuleIds((current) => ({ ...current, [module.module_id]: true }));
    } catch (err: unknown) {
      setRegenerationError(errorMessage(err, "Failed to regenerate this module with learner insights."));
    } finally {
      setRegeneratingModuleIds((current) => ({ ...current, [module.module_id]: false }));
      setModuleInsightCounts(moduleInsightCountsForPlan(plan));
    }
  };

  return (
    <div className="bg-white text-zinc-900 min-h-screen flex flex-col font-sans selection:bg-zinc-100 selection:text-zinc-950">
      {/* Navigation Header */}
      <header className="w-full max-w-6xl mx-auto px-6 h-14 flex items-center justify-between border-b border-zinc-300">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-zinc-500 hover:text-zinc-900 transition-colors text-sm font-medium">
            &larr; Home
          </Link>
          <span className="text-zinc-300">|</span>
          <span className="text-sm font-semibold tracking-tight text-zinc-900">
            Curriculum Detail
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="relative hidden md:block">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search modules..."
              className="bg-zinc-55 border border-zinc-300 rounded-full px-4 py-1 text-xs w-48 focus:border-zinc-950 outline-none placeholder:text-zinc-400 font-light"
            />
          </div>
          <Link
            href="/onboard"
            className="text-xs font-medium text-zinc-500 hover:text-zinc-950 transition-colors border border-zinc-300 rounded-full px-4 py-1.5 hover:border-zinc-955"
          >
            New Plan
          </Link>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex flex-col md:flex-row max-w-6xl w-full mx-auto flex-1 py-10 px-6 gap-12 overflow-y-auto md:overflow-hidden">
        {/* Timeline roadmap view */}
        <main className="flex-1 flex flex-col gap-10 overflow-y-auto custom-scrollbar pr-0 md:pr-4">
          {/* Summary Banner Card */}
          <section className="flex flex-col gap-6 border-b border-zinc-300 pb-8">
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                  Curriculum Plan
                </span>
                <h1 className="text-3xl font-light tracking-tight text-zinc-950 leading-tight mt-1">
                  {plan.onboarding.topic}
                </h1>
                {cleanText(plan.onboarding.learning_goal) && (
                  <p className="mt-2 text-sm text-zinc-500 leading-normal font-light">
                    Goal: {plan.onboarding.learning_goal}
                  </p>
                )}
              </div>
              
              <div className="flex flex-col items-start sm:items-end gap-1.5 shrink-0">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                  Progress
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-light text-zinc-950 leading-none">
                    {progressPercentage}%
                  </span>
                  <div className="w-24 h-1.5 bg-zinc-50 border border-zinc-300 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-zinc-900 rounded-full transition-all duration-1000 ease-out"
                      style={{ width: `${progressPercentage}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Preferences breakdown */}
            {planDetails.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6 border-t border-zinc-200">
                {planDetails.map((detail) => (
                  <div key={detail.label}>
                    <p className="text-[9px] text-zinc-400 uppercase font-medium tracking-wider mb-0.5">{detail.label}</p>
                    <p className="text-xs font-normal text-zinc-700">{detail.value}</p>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Chronological Timeline list */}
          <section className="flex flex-col gap-8">
            {regenerationError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 text-xs font-medium">
                {regenerationError}
              </div>
            )}
            
            <div className="flex flex-col gap-10">
              {displayedModules.map((module, idx) => {
                const isCompleted = completedModuleIds.includes(module.module_id);
                const isActive = module.module_id === activeModuleId;

                return (
                  <div key={module.module_id} className="flex flex-col md:flex-row gap-4 md:gap-8 border-b border-zinc-200 pb-10 last:border-b-0">
                    {/* Metadata Column */}
                    <div className="w-full md:w-36 shrink-0 flex flex-row md:flex-col md:items-start justify-between md:justify-start gap-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                        Module {String(idx + 1).padStart(2, "0")}
                      </span>
                      <span className={`inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider mt-1 px-2.5 py-0.5 rounded-full border ${
                        isCompleted
                          ? "border-zinc-200 bg-zinc-50 text-zinc-500"
                          : isActive
                            ? "border-zinc-950 bg-zinc-950 text-white animate-pulse"
                            : "border-zinc-300 bg-white text-zinc-500"
                      }`}>
                        {isCompleted ? "Completed" : isActive ? "Active" : "Upcoming"}
                      </span>
                    </div>

                    {/* Module details */}
                    <div className="flex-1 flex flex-col gap-4">
                      <div>
                        <h3 className="text-lg font-normal text-zinc-950 leading-tight">
                          {module.title}
                        </h3>
                        <p className="mt-2.5 text-sm text-zinc-650 leading-relaxed font-light">
                          {module.module_goal}
                        </p>
                      </div>

                      {/* Concepts Covered */}
                      {module.covered_concept_ids && module.covered_concept_ids.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {module.covered_concept_ids.map((concept) => (
                            <span
                              key={concept}
                              className="px-2.5 py-0.5 rounded-full border border-zinc-200 bg-zinc-50 text-[10px] font-medium text-zinc-600"
                            >
                              {labels.conceptLabel(concept)}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Prerequisite Alert warning */}
                      {module.prerequisite_warnings && module.prerequisite_warnings.length > 0 && (
                        <div className="p-3 rounded-lg border border-amber-200 bg-amber-50 text-[11px] text-amber-800 leading-normal font-light flex items-start gap-1.5">
                          <span className="material-symbols-outlined text-sm mt-0.5">warning</span>
                          <span>{labels.renderRelationshipText(module.prerequisite_warnings[0])}</span>
                        </div>
                      )}

                      {/* Footer Actions */}
                      <div className="flex items-center justify-between border-t border-zinc-200 pt-4 mt-2">
                        {idx < sortedModules.length - 1 ? (
                          <span className="text-[11px] text-zinc-400 font-light">
                            Next &rarr; {sortedModules[idx + 1].title}
                          </span>
                        ) : (
                          <span className="text-[11px] text-zinc-400 font-light">
                            End of curriculum
                          </span>
                        )}

                        <div className="flex items-center gap-3">
                          {/* Regenerate Button */}
                          {(moduleInsightCounts[module.module_id] || 0) > 0 && (
                            <button
                              type="button"
                              onClick={() => void handleRegenerateWithInsights(module)}
                              disabled={Boolean(regeneratingModuleIds[module.module_id])}
                              className="text-[11px] font-medium border border-zinc-300 rounded-full px-4 py-1.5 text-zinc-650 hover:border-zinc-950 hover:text-zinc-955 hover:bg-zinc-50 transition-colors disabled:opacity-50 disabled:cursor-wait"
                            >
                              {regeneratingModuleIds[module.module_id]
                                ? "Regenerating..."
                                : regeneratedModuleIds[module.module_id]
                                  ? "Personalized ✓"
                                  : `Personalize (${moduleInsightCounts[module.module_id]} insights)`}
                            </button>
                          )}

                          {isCompleted ? (
                            <Link
                              href={moduleHref(plan.curriculum_plan_id, module.module_id)}
                              className="text-xs font-semibold text-zinc-900 hover:text-zinc-600 transition-colors inline-flex items-center gap-0.5"
                            >
                              Review &rarr;
                            </Link>
                          ) : (
                            <Link
                              href={moduleHref(plan.curriculum_plan_id, module.module_id)}
                              className="bg-zinc-900 text-white rounded-full px-5 py-2 text-xs font-semibold hover:bg-zinc-800 transition-colors"
                            >
                              {isActive ? "Start Studying" : "Open Module"}
                            </Link>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </main>

        {/* Right Sidebar: Real graph-backed recommendations (Desktop Only) */}
        <aside className="hidden md:flex flex-col w-80 shrink-0 border-l border-zinc-300 pl-8 overflow-y-auto custom-scrollbar gap-6">
          {activeModule && (
            <div className="flex flex-col gap-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
                <span className="material-symbols-outlined text-sm">auto_stories</span>
                Active Module
              </h4>
              <div className="p-4 rounded-xl border border-zinc-300 bg-zinc-50 flex flex-col gap-2">
                <p className="text-sm font-medium text-zinc-900 leading-tight">{activeModule.title}</p>
                <p className="text-xs text-zinc-505 leading-normal font-light">{activeModule.module_goal}</p>
                {activeModule.source_section_ids.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-zinc-200">
                    <p className="text-[9px] text-zinc-400 uppercase font-medium tracking-wider mb-2">Source sections</p>
                    <ul className="flex flex-col gap-1.5">
                      {activeModule.source_section_ids.map((sectionId) => (
                        <li key={sectionId} className="text-xs text-zinc-700 font-light">
                          {labels.sectionLabel(sectionId)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          <PlanSectionList
            title="Helpful Alongside This"
            icon="recommend"
            sectionIds={activeModule?.parallel_support_section_ids || []}
            labels={labels}
          />
          <PlanSectionList
            title="Reinforce With"
            icon="fitness_center"
            sectionIds={activeModule?.reinforcement_section_ids || []}
            labels={labels}
          />
          <PlanSectionList
            title="After This"
            icon="trending_flat"
            sectionIds={activeModule?.next_step_section_ids || []}
            labels={labels}
          />

          <div className="mt-auto p-4 bg-zinc-50 rounded-xl border border-zinc-300 flex flex-col gap-2">
            <p className="text-[9px] text-zinc-400 uppercase font-medium tracking-wider">Plan Summary</p>
            <p className="text-xs text-zinc-700 leading-normal font-light">
              {sortedModules.length} modules
              {totalCheckpointCount(plan) > 0 ? ` with ${totalCheckpointCount(plan)} quiz questions` : ""}.
            </p>
            {activeModule && (
              <Link
                href={moduleHref(plan.curriculum_plan_id, activeModuleId)}
                className="w-full py-2 bg-white text-zinc-900 border border-zinc-300 rounded-lg text-xs font-semibold text-center block hover:border-zinc-900 hover:bg-zinc-50 transition-all mt-1"
              >
                Open Active Module
              </Link>
            )}
          </div>
        </aside>
      </div>

      {/* Bottom Nav Bar (Mobile Only) */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full flex justify-around items-center py-3 bg-white border-t border-zinc-300 z-50">
        <Link
          href="/"
          className="flex flex-col items-center justify-center text-zinc-400 hover:text-zinc-900 transition-colors"
        >
          <span className="material-symbols-outlined text-xl">home</span>
          <span className="text-[9px] font-medium mt-0.5">Home</span>
        </Link>
        <span className="flex flex-col items-center justify-center text-zinc-950 font-semibold">
          <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
            menu_book
          </span>
          <span className="text-[9px] mt-0.5">My Plan</span>
        </span>
        {activeModule && (
          <Link
            href={moduleHref(plan.curriculum_plan_id, activeModuleId)}
            className="flex flex-col items-center justify-center text-zinc-400 hover:text-zinc-900 transition-colors"
          >
            <span className="material-symbols-outlined text-xl">school</span>
            <span className="text-[9px] font-medium mt-0.5">Learning</span>
          </Link>
        )}
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

function PlanSectionList({
  title,
  icon,
  sectionIds,
  labels,
}: {
  title: string;
  icon: string;
  sectionIds: string[];
  labels: ReturnType<typeof buildPlanLabelResolver>;
}) {
  if (sectionIds.length === 0) return null;

  return (
    <div className="pt-6 border-t border-zinc-300">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-1.5">
        <span className="material-symbols-outlined text-sm">{icon}</span>
        {title}
      </h4>
      <ul className="flex flex-col gap-2">
        {sectionIds.map((sectionId) => (
          <li key={sectionId} className="p-3 rounded-xl border border-zinc-300 bg-white">
            <p className="text-xs font-normal text-zinc-900 leading-snug">
              {labels.sectionLabel(sectionId)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function totalCheckpointCount(plan: CurriculumPlanPayload): number {
  return Object.values(plan.mcq_allocation || {}).reduce((total, count) => total + Number(count || 0), 0);
}

function planDetailRows(plan: CurriculumPlanPayload): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];
  const subject = cleanText(plan.onboarding.subject);
  const grade = cleanText(plan.metadata?.grade);
  const pace = cleanText(plan.onboarding.deadline_or_pace);
  const learningStyle = cleanText(plan.onboarding.preferred_learning_style);
  const availableTime = cleanText(plan.onboarding.available_time);
  const checkpointCount = totalCheckpointCount(plan);

  if (subject) rows.push({ label: "Subject", value: subject });
  if (grade) rows.push({ label: "Grade", value: `Grade ${grade}` });
  if (pace) rows.push({ label: "Pace", value: pace });
  if (learningStyle) rows.push({ label: "Learning Style", value: learningStyle.replace(/[-_]+/g, " ") });
  if (availableTime) rows.push({ label: "Available Time", value: availableTime });
  rows.push({ label: "Modules", value: String(plan.modules.length) });
  if (checkpointCount > 0) rows.push({ label: "Checkpoint Questions", value: String(checkpointCount) });

  return rows;
}

function cleanText(value: unknown): string {
  if (typeof value !== "string" && typeof value !== "number") return "";
  const text = String(value).trim();
  if (!text || ["n/a", "na", "none", "null", "undefined", "general"].includes(text.toLowerCase())) {
    return "";
  }
  return text;
}

function moduleInsightCountsForPlan(plan: CurriculumPlanPayload): Record<string, number> {
  return Object.fromEntries(
    plan.modules.map((module) => [
      module.module_id,
      readLatestSectionInsights(plan.learner_id, module.source_section_ids).length,
    ])
  );
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message;
  return fallback;
}

function buildPlanLabelResolver(plan: CurriculumPlanPayload) {
  const sectionLabels = new Map<string, string>();
  const conceptLabels = new Map<string, string>();

  const packetSections = plan.metadata?.planning_packet?.sections_by_id || {};
  for (const [sectionId, section] of Object.entries(packetSections)) {
    const label = section.title?.trim();
    if (label) {
      sectionLabels.set(sectionId, label);
    }
  }

  const learningPath = plan.metadata?.learning_path_context;
  const sectionRows = [
    ...(learningPath?.main_path_sections || []),
    ...(learningPath?.target_sections || []),
    ...(learningPath?.prerequisite_sections || []),
    ...(learningPath?.support_sections || []),
  ];
  for (const section of sectionRows) {
    const sectionId = section.section_id?.trim();
    const label = section.title?.trim();
    if (sectionId && label) {
      sectionLabels.set(sectionId, label);
    }
  }

  const conceptRows = [
    ...(learningPath?.required_concepts || []),
    ...(learningPath?.taught_concepts || []),
    ...((learningPath?.main_path_sections || []).flatMap((section) => [
      ...(section.teaches || []),
      ...(section.requires || []),
    ])),
    ...((learningPath?.target_sections || []).flatMap((section) => [
      ...(section.teaches || []),
      ...(section.requires || []),
    ])),
    ...((learningPath?.prerequisite_sections || []).flatMap((section) => [
      ...(section.teaches || []),
      ...(section.requires || []),
    ])),
  ];

  for (const concept of conceptRows) {
    const conceptId = concept.concept_id?.trim();
    const label = concept.label?.trim();
    if (conceptId && label && label !== conceptId) {
      conceptLabels.set(conceptId, label);
    }
  }

  const replacementLabels = new Map<string, string>([
    ...sectionLabels,
    ...conceptLabels,
  ]);

  return {
    sectionLabel: (sectionId: string) => sectionLabels.get(sectionId) || readableId(sectionId),
    conceptLabel: (conceptId: string) => conceptLabels.get(conceptId) || readableId(conceptId),
    renderRelationshipText: (text: string) => replaceKnownIds(text, replacementLabels),
  };
}

function replaceKnownIds(text: string, labelsById: Map<string, string>): string {
  let rendered = text;
  const ids = [...labelsById.keys()].sort((a, b) => b.length - a.length);
  for (const id of ids) {
    rendered = rendered.replace(new RegExp(escapeRegExp(id), "g"), labelsById.get(id) || readableId(id));
  }
  return rendered
    .replace(/\bconcept:([a-zA-Z0-9_./-]+)/g, (_, value: string) => readableId(value))
    .replace(/\bncert:([a-zA-Z0-9_./:-]+)/g, (_, value: string) => readableSectionId(value));
}

function readableId(id: string): string {
  const rawTail = id.includes(":") ? id.split(":").at(-1) || id : id;
  return rawTail
    .replace(/^concept[:_-]?/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function readableSectionId(id: string): string {
  const rawTail = id.includes(":") ? id.split(":").at(-1) || id : id;
  return `section ${rawTail.replace(/[_-]+/g, " ").trim()}`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
