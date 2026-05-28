"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { designModule } from "../../../../services/api";
import { CurriculumPlanPayload } from "../../../../types/curriculum";

export default function ModuleReadingPage() {
  const params = useParams();
  const id = params.id as string;
  const moduleId = params.moduleId as string;

  const [plan, setPlan] = useState<CurriculumPlanPayload | null>(null);
  const [moduleData, setModuleData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completedCount, setCompletedCount] = useState(0);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedPlan = localStorage.getItem(`curriculum-plan-${id}`);
      
      Promise.resolve().then(() => {
        if (!storedPlan) {
          setError("Plan not found. Please regenerate onboarding.");
          setLoading(false);
          return;
        }

        try {
          const parsedPlan = JSON.parse(storedPlan) as CurriculumPlanPayload;
          setPlan(parsedPlan);

          // Calculate completed count
          const count = parsedPlan.modules.filter((m) => {
            return localStorage.getItem(`curriculum-checkpoint-score-${id}-${m.module_id}`) !== null;
          }).length;
          setCompletedCount(count);

          // Fetch designed module content from backend
          designModule({
            plan: parsedPlan,
            module_id: moduleId,
            learner_state: [],
          })
            .then((data) => {
              setModuleData(data);
            })
            .catch((err) => {
              console.error(err);
              setError(err.message || "Failed to load module details from API backend.");
            })
            .finally(() => {
              setLoading(false);
            });
        } catch (e) {
          setError("Invalid curriculum plan file format.");
          setLoading(false);
        }
      });
    }
  }, [id, moduleId]);

  if (loading) {
    return (
      <div className="fixed inset-0 z-[100] bg-surface flex flex-col items-center justify-center transition-opacity duration-500">
        <div className="relative w-48 h-1 bg-surface-container-highest overflow-hidden rounded-full mb-3">
          <div className="absolute inset-0 bg-secondary pulsing-bar h-full rounded-full"></div>
        </div>
        <p className="font-hanken font-bold text-xs text-primary tracking-widest uppercase animate-pulse">
          Synthesizing module content...
        </p>
      </div>
    );
  }

  if (error && !moduleData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="max-w-md w-full text-center bg-surface-container-lowest p-8 rounded-2xl border border-outline-variant shadow-md">
          <h2 className="text-2xl font-bold text-error">Error</h2>
          <p className="mt-2 text-on-surface-variant text-sm">{error}</p>
          <Link
            href={`/plan/${id}`}
            className="mt-6 inline-block px-6 py-2 bg-primary text-on-primary rounded-full hover:opacity-90 text-sm font-semibold shadow-sm"
          >
            Back to Plan
          </Link>
        </div>
      </div>
    );
  }

  // Find previous and next modules for navigation
  const sortedModules = plan ? [...plan.modules].sort((a, b) => a.position - b.position) : [];
  const currentIndex = sortedModules.findIndex((m) => m.module_id === moduleId);
  
  const prevModule = currentIndex > 0 ? sortedModules[currentIndex - 1] : null;
  const nextModule = currentIndex < sortedModules.length - 1 ? sortedModules[currentIndex + 1] : null;

  // Completed chapters computed in useEffect to avoid hydration mismatches
  
  const progressPercent = sortedModules.length > 0 
    ? Math.round((completedCount / sortedModules.length) * 100) 
    : 0;

  return (
    <div className="bg-background text-on-surface font-public overflow-hidden flex min-h-screen">
      
      {/* Side Navigation Bar (Desktop Only) */}
      <aside className="hidden md:flex flex-col h-screen py-6 bg-surface-container-low border-r border-outline-variant w-64 shrink-0 px-4">
        <div className="mb-8">
          <h2 className="font-hanken text-lg font-bold text-primary">Academic Portal</h2>
          <p className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold opacity-70">Modern Academic System</p>
        </div>
        
        <nav className="flex-1 space-y-1">
          <Link
            href="/"
            className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-variant transition-all rounded-lg group"
          >
            <span className="material-symbols-outlined group-hover:text-secondary">dashboard</span>
            <span className="font-hanken font-semibold text-sm">Dashboard</span>
          </Link>
          <Link
            href={`/plan/${id}`}
            className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-variant transition-all rounded-lg group"
          >
            <span className="material-symbols-outlined group-hover:text-secondary">map</span>
            <span className="font-hanken font-semibold text-sm">Curriculum Plan</span>
          </Link>
          <span className="flex items-center gap-3 px-3 py-2.5 text-secondary font-bold border-r-4 border-secondary bg-surface-container-high rounded-l-lg translate-x-1 transition-transform">
            <span className="material-symbols-outlined">auto_stories</span>
            <span className="font-hanken font-semibold text-sm">Active Module</span>
          </span>
        </nav>

        <div className="mt-auto space-y-3">
          <Link
            href="/onboard"
            className="w-full bg-primary text-on-primary font-hanken font-bold text-xs py-3 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            New Plan
          </Link>
          <div className="space-y-1 pt-6 border-t border-outline-variant">
            <a href="#" className="flex items-center text-on-surface-variant hover:bg-surface-variant py-2 px-2 rounded transition-all">
              <span className="material-symbols-outlined mr-3 text-[20px]">settings</span>
              <span className="font-hanken font-semibold text-xs">Settings</span>
            </a>
            <a href="#" className="flex items-center text-on-surface-variant hover:bg-surface-variant py-2 px-2 rounded transition-all">
              <span className="material-symbols-outlined mr-3 text-[20px]">help</span>
              <span className="font-hanken font-semibold text-xs">Support</span>
            </a>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-background overflow-hidden relative">
        
        {/* Top AppBar */}
        <header className="flex justify-between items-center w-full px-10 h-16 bg-surface border-b border-outline-variant shrink-0">
          <div className="flex items-center gap-4">
            <span className="text-headline-md font-hanken font-bold text-primary">AcademicFlow</span>
          </div>
          <div className="flex items-center gap-6">
            <div className="relative hidden sm:block">
              <input
                type="text"
                placeholder="Search lessons..."
                className="bg-surface-container-low border-none rounded-full px-4 py-1.5 text-xs w-64 focus:ring-2 focus:ring-secondary/20 transition-all outline-none"
              />
              <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-[20px] text-on-surface-variant">
                search
              </span>
            </div>
            
            <div className="flex items-center gap-4 text-primary">
              <button className="hover:text-secondary transition-colors relative cursor-pointer">
                <span className="material-symbols-outlined">notifications</span>
                <span className="absolute top-0 right-0 w-2 h-2 bg-error rounded-full"></span>
              </button>
              <button className="hover:text-secondary transition-colors cursor-pointer">
                <span className="material-symbols-outlined">account_circle</span>
              </button>
            </div>
          </div>
        </header>

        {/* Scrollable Container */}
        <div className="flex-1 overflow-y-auto px-4 md:px-10 py-6 custom-scrollbar">
          <div className="max-w-[1280px] mx-auto pb-24">
            
            {/* Breadcrumbs & Progress Indicator */}
            <nav className="flex items-center gap-2 mb-6">
              <span className="text-xs text-on-surface-variant font-semibold">{plan?.onboarding.topic}</span>
              <span className="material-symbols-outlined text-[14px] text-outline">chevron_right</span>
              <span className="text-xs text-secondary font-semibold">{moduleData.title}</span>
              
              <div className="ml-auto flex items-center gap-3 shrink-0">
                <span className="text-xs text-on-surface-variant font-semibold">{progressPercent}% Complete</span>
                <div className="w-24 h-2 bg-surface-container-high rounded-full overflow-hidden">
                  <div
                    className="h-full bg-secondary rounded-full transition-all duration-1000"
                    style={{ width: `${progressPercent}%` }}
                  ></div>
                </div>
              </div>
            </nav>

            {/* Module Title Header */}
            <div className="mb-8 border-b border-outline-variant pb-6">
              <h1 className="font-hanken text-2xl md:text-3xl font-extrabold text-on-background mb-2">
                Module {currentIndex + 1}: {moduleData.title}
              </h1>
              
              <div className="flex flex-wrap gap-6 items-start mt-6">
                {/* Goal Panel */}
                <div className="flex-1 min-w-[300px] p-6 bg-surface-container-low rounded-xl border border-outline-variant/30">
                  <h3 className="font-hanken font-bold text-xs text-secondary uppercase tracking-wider mb-2">
                    Primary Goal
                  </h3>
                  <p className="text-sm text-on-surface leading-relaxed">
                    {moduleData.module_goal}
                  </p>
                </div>
                
                {/* Alignment Panel */}
                {moduleData.larger_goal_alignment && (
                  <div className="flex-1 min-w-[300px] p-6 bg-white border border-outline-variant rounded-xl shadow-sm">
                    <h3 className="font-hanken font-bold text-xs text-on-surface-variant mb-2">
                      How it supports your goal
                    </h3>
                    <p className="text-sm text-on-surface-variant italic leading-relaxed">
                      "{moduleData.larger_goal_alignment}"
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Transitions timeline previously / next */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
              {prevModule ? (
                <Link
                  href={`/plan/${id}/module/${prevModule.module_id}`}
                  className="group p-4 border border-outline-variant rounded-lg flex items-center gap-4 hover:bg-surface-container transition-all"
                >
                  <span className="material-symbols-outlined text-outline group-hover:text-secondary transition-colors">
                    arrow_back
                  </span>
                  <div>
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Previously</p>
                    <p className="font-hanken font-bold text-sm text-on-background">{prevModule.title}</p>
                  </div>
                </Link>
              ) : (
                <Link
                  href={`/plan/${id}`}
                  className="group p-4 border border-outline-variant rounded-lg flex items-center gap-4 hover:bg-surface-container transition-all"
                >
                  <span className="material-symbols-outlined text-outline group-hover:text-secondary transition-colors">
                    arrow_back
                  </span>
                  <div>
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Previously</p>
                    <p className="font-hanken font-bold text-sm text-on-background">Pathway Timeline</p>
                  </div>
                </Link>
              )}

              {nextModule ? (
                <Link
                  href={`/plan/${id}/module/${nextModule.module_id}`}
                  className="group p-4 border border-outline-variant rounded-lg flex items-center justify-end gap-4 text-right hover:bg-surface-container transition-all"
                >
                  <div>
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Next</p>
                    <p className="font-hanken font-bold text-sm text-on-background">{nextModule.title}</p>
                  </div>
                  <span className="material-symbols-outlined text-outline group-hover:text-secondary transition-colors">
                    arrow_forward
                  </span>
                </Link>
              ) : (
                <Link
                  href={`/plan/${id}`}
                  className="group p-4 border border-outline-variant rounded-lg flex items-center justify-end gap-4 text-right hover:bg-surface-container transition-all"
                >
                  <div>
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Next</p>
                    <p className="font-hanken font-bold text-sm text-on-background">Curriculum Complete</p>
                  </div>
                  <span className="material-symbols-outlined text-outline group-hover:text-secondary transition-colors">
                    arrow_forward
                  </span>
                </Link>
              )}
            </div>

            {/* Lesson Content Sections */}
            <div className="space-y-12 mb-10">
              {moduleData.lesson_sections?.map((section: any, idx: number) => {
                const readMinutes = Math.max(3, Math.round(section.body.split(/\s+/).length / 150));
                
                return (
                  <article key={idx} className="prose max-w-none border-b border-outline-variant/30 pb-10 last:border-b-0">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="font-hanken text-xl font-extrabold text-primary m-0">
                        {section.heading}
                      </h2>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant bg-surface-container-high px-2.5 py-1 rounded">
                        {readMinutes} min read
                      </span>
                    </div>

                    <div className="text-sm text-on-surface-variant leading-relaxed space-y-4 whitespace-pre-line">
                      {section.body}
                    </div>

                    {/* Show a beautiful botanical / laboratory graphic on the first lesson stack */}
                    {idx === 0 && (
                      <div className="my-6 relative overflow-hidden rounded-xl shadow-md border border-outline-variant h-80">
                        <img
                          alt="Cross-section scientific biology visualization"
                          className="w-full h-full object-cover"
                          src="https://lh3.googleusercontent.com/aida-public/AB6AXuDKWGXncvYiopwOqal8ge4t_w1yNloJD5-2StN-irk3Z9_l8NUifTL_TQ_mcnKUblvUWMuI2m6Vd-BAGhq8jGDseHqWBfD16KFhL5GSVQ378J4idZ3gYIDh5eOlfFYrcD76w3qno96jFQmrGyfvTC_vbd6En5yHyvepimfh_ZbVODhOyY6JPhOkgMoELMKnIHJVA3_eRRoArvkC9qu0CjLshfcmrTwxwwTAHOlhpjySNyMexispNoIOec3zBos7nnW8yRU4jdudWBK4"
                        />
                      </div>
                    )}

                    {section.source_section_ids && section.source_section_ids.length > 0 && (
                      <div className="mt-4 flex items-center gap-2 py-2 text-xs">
                        <span className="material-symbols-outlined text-sm text-outline">menu_book</span>
                        <span className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                          Source Section: {section.source_section_ids[0]}
                        </span>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>

            {/* Guided Activity Section */}
            {moduleData.guided_activity && (
              <section className="mb-10 p-6 bg-surface-container-low rounded-xl border-l-4 border-secondary shadow-sm">
                <div className="flex items-center gap-3 mb-4 text-secondary">
                  <span className="material-symbols-outlined text-2xl">explore</span>
                  <h3 className="font-hanken text-lg font-bold text-on-background m-0">
                    Guided Activity
                  </h3>
                </div>
                <div className="text-sm text-on-surface leading-relaxed whitespace-pre-line">
                  {moduleData.guided_activity}
                </div>
              </section>
            )}

            {/* Common Misconceptions Section */}
            {moduleData.common_misconceptions && moduleData.common_misconceptions.length > 0 && (
              <section className="mb-10 p-6 bg-error-container/20 rounded-xl border border-error/10">
                <div className="flex items-center gap-3 mb-4 text-error">
                  <span className="material-symbols-outlined">warning</span>
                  <h3 className="font-hanken text-xs font-bold uppercase tracking-wider m-0">
                    Common Misconceptions
                  </h3>
                </div>
                <ul className="list-disc list-inside space-y-2 text-sm text-on-surface leading-relaxed">
                  {moduleData.common_misconceptions.map((misconception: string, mIdx: number) => (
                    <li key={mIdx}>{misconception}</li>
                  ))}
                </ul>
              </section>
            )}

            {/* Checkpoint triggering region */}
            <div className="mt-12 mb-10 pt-10 border-t border-outline-variant text-center">
              <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-4">
                Ready to validate your progress?
              </p>
              <Link
                href={`/plan/${id}/module/${moduleId}/checkpoint`}
                className="bg-secondary text-on-secondary px-8 py-4 rounded-full font-hanken font-bold text-sm hover:shadow-lg hover:scale-105 active:scale-95 transition-all flex items-center gap-3 mx-auto cursor-pointer w-fit"
              >
                <span className="material-symbols-outlined">quiz</span>
                Checkpoint Quiz
              </Link>
            </div>
          </div>
        </div>

        {/* Mobile Navigation bar */}
        <nav className="md:hidden fixed bottom-0 left-0 w-full flex justify-around items-center py-2 bg-surface-container-lowest border-t border-outline-variant shadow-lg z-50 rounded-t-xl">
          <Link href="/" className="flex flex-col items-center justify-center text-on-surface-variant hover:text-secondary">
            <span className="material-symbols-outlined">home</span>
            <span className="text-[10px]">Home</span>
          </Link>
          <Link href={`/plan/${id}`} className="flex flex-col items-center justify-center text-on-surface-variant hover:text-secondary">
            <span className="material-symbols-outlined">menu_book</span>
            <span className="text-[10px]">My Plan</span>
          </Link>
          <span className="flex flex-col items-center justify-center text-secondary font-bold scale-110">
            <span className="material-symbols-outlined">school</span>
            <span className="text-[10px]">Learning</span>
          </span>
        </nav>
      </main>
    </div>
  );
}
