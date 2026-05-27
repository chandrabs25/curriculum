"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createCurriculumPlan } from "../../services/api";
import { RetrievalPreviewResponse, CurriculumQueryPayload } from "../../types/curriculum";

export default function OnboardPreviewPage() {
  const router = useRouter();
  
  const [previewData, setPreviewData] = useState<RetrievalPreviewResponse | null>(null);
  const [query, setQuery] = useState<CurriculumQueryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Quiz selection state: maps concept_id to status ("known_well" | "somewhat_known" | "unfamiliar")
  const [comfortAnswers, setComfortAnswers] = useState<Record<string, string>>({});
  
  // Success overlay state
  const [showOverlay, setShowOverlay] = useState(false);
  const [progressWidth, setProgressWidth] = useState(0);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedPreview = localStorage.getItem("curriculum-onboard-preview");
      const storedQuery = localStorage.getItem("curriculum-onboard-query");

      if (storedPreview && storedQuery) {
        try {
          const parsedPreview = JSON.parse(storedPreview) as RetrievalPreviewResponse;
          const parsedQuery = JSON.parse(storedQuery) as CurriculumQueryPayload;

          setPreviewData(parsedPreview);
          setQuery(parsedQuery);
          
          // Pre-populate quiz answers with default "somewhat_known" for all prerequisite questions
          const defaults: Record<string, string> = {};
          parsedPreview.prerequisite_questions?.forEach((q) => {
            defaults[q.concept_id] = "somewhat_known";
          });
          setComfortAnswers(defaults);
        } catch (e) {
          setError("Failed to load retrieval preview details.");
        }
      } else {
        setError("Onboarding query context not found. Please fill out the form first.");
      }
      setLoading(false);
    }
  }, []);

  const handleSelectOption = (conceptId: string, status: string) => {
    setComfortAnswers((prev) => ({
      ...prev,
      [conceptId]: status,
    }));
  };

  const handleGeneratePlan = async () => {
    if (!query || !previewData) return;

    setSubmitting(true);
    setError(null);
    setShowOverlay(true);
    setProgressWidth(0);

    // Increment progress bar animation
    const progressInterval = setInterval(() => {
      setProgressWidth((prev) => {
        if (prev >= 95) {
          clearInterval(progressInterval);
          return 95;
        }
        return prev + 15;
      });
    }, 300);

    // Structure the prerequisite checks matching PrerequisiteCheckPayload
    const formattedAnswers = Object.entries(comfortAnswers).map(([conceptId, status]) => {
      const matchingQuestion = previewData.prerequisite_questions.find(
        (q) => q.concept_id === conceptId
      );
      return {
        concept_id: conceptId,
        status: status,
        required_by_section_id: matchingQuestion?.required_by_section_id || "",
      };
    });

    const finalQuery: CurriculumQueryPayload = {
      ...query,
      prerequisite_check: {
        asked: true,
        answers: formattedAnswers,
      },
    };

    try {
      const plan = await createCurriculumPlan(finalQuery);
      
      clearInterval(progressInterval);
      setProgressWidth(100);

      // Save plan to localStorage because backend is stateless
      localStorage.setItem(`curriculum-plan-${plan.curriculum_plan_id}`, JSON.stringify(plan));
      
      // Delay slightly to finish progress bar animation
      setTimeout(() => {
        router.push(`/plan/${plan.curriculum_plan_id}`);
      }, 500);
    } catch (err: any) {
      clearInterval(progressInterval);
      setShowOverlay(false);
      console.error(err);
      setError(err.message || "Failed to generate curriculum. Please check backend connections.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-secondary border-t-transparent mx-auto"></div>
          <p className="mt-4 text-on-surface-variant text-sm">Analyzing textbooks...</p>
        </div>
      </div>
    );
  }

  if (error || !previewData || !query) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="max-w-md w-full text-center bg-surface-container-lowest p-8 rounded-2xl border border-outline-variant shadow-md">
          <h2 className="text-2xl font-bold text-error">Error</h2>
          <p className="mt-2 text-on-surface-variant text-sm">{error || "Preview unavailable."}</p>
          <Link
            href="/onboard"
            className="mt-6 inline-block px-6 py-2 bg-primary text-on-primary rounded-full hover:opacity-90 text-sm font-semibold shadow-sm"
          >
            Back to Onboarding
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="font-public text-body-md bg-background min-h-screen overflow-x-hidden">
      {/* focused onboarding container */}
      <main className="min-h-screen px-4 md:px-10 py-10 max-w-[1280px] mx-auto">
        
        {/* Header Section */}
        <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-secondary font-hanken font-bold text-sm">
              <span className="material-symbols-outlined text-sm">auto_awesome</span>
              <span>Curriculum Preview</span>
            </div>
            <h1 className="font-hanken text-3xl md:text-4xl font-extrabold text-on-background">
              Topic: {query.onboarding.topic}
            </h1>
            <p className="text-body-lg text-on-surface-variant max-w-2xl">
              Goal: {query.onboarding.learning_goal}
            </p>
          </div>
          <Link
            href="/onboard"
            className="hidden md:flex items-center gap-2 px-6 py-3 border border-outline-variant rounded-xl bg-white hover:bg-surface-container-low transition-colors font-hanken font-bold text-sm text-on-surface-variant"
          >
            <span className="material-symbols-outlined text-base">edit</span>
            Back to Onboarding
          </Link>
        </header>

        {/* Bento Grid layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Left Bento: Modules and details */}
          <div className="lg:col-span-8 space-y-12">
            
            {/* Target Sections */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-hanken text-2xl font-bold text-on-background">Target Sections</h2>
                <span className="bg-secondary-container text-on-secondary-container px-3 py-1 rounded-full text-xs font-semibold">
                  {previewData.retrieved_sections?.length || 0} Modules
                </span>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {previewData.retrieved_sections?.map((section, index) => {
                  const estReadTime = Math.max(5, Math.round(section.summary.split(/\s+/).length / 20));
                  return (
                    <article
                      key={section.section_id}
                      className="tonal-card bg-surface-container-lowest p-6 rounded-xl relative border border-[#E2E8F0] shadow-sm hover:border-secondary transition-all cursor-default"
                    >
                      <div className="absolute top-4 right-4 text-xs text-on-surface-variant opacity-60">
                        {estReadTime} min read
                      </div>
                      <div className="mb-3 flex items-center gap-2">
                        <span className="bg-[#EFF6FF] text-secondary text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded">
                          {section.score >= 0.7 ? "Highly Relevant" : "Related Section"}
                        </span>
                      </div>
                      <h3 className="font-hanken font-bold text-lg mb-2 text-on-background">
                        {section.title}
                      </h3>
                      <p className="text-sm text-on-surface-variant mb-4 line-clamp-3">
                        {section.summary}
                      </p>
                      <div className="flex items-center gap-4 text-xs text-outline">
                        <div className="flex items-center gap-1">
                          <span className="material-symbols-outlined text-sm">school</span>
                          {section.subject || "General"}
                        </div>
                        {section.grade !== null && (
                          <div className="flex items-center gap-1">
                            <span className="material-symbols-outlined text-sm">grade</span>
                            Grade {section.grade}
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>

            {/* Prerequisite Sections */}
            {previewData.learning_path_context?.prerequisite_sections?.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-hanken text-2xl font-bold text-on-background">Foundational Prerequisites</h2>
                </div>
                <div className="bg-surface-container-low rounded-xl overflow-hidden border border-outline-variant/60 shadow-inner">
                  <div className="divide-y divide-outline-variant">
                    {previewData.learning_path_context.prerequisite_sections.map((prereq, index) => (
                      <div
                        key={prereq.section_id}
                        className="p-6 flex flex-col md:flex-row md:items-center gap-4 hover:bg-surface-container-high transition-colors"
                      >
                        <div className="h-12 w-12 rounded-lg bg-surface-container-lowest flex items-center justify-center shrink-0 border border-outline-variant">
                          <span className="material-symbols-outlined text-secondary">
                            energy_savings_leaf
                          </span>
                        </div>
                        <div className="grow">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-hanken font-semibold text-sm text-on-background">
                              {prereq.title}
                            </h4>
                            <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant px-2 py-0.5 border border-outline-variant rounded">
                              {prereq.role}
                            </span>
                          </div>
                          <p className="text-xs text-on-surface-variant">
                            {prereq.summary}
                          </p>
                        </div>
                        <div className="text-xs text-secondary font-semibold shrink-0 uppercase tracking-wide">
                          Required Base
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {/* Optional Support / reinforcement */}
            {previewData.learning_path_context?.support_sections?.length > 0 && (
              <section>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-hanken text-2xl font-bold text-on-background">Optional Support Resources</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {previewData.learning_path_context.support_sections.map((support, index) => (
                    <div
                      key={support.section_id}
                      className="tonal-card bg-surface-container-lowest p-5 rounded-xl border border-[#E2E8F0] shadow-sm flex gap-4"
                    >
                      <div className="h-14 w-14 rounded-lg bg-surface-container-low flex items-center justify-center shrink-0 border border-outline-variant">
                        <span className="material-symbols-outlined text-secondary text-2xl">
                          layers
                        </span>
                      </div>
                      <div className="py-0.5">
                        <h4 className="font-hanken font-semibold text-sm text-on-background mb-1">
                          {support.title}
                        </h4>
                        <p className="text-xs text-on-surface-variant mb-2 line-clamp-2">
                          {support.summary}
                        </p>
                        <span className="text-[10px] font-bold bg-surface-container px-2 py-0.5 rounded text-secondary uppercase tracking-wider">
                          {support.role}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* Right Bento: Prerequisite comfort check */}
          <div className="lg:col-span-4 space-y-6 lg:sticky lg:top-24">
            
            {/* comfort check panel */}
            {previewData.prerequisite_questions?.length > 0 ? (
              <div className="tonal-card bg-surface-container-lowest p-6 rounded-xl border border-[#E2E8F0] shadow-md">
                <h3 className="font-hanken text-lg font-bold mb-3 flex items-center gap-2 text-on-background">
                  <span className="material-symbols-outlined text-secondary">psychology</span>
                  Prerequisite Check
                </h3>
                <p className="text-sm text-on-surface-variant mb-6 leading-relaxed">
                  Before generating your flow, how comfortable are you with these foundational concepts?
                </p>

                <div className="space-y-6">
                  {previewData.prerequisite_questions.map((q) => {
                    const selectedVal = comfortAnswers[q.concept_id] || "somewhat_known";

                    return (
                      <div key={q.question_id} className="border-t border-outline-variant/40 pt-4 first:border-0 first:pt-0">
                        <span className="font-hanken font-bold text-sm block text-on-background mb-3">
                          Concept: {q.label}
                        </span>
                        
                        {q.pedagogical_reason && (
                          <p className="text-[11px] text-on-surface-variant/80 italic mb-2 leading-tight">
                            Reason: {q.pedagogical_reason}
                          </p>
                        )}

                        <div className="grid grid-cols-1 gap-2">
                          <button
                            type="button"
                            onClick={() => handleSelectOption(q.concept_id, "known_well")}
                            className={`quiz-btn w-full text-left p-3 rounded-lg border text-sm transition-all flex items-center justify-between focus:outline-none cursor-pointer ${
                              selectedVal === "known_well"
                                ? "bg-[#EFF6FF] border-secondary text-secondary font-semibold"
                                : "border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:border-secondary"
                            }`}
                          >
                            <span>Know Well</span>
                            <span className={`material-symbols-outlined text-sm check ${
                              selectedVal === "known_well" ? "opacity-100" : "opacity-0"
                            }`}>
                              check_circle
                            </span>
                          </button>
                          
                          <button
                            type="button"
                            onClick={() => handleSelectOption(q.concept_id, "somewhat_known")}
                            className={`quiz-btn w-full text-left p-3 rounded-lg border text-sm transition-all flex items-center justify-between focus:outline-none cursor-pointer ${
                              selectedVal === "somewhat_known"
                                ? "bg-[#EFF6FF] border-secondary text-secondary font-semibold"
                                : "border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:border-secondary"
                            }`}
                          >
                            <span>Somewhat Know</span>
                            <span className={`material-symbols-outlined text-sm check ${
                              selectedVal === "somewhat_known" ? "opacity-100" : "opacity-0"
                            }`}>
                              check_circle
                            </span>
                          </button>

                          <button
                            type="button"
                            onClick={() => handleSelectOption(q.concept_id, "unfamiliar")}
                            className={`quiz-btn w-full text-left p-3 rounded-lg border text-sm transition-all flex items-center justify-between focus:outline-none cursor-pointer ${
                              selectedVal === "unfamiliar"
                                ? "bg-[#EFF6FF] border-secondary text-secondary font-semibold"
                                : "border-outline-variant bg-surface-container-lowest text-on-surface-variant hover:border-secondary"
                            }`}
                          >
                            <span>Unfamiliar</span>
                            <span className={`material-symbols-outlined text-sm check ${
                              selectedVal === "unfamiliar" ? "opacity-100" : "opacity-0"
                            }`}>
                              check_circle
                            </span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="tonal-card bg-surface-container-lowest p-6 rounded-xl border border-[#E2E8F0] shadow-md text-center">
                <span className="material-symbols-outlined text-secondary text-4xl mb-2">check_circle</span>
                <h4 className="font-hanken font-bold text-base text-on-background">No Prerequisites Required</h4>
                <p className="text-xs text-on-surface-variant mt-2 leading-relaxed">
                  Your selected subject and topic flow seamlessly from scratch! We are ready to generate your curriculum plan.
                </p>
              </div>
            )}

            {/* Main Action buttons */}
            <div className="space-y-3">
              <button
                type="button"
                onClick={handleGeneratePlan}
                disabled={submitting}
                className="w-full bg-primary text-on-primary py-4 rounded-xl font-hanken font-bold text-sm hover:opacity-90 active:scale-[0.98] transition-all flex items-center justify-center gap-2 group cursor-pointer shadow-md disabled:opacity-50"
              >
                <span>Continue and Generate Plan</span>
                <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">
                  arrow_forward
                </span>
              </button>
              <Link
                href="/onboard"
                className="w-full py-4 rounded-xl font-hanken font-bold text-sm border border-outline-variant bg-white text-on-surface-variant hover:bg-surface-container-low transition-colors block text-center shadow-sm"
              >
                Back to Edit Onboarding
              </Link>
            </div>

            {/* intelligence counter */}
            <div className="flex items-center gap-3 p-4 bg-surface-container-low rounded-xl border border-outline-variant/40 shadow-inner">
              <div className="relative shrink-0">
                <span className="material-symbols-outlined text-secondary animate-pulse">hub</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-normal">
                Our AI engine is processing <span className="font-bold text-on-background">24,000+ textbook concepts</span> to tailor this learning pathway.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Success Loading Overlay */}
      {showOverlay && (
        <div className="fixed inset-0 z-[100] bg-[#0b1c30]/80 flex items-center justify-center p-6 transition-opacity duration-500 animate-fadeIn">
          <div className="bg-surface-container-lowest max-w-md w-full p-8 rounded-xl text-center shadow-2xl border border-outline-variant">
            <div className="mb-6 flex justify-center">
              <div className="h-20 w-20 rounded-full bg-surface-container-low flex items-center justify-center border border-secondary/20">
                <span className="material-symbols-outlined text-4xl text-secondary animate-spin">
                  auto_fix_high
                </span>
              </div>
            </div>
            <h2 className="font-hanken text-xl font-bold mb-2 text-on-background">Generating Your Flow</h2>
            <p className="text-sm text-on-surface-variant mb-6 leading-relaxed">
              Assembling the tailored roadmap for <span className="font-semibold">{query.onboarding.topic}</span> based on your comfort assessments.
            </p>
            
            {/* Pulsing Progress Bar */}
            <div className="h-2 w-full bg-surface-container rounded-full overflow-hidden mb-6">
              <div
                className="h-full bg-secondary rounded-full transition-all duration-300 ease-out"
                style={{ width: `${progressWidth}%` }}
              ></div>
            </div>
            <p className="text-xs text-outline font-semibold uppercase tracking-widest animate-pulse">
              Optimizing Pathways...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
