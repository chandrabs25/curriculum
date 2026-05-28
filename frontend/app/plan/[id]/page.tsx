"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CurriculumPlanPayload } from "../../types/curriculum";

export default function PlanDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const id = decodeURIComponent(params.id as string);

  const [plan, setPlan] = useState<CurriculumPlanPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Track completed module IDs locally
  const [completedModuleIds, setCompletedModuleIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;

    const loadTimer = window.setTimeout(() => {
      const storedPlan = localStorage.getItem(`curriculum-plan-${id}`) || matchingCurrentPlan(id);
      if (storedPlan) {
        try {
          const parsedPlan = JSON.parse(storedPlan) as CurriculumPlanPayload;
          localStorage.setItem(`curriculum-plan-${parsedPlan.curriculum_plan_id}`, JSON.stringify(parsedPlan));
          setPlan(parsedPlan);
          
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
  }, [id]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="max-w-md w-full text-center bg-surface-container-lowest p-8 rounded-2xl border border-outline-variant shadow-md">
          <h2 className="text-2xl font-bold text-error">Error</h2>
          <p className="mt-2 text-on-surface-variant text-sm">{error}</p>
          <Link
            href="/onboard"
            className="mt-6 inline-block px-6 py-2 bg-primary text-on-primary rounded-full hover:opacity-90 text-sm font-semibold shadow-sm"
          >
            Go to Onboarding
          </Link>
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-secondary border-t-transparent mx-auto"></div>
          <p className="mt-4 text-on-surface-variant text-sm">Loading plan dashboard...</p>
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

  return (
    <div className="bg-background text-on-surface min-h-screen flex flex-col font-public">
      
      {/* Top Navigation Bar */}
      <nav className="bg-surface border-b border-outline-variant sticky top-0 z-45 flex justify-between items-center w-full px-10 h-16">
        <div className="flex items-center gap-6">
          <span className="text-headline-md font-hanken font-bold text-primary">AcademicFlow</span>
          <div className="hidden md:flex gap-6 h-full items-center">
            <Link
              href="/"
              className="text-on-surface-variant font-hanken font-bold text-sm hover:text-secondary transition-colors"
            >
              Dashboard
            </Link>
            <span className="text-secondary border-b-2 border-secondary font-hanken font-bold text-sm h-16 flex items-center px-1">
              Curriculum Plan
            </span>
            {activeModule && (
              <Link
                href={`/plan/${plan.curriculum_plan_id}/module/${activeModuleId}`}
                className="text-on-surface-variant font-hanken font-bold text-sm hover:text-secondary transition-colors"
              >
                Active Module
              </Link>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="relative hidden lg:block">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search curriculum..."
              className="bg-surface-container-low border border-outline-variant rounded-full px-4 py-1.5 text-sm w-64 focus:ring-2 focus:ring-secondary focus:border-transparent outline-none"
            />
          </div>
          <button className="material-symbols-outlined text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
            notifications
          </button>
          <button className="material-symbols-outlined text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
            account_circle
          </button>
          <Link
            href="/onboard"
            className="bg-primary text-on-primary px-4 py-2 rounded-lg font-hanken font-bold text-xs flex items-center gap-2 hover:opacity-90 active:scale-95 transition-all shadow-sm"
          >
            <span className="material-symbols-outlined text-base">add</span>
            Create New
          </Link>
        </div>
      </nav>

      {/* Main Container */}
      <div className="flex max-w-[1280px] w-full mx-auto flex-1 h-[calc(100vh-64px)] overflow-hidden">
        
        {/* Left Side Navigation (Desktop Only) */}
        <aside className="hidden md:flex flex-col h-full py-6 bg-surface-container-low border-r border-outline-variant w-64 shrink-0 px-4">
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-1">
              <img
                alt="User Profile"
                className="w-10 h-10 rounded-full bg-surface-container-high border border-outline-variant object-cover"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCnJhQ53m1u2m5YRvCuVeDOmDiMVBh5M3TbAznPVxGkB9kJjUQ2lzxmLvGg_oDRstbvgwoZlESK-x_JZp7-NfVe92tYeLpZuq0HWFy1RbbAJ4JxBtvo17-VwsGP7zc34ldWCRj5TwaMUz0Wrt5dkcq3ZWZ7Ys9a7I7h2fofFw3By9c14BUPO4Y2BrF-X44OtTCt_uC_PmK0_EMJkscJ6hLWf12VoRHsaRKL_tqQe5o2P-k9cWEr3xBbQRSXpheTLCfcMEUayyhOZZrc"
              />
              <div>
                <p className="font-hanken font-bold text-xs text-on-surface">Academic Portal</p>
                <p className="text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">Curriculum Engine</p>
              </div>
            </div>
          </div>
          
          <nav className="flex-1 space-y-1">
            <Link
              href="/"
              className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-variant transition-all rounded-lg group"
            >
              <span className="material-symbols-outlined group-hover:text-secondary">dashboard</span>
              <span className="font-hanken font-semibold text-sm">Dashboard</span>
            </Link>
            <span className="flex items-center gap-3 px-3 py-2.5 text-secondary font-bold border-r-4 border-secondary bg-surface-container-high rounded-l-lg translate-x-1 transition-transform">
              <span className="material-symbols-outlined">map</span>
              <span className="font-hanken font-semibold text-sm">Curriculum Plan</span>
            </span>
            {activeModule && (
              <Link
                href={`/plan/${plan.curriculum_plan_id}/module/${activeModuleId}`}
                className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-variant transition-all rounded-lg group"
              >
                <span className="material-symbols-outlined group-hover:text-secondary">auto_stories</span>
                <span className="font-hanken font-semibold text-sm">Active Module</span>
              </Link>
            )}
          </nav>

          <div className="mt-auto pt-6 border-t border-outline-variant space-y-1">
            <a href="#" className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-variant transition-all rounded-lg">
              <span className="material-symbols-outlined">settings</span>
              <span className="font-hanken font-semibold text-sm">Settings</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2.5 text-on-surface-variant hover:bg-surface-variant transition-all rounded-lg">
              <span className="material-symbols-outlined">help</span>
              <span className="font-hanken font-semibold text-sm">Support</span>
            </a>
          </div>
        </aside>

        {/* Central main view: Timeline/Roadmap */}
        <main className="flex-1 overflow-y-auto px-4 md:px-10 py-8 bg-background custom-scrollbar">
          
          {/* Summary Banner Card */}
          <section className="mb-8">
            <div className="bg-surface-container-lowest border border-outline-variant rounded-xl p-6 shadow-[0px_4px_20px_rgba(15,23,42,0.05)]">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                  <h1 className="font-hanken text-2xl md:text-3xl font-extrabold text-primary mb-1">
                    {plan.onboarding.topic}
                  </h1>
                  <p className="text-sm text-on-surface-variant">
                    {plan.onboarding.learning_goal}
                  </p>
                </div>
                
                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-secondary">
                      Pathway Progress
                    </p>
                    <p className="font-hanken text-2xl font-extrabold text-primary">
                      {progressPercentage}%
                    </p>
                  </div>
                  <div className="w-32 h-2 bg-surface-container rounded-full overflow-hidden">
                    <div
                      className="h-full bg-secondary-container rounded-full transition-all duration-1000 ease-out"
                      style={{ width: `${progressPercentage}%` }}
                    ></div>
                  </div>
                </div>
              </div>

              {/* Preferences breakdown */}
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mt-8 pt-6 border-t border-outline-variant">
                <div>
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider mb-0.5">Subject</p>
                  <p className="text-sm font-semibold text-on-surface">{plan.onboarding.subject || "General"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider mb-0.5">Grade Level</p>
                  <p className="text-sm font-semibold text-on-surface">Grade {plan.metadata?.grade || "N/A"}</p>
                </div>
                <div>
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider mb-0.5">Study Pace</p>
                  <p className="text-sm font-semibold text-on-surface">{plan.onboarding.deadline_or_pace}</p>
                </div>
                <div>
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider mb-0.5">Learning Style</p>
                  <p className="text-sm font-semibold text-on-surface capitalize">{plan.onboarding.preferred_learning_style.replace("-", " ")}</p>
                </div>
                <div>
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider mb-0.5">Total Duration</p>
                  <p className="text-sm font-semibold text-on-surface">{plan.onboarding.available_time}</p>
                </div>
              </div>
            </div>
          </section>

          {/* Chronological Timeline list */}
          <section className="relative">
            <div className="absolute left-6 top-0 bottom-0 w-px bg-outline-variant/60 hidden md:block"></div>
            
            <div className="space-y-6 relative">
              {displayedModules.map((module, idx) => {
                const isCompleted = completedModuleIds.includes(module.module_id);
                const isActive = module.module_id === activeModuleId;
                const isUpcoming = !isCompleted && !isActive;

                const estReadTime = Math.max(10, module.source_section_ids.length * 6);

                return (
                  <div key={module.module_id} className="flex gap-8 group">
                    {/* Circle Icon Badge on Timeline (Desktop Only) */}
                    <div className="relative z-10 hidden md:flex items-center justify-center w-12 h-12 rounded-full border-4 border-background shadow-md shrink-0">
                      {isCompleted && (
                        <div className="w-full h-full rounded-full bg-secondary-container text-on-secondary flex items-center justify-center">
                          <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                            check_circle
                          </span>
                        </div>
                      )}
                      {isActive && (
                        <div className="w-full h-full rounded-full bg-white text-secondary border border-secondary flex items-center justify-center animate-pulse">
                          <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                            play_circle
                          </span>
                        </div>
                      )}
                      {isUpcoming && (
                        <div className="w-full h-full rounded-full bg-surface-container text-outline flex items-center justify-center">
                          <span className="material-symbols-outlined text-[20px]">lock</span>
                        </div>
                      )}
                    </div>

                    {/* Module card body */}
                    <div className={`flex-1 border rounded-xl p-6 relative overflow-hidden transition-all duration-300 ${
                      isActive
                        ? "bg-white border-2 border-secondary-container shadow-xl"
                        : "bg-surface-container-lowest border-outline-variant hover:shadow-lg"
                    } ${isUpcoming ? "opacity-75 hover:opacity-100" : ""}`}>
                      
                      <div className="absolute top-0 right-0 p-3">
                        <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${
                          isActive
                            ? "bg-secondary-fixed-dim text-on-secondary-fixed"
                            : "bg-surface-variant text-on-surface-variant"
                        }`}>
                          {estReadTime}m to Read
                        </span>
                      </div>

                      <div className="mb-4">
                        <p className="text-[10px] font-bold text-secondary uppercase tracking-widest mb-1">
                          Module {String(idx + 1).padStart(2, "0")} {isActive ? "• Active" : ""}
                        </p>
                        <h3 className="font-hanken text-lg font-bold text-on-surface">
                          {module.title}
                        </h3>
                      </div>

                      <p className="text-sm text-on-surface-variant mb-6 leading-relaxed">
                        {module.module_goal}
                      </p>

                      {/* Concepts Covered */}
                      {module.covered_concept_ids && module.covered_concept_ids.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-6">
                          {module.covered_concept_ids.map((concept) => (
                            <span
                              key={concept}
                              className={`px-2 py-1 rounded text-xs font-semibold ${
                                isActive
                                  ? "bg-secondary-container/10 text-secondary border border-secondary/20"
                                  : "bg-surface-container text-on-surface-variant"
                              }`}
                            >
                              {concept.replace("concept:", "").replace(/_/g, " ")}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Prerequisite Alert warning */}
                      {module.prerequisite_warnings && module.prerequisite_warnings.length > 0 && (
                        <div className="mb-6 p-3 rounded-lg bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-900 text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2">
                          <span className="material-symbols-outlined text-base">warning</span>
                          <span>{module.prerequisite_warnings[0]}</span>
                        </div>
                      )}

                      <div className="flex items-center justify-between border-t border-outline-variant pt-4">
                        {idx < sortedModules.length - 1 ? (
                          <p className="text-xs text-on-surface-variant italic">
                            Next: {sortedModules[idx + 1].title}
                          </p>
                        ) : (
                          <p className="text-xs text-on-surface-variant italic">
                            Prerequisite Complete
                          </p>
                        )}

                        {isCompleted && (
                          <Link
                            href={`/plan/${plan.curriculum_plan_id}/module/${module.module_id}`}
                            className="text-secondary font-hanken font-bold text-sm hover:underline flex items-center gap-1"
                          >
                            Review Module
                            <span className="material-symbols-outlined text-base">arrow_forward</span>
                          </Link>
                        )}

                        {isActive && (
                          <Link
                            href={`/plan/${plan.curriculum_plan_id}/module/${module.module_id}`}
                            className="bg-primary text-on-primary px-6 py-2 rounded-lg font-hanken font-bold text-xs shadow-md hover:bg-on-background transition-all"
                          >
                            Start Studying
                          </Link>
                        )}

                        {isUpcoming && (
                          <span className="text-on-surface-variant font-hanken font-bold text-sm flex items-center gap-1 cursor-not-allowed opacity-60">
                            Open Module
                            <span className="material-symbols-outlined text-base">lock</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Bottom CTA for new curriculum */}
          <section className="mt-12 flex justify-center pb-12">
            <Link
              href="/onboard"
              className="flex flex-col items-center gap-2 group p-8 rounded-2xl border-2 border-dashed border-outline-variant hover:border-secondary hover:bg-surface-container-low transition-all cursor-pointer text-center w-full max-w-md"
            >
              <span className="material-symbols-outlined text-secondary scale-150 mb-2 group-hover:rotate-90 transition-transform">
                add_circle
              </span>
              <span className="font-hanken font-bold text-lg text-on-surface">New Curriculum</span>
              <span className="text-xs text-on-surface-variant">Generate a fresh learning path with AI</span>
            </Link>
          </section>
        </main>

        {/* Right Sidebar: Recommended content & reinforcement (Desktop Only) */}
        <aside className="hidden xl:flex flex-col w-80 shrink-0 border-l border-outline-variant bg-surface-container-lowest p-6 overflow-y-auto custom-scrollbar">
          
          {/* recommended box */}
          <div className="mb-8">
            <h4 className="font-hanken font-bold text-sm text-primary mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary text-lg">recommend</span>
              Helpful Alongside This
            </h4>
            
            <div className="space-y-4">
              <div className="group cursor-pointer">
                <div className="w-full h-32 rounded-lg bg-surface-container mb-2 overflow-hidden relative border border-outline-variant/40">
                  <img
                    alt="Abstract study notes"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuBQyoC7glS4bULrZwtHHGt-Inoo87iKg-Yn3dmlgB5KBKNSMQjyO8gAvEEC3YFSrOqyu46rJskdEx_pL0X-Tkiu0B_8tG6cayUwnd73kS6eehK2roQtP--nlQXTcsfgP5Fh1HbOpCZVTaCMI6Q70UUlIXsFzbaRZz-h-4eOrHM26n60oKMQNu8a_SzSH8yvzqtUoeApZKNbwYJbgvlfsmPfKrdxxQ62M1UG95AkNVGPF3wxiEOIgHlQYU6p38fOf1FfbYqAiAAO23rK"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent flex items-end p-3">
                    <span className="text-white text-xxs font-bold uppercase tracking-wider">Recommended Pack</span>
                  </div>
                </div>
                <p className="font-hanken font-semibold text-xs text-on-surface group-hover:text-secondary transition-colors">
                  Reference Formulas & Formulas Cheatsheet
                </p>
                <p className="text-[10px] text-on-surface-variant">Strengthen your math derivations</p>
              </div>

              <div className="group cursor-pointer">
                <div className="w-full h-32 rounded-lg bg-surface-container mb-2 overflow-hidden relative border border-outline-variant/40">
                  <img
                    alt="strategic nodes"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuCtiSnoiupQgXeEMwDzoOCdqvhBjFEuSAyEKM7PAJVc6JvPEJbpC8D9Rzda_zFIY4CxEG6tAGCLZN_49ImWGfqpE6qAQpd6QAsDIppnPPPrQPz7-zxnmYcnKY8BSiKxRGAc93O-EqMRuMn7l1Lbhr7GL93CHKcF8lRYlw9KuFYVQup9EJoWeR0z3vyh9x6en9ezJvBxW_eeMT-jS_egUA0wRlAI91ZcjCIGzBc6ez3zkvntjV1bHFFxx_FomnsFWLHKBR68Ym641iPG"
                  />
                </div>
                <p className="font-hanken font-semibold text-xs text-on-surface group-hover:text-secondary transition-colors">
                  Intro to Concept Relations
                </p>
                <p className="text-[10px] text-on-surface-variant">Parallel concepts in textbook links</p>
              </div>
            </div>
          </div>

          {/* reinforcement box */}
          <div className="mb-8 pt-6 border-t border-outline-variant">
            <h4 className="font-hanken font-bold text-sm text-primary mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary text-lg">fitness_center</span>
              Reinforce With
            </h4>
            
            <ul className="space-y-3">
              <li className="flex items-start gap-3 p-3 rounded-lg hover:bg-surface-container transition-colors cursor-pointer border border-transparent hover:border-outline-variant">
                <span className="material-symbols-outlined text-secondary mt-1 text-base">quiz</span>
                <div>
                  <p className="text-xs font-bold text-on-surface">Concept Scaffolding Quiz</p>
                  <p className="text-[10px] text-on-surface-variant">10 Rapid-fire questions</p>
                </div>
              </li>
              <li className="flex items-start gap-3 p-3 rounded-lg hover:bg-surface-container transition-colors cursor-pointer border border-transparent hover:border-outline-variant">
                <span className="material-symbols-outlined text-secondary mt-1 text-base">edit_note</span>
                <div>
                  <p className="text-xs font-bold text-on-surface">Worked Out Proofs</p>
                  <p className="text-[10px] text-on-surface-variant">Guided textbook exercises</p>
                </div>
              </li>
            </ul>
          </div>

          {/* AI advisor helper */}
          <div className="mt-auto p-4 bg-surface-container-low rounded-xl border border-outline-variant">
            <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-wider mb-2">Academic Advisor AI</p>
            <p className="text-xs italic text-on-surface mb-3 leading-relaxed">
              "We have mapped {sortedModules.length} lessons optimized for Grade {plan.metadata?.grade || "N/A"} textbook constraints. Master checkpoints to track misconceptions."
            </p>
            <Link
              href={`/plan/${plan.curriculum_plan_id}/module/${activeModuleId}`}
              className="w-full py-2 bg-surface-container-highest text-secondary border border-secondary/20 rounded-lg text-xs font-bold text-center block hover:bg-surface-variant transition-colors"
            >
              Study Active Lesson
            </Link>
          </div>
        </aside>
      </div>

      {/* Bottom Nav Bar (Mobile Only) */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full flex justify-around items-center py-2 bg-surface-container-lowest border-t border-outline-variant shadow-lg z-50 rounded-t-xl">
        <Link
          href="/"
          className="flex flex-col items-center justify-center text-on-surface-variant hover:text-secondary"
        >
          <span className="material-symbols-outlined">home</span>
          <span className="text-[10px]">Home</span>
        </Link>
        <span className="flex flex-col items-center justify-center text-secondary font-bold">
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
            menu_book
          </span>
          <span className="text-[10px]">My Plan</span>
        </span>
        {activeModule && (
          <Link
            href={`/plan/${plan.curriculum_plan_id}/module/${activeModuleId}`}
            className="flex flex-col items-center justify-center text-on-surface-variant hover:text-secondary"
          >
            <span className="material-symbols-outlined">school</span>
            <span className="text-[10px]">Learning</span>
          </Link>
        )}
      </nav>
      
      {/* Floating Action Button for curriculum creation */}
      <Link
        href="/onboard"
        className="fixed bottom-20 right-6 md:bottom-8 md:right-8 w-14 h-14 bg-secondary-container text-on-secondary-container rounded-full shadow-2xl flex items-center justify-center hover:scale-110 active:scale-90 transition-all z-40"
      >
        <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
          add
        </span>
      </Link>
    </div>
  );
}

function matchingCurrentPlan(id: string): string | null {
  const raw = localStorage.getItem("curriculum-current-plan");
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as CurriculumPlanPayload;
    return parsed.curriculum_plan_id === id ? raw : null;
  } catch {
    return null;
  }
}
