"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface LocalPlan {
  id: string;
  topic: string;
  subject: string;
  modulesCount: number;
}

export default function Home() {
  const [recentPlans, setRecentPlans] = useState<LocalPlan[]>([]);

  useEffect(() => {
    const keys = Object.keys(localStorage);
    const plansById = new Map<string, LocalPlan>();

    keys.forEach((key) => {
      if (key.startsWith("curriculum-plan-")) {
        const raw = localStorage.getItem(key);
        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            const id = parsed.curriculum_plan_id;
            if (!id || plansById.has(id)) return;
            plansById.set(id, {
              id: parsed.curriculum_plan_id,
              topic: parsed.onboarding?.topic || "Unknown Topic",
              subject: parsed.onboarding?.subject || "General",
              modulesCount: parsed.modules?.length || 0,
            });
          } catch {
            // Ignore corrupted plans
          }
        }
      }
    });

    Promise.resolve().then(() => {
      setRecentPlans([...plansById.values()]);
    });
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-white font-sans text-zinc-900 selection:bg-zinc-100 selection:text-zinc-950">
      {/* Navigation */}
      <header className="w-full max-w-4xl mx-auto px-6 h-20 flex items-center justify-between border-b border-zinc-200">
        <Link href="/" className="text-sm font-medium tracking-tight text-zinc-900 hover:opacity-85 transition-opacity">
          Curriculum
        </Link>
        <Link
          href="/onboard"
          className="text-xs font-medium text-zinc-500 hover:text-zinc-900 transition-colors border border-zinc-300 rounded-full px-4 py-1.5 hover:border-zinc-900"
        >
          New Plan
        </Link>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-20 flex flex-col gap-16">
        {/* Hero Section */}
        <section className="max-w-xl py-4">
          <h1 className="text-3xl font-light tracking-tight text-zinc-950 leading-tight">
            AI Curriculum Creator
          </h1>
          <p className="mt-4 text-sm text-zinc-500 leading-relaxed font-normal">
            Generate customized subject roadmaps and take diagnostic checks to track core competencies.
          </p>
          <div className="mt-8">
            <Link
              className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-6 py-2.5 text-xs font-medium text-white transition-colors hover:bg-zinc-800"
              href="/onboard"
            >
              Start
            </Link>
          </div>
        </section>

        {/* Recent Plans */}
        <section className="border-t border-zinc-200 pt-12">
          <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-400 mb-6">Recent plans</h2>
          {recentPlans.length === 0 ? (
            <div className="text-left py-4">
              <p className="text-sm text-zinc-400">
                No active plans. Create one to begin.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {recentPlans.map((plan) => (
                <div
                  key={plan.id}
                  className="group flex flex-col justify-between items-start border-b border-zinc-200 pb-6"
                >
                  <div className="w-full">
                    <span className="text-[10px] font-medium tracking-wider uppercase text-zinc-400">
                      {plan.subject}
                    </span>
                    <h3 className="text-base font-normal text-zinc-900 mt-1">
                      {plan.topic}
                    </h3>
                    <p className="text-xs text-zinc-400 mt-1 font-light">
                      {plan.modulesCount} modules
                    </p>
                  </div>
                  <Link
                    href={`/plan/${plan.id}`}
                    className="mt-4 text-xs font-medium text-zinc-900 group-hover:text-zinc-600 inline-flex items-center gap-1 transition-colors"
                  >
                    Resume &rarr;
                  </Link>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-200 py-10 px-6 text-left text-[11px] text-zinc-400">
        <div className="max-w-4xl mx-auto">
          AI Curriculum Creator &copy; {new Date().getFullYear()}
        </div>
      </footer>
    </div>
  );
}

