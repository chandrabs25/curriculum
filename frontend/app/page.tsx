"use client";

import { useState } from "react";
import Link from "next/link";

interface LocalPlan {
  id: string;
  topic: string;
  subject: string;
  modulesCount: number;
}

export default function Home() {
  const [recentPlans] = useState<LocalPlan[]>(() => {
    if (typeof window !== "undefined") {
      const keys = Object.keys(localStorage);
      const plans: LocalPlan[] = [];

      keys.forEach((key) => {
        if (key.startsWith("curriculum-plan-")) {
          const raw = localStorage.getItem(key);
          if (raw) {
            try {
              const parsed = JSON.parse(raw);
              plans.push({
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

      return plans;
    }
    return [];
  });

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 dark:bg-zinc-900 font-sans text-gray-900 dark:text-zinc-50">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white py-5 px-6 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mx-auto max-w-5xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-6 w-6 rounded bg-indigo-600"></span>
            <span className="text-xl font-bold tracking-tight">AI Curriculum Creator</span>
          </div>
          <Link
            href="/onboard"
            className="inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm"
          >
            Create Plan
          </Link>
        </div>
      </header>

      {/* Main Hero */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-16 flex flex-col gap-12">
        <div className="text-center md:text-left max-w-2xl py-8">
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight leading-tight">
            Tailor-Made Learning Pathways, <span className="text-indigo-600">Powered by AI</span>
          </h1>
          <p className="mt-4 text-lg text-gray-600 dark:text-zinc-400 leading-relaxed">
            Generate customized physics, chemistry, biology or other subject curriculum roadmaps. Take dynamic module-level diagnostic checks to track competencies and clear up misconceptions.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center md:justify-start">
            <Link
              className="flex h-12 items-center justify-center rounded-lg bg-indigo-600 px-6 font-medium text-white shadow hover:bg-indigo-700 text-base"
              href="/onboard"
            >
              Start Onboarding Wizard
            </Link>
          </div>
        </div>

        {/* Recent Plans */}
        <div className="border-t border-gray-200 dark:border-zinc-800 pt-12">
          <h2 className="text-2xl font-bold mb-6">Recent Local Learning Plans</h2>
          {recentPlans.length === 0 ? (
            <div className="bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 p-8 rounded-xl text-center">
              <p className="text-gray-500 dark:text-zinc-400">
                You haven&apos;t generated any learning plans yet.
              </p>
              <Link
                href="/onboard"
                className="mt-4 inline-block text-sm font-semibold text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
              >
                Launch onboarding wizard &rarr;
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {recentPlans.map((plan) => (
                <div
                  key={plan.id}
                  className="bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow flex justify-between items-center"
                >
                  <div>
                    <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950 px-2 py-0.5 rounded uppercase">
                      {plan.subject}
                    </span>
                    <h3 className="text-lg font-bold mt-2 text-gray-900 dark:text-white">
                      {plan.topic}
                    </h3>
                    <p className="text-xs text-gray-500 dark:text-zinc-400 mt-1">
                      {plan.modulesCount} planned modules
                    </p>
                  </div>
                  <Link
                    href={`/plan/${plan.id}`}
                    className="inline-flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 dark:bg-zinc-700 dark:text-white dark:border-zinc-650"
                  >
                    Resume
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 dark:border-zinc-800 py-8 px-6 bg-white dark:bg-zinc-950 text-center text-xs text-gray-500 dark:text-zinc-400">
        <div className="max-w-5xl mx-auto">
          AI Curriculum Creator Frontend &copy; {new Date().getFullYear()}. Ready for Vercel upload.
        </div>
      </footer>
    </div>
  );
}
