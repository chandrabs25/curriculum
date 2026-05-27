"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { fetchOptions, previewRetrieval } from "../services/api";
import { OptionResponse, OnboardingPayload } from "../types/curriculum";

export default function OnboardPage() {
  const router = useRouter();
  const [options, setOptions] = useState<OptionResponse | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search input & pre-fills
  const [topic, setTopic] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Advanced collapsible state
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Advanced Form states
  const [selectedSubject, setSelectedSubject] = useState("");
  const [selectedGrade, setSelectedGrade] = useState("");
  const [selectedChapter, setSelectedChapter] = useState("");
  const [currentLevel, setCurrentLevel] = useState("beginner");
  const [confidence, setConfidence] = useState("medium");
  const [learningGoal, setLearningGoal] = useState("");
  const [availableTime, setAvailableTime] = useState("3 hours/week");
  const [preferredStyle, setPreferredStyle] = useState("theoretical");
  const [deadlineOrPace, setDeadlineOrPace] = useState("self-paced");
  const [maxModules, setMaxModules] = useState(6);

  useEffect(() => {
    fetchOptions()
      .then((data) => {
        setOptions(data);
        if (data.subjects.length > 0) {
          setSelectedSubject(data.subjects[0]);
        }
        if (data.grades.length > 0) {
          setSelectedGrade(String(data.grades[0]));
        }
      })
      .catch((err) => {
        console.error("Options fetch error (running in mock/standalone mode):", err);
        // We will silently handle this so the page remains beautiful even if backend is offline
      })
      .finally(() => {
        setLoadingOptions(false);
      });
  }, []);

  // Filter chapters based on subject and grade
  const filteredChapters = options?.chapters.filter((ch) => {
    const matchSubject = !selectedSubject || ch.subject === selectedSubject;
    const matchGrade = !selectedGrade || String(ch.grade) === selectedGrade;
    return matchSubject && matchGrade;
  }) || [];

  // Update topic automatically when chapter changes
  const handleChapterChange = (chapterId: string) => {
    setSelectedChapter(chapterId);
    const chapter = options?.chapters.find((ch) => ch.id === chapterId);
    if (chapter) {
      setTopic(chapter.chapter_title);
      // Auto-focus and adjust height
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
      }
    }
  };

  const setQuery = (text: string) => {
    setTopic(text);
    if (textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) {
      setError("A description is required to generate your curriculum.");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    setSubmitting(true);
    setError(null);

    const onboarding: OnboardingPayload = {
      subject: selectedSubject,
      topic: topic,
      current_level: currentLevel,
      confidence: confidence,
      learning_goal: learningGoal || `Master ${topic}`,
      available_time: availableTime,
      preferred_learning_style: preferredStyle,
      deadline_or_pace: deadlineOrPace,
    };

    const queryPayload = {
      learner_id: "learner_" + Math.random().toString(36).substring(2, 7),
      onboarding,
      learner_state: [],
      prerequisite_check: null,
      subject: selectedSubject || null,
      grade: selectedGrade ? Number(selectedGrade) : null,
      chapter_id: selectedChapter || null,
      max_modules: maxModules,
      retrieval_limit: 12,
    };

    try {
      const previewData = await previewRetrieval(queryPayload);

      // Save preview and query payload to localStorage to bridge to preview page
      localStorage.setItem("curriculum-onboard-preview", JSON.stringify(previewData));
      localStorage.setItem("curriculum-onboard-query", JSON.stringify(queryPayload));
      
      router.push("/onboard/preview");
    } catch (err: any) {
      console.error(err);
      setError("Failed to build curriculum preview. Please describe your learning goal in more detail or ensure the backend is running.");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-background text-on-surface font-public min-h-screen">
      {/* Top Navigation */}
      <header className="bg-surface border-b border-outline-variant flex justify-between items-center w-full px-10 h-16 sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <span className="text-headline-md font-hanken font-bold text-primary">AcademicFlow</span>
        </div>
        <div className="flex items-center gap-4">
          <button className="material-symbols-outlined text-on-surface-variant p-2 hover:bg-surface-container rounded-full transition-all">
            notifications
          </button>
          <div className="w-8 h-8 rounded-full overflow-hidden border border-outline-variant">
            <img
              alt="User Profile"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDApUm4jLk55JM8lx7kM4XAjtc2yozXJc8gKsXkgDkODw7zYt9CjKa0BLUKDSCsT_OoK4MZ8OUoJF_VlRyb7cEW3lDe74nKson_zwjy0QtwSejgXG6cF-9NICkhXdRv1KNyMEkTjQHixaZZB0d6W2FClpouPwx5WRjvtbcVdC8He2YQdGgK6p8XEUiG5yBOHDFwwskJJ_TTtxM7k9h18RwGYaoxhHDx_wvV883bzZayXpQi_NX7ojHKvpiJuU2O5wQbWXM4acdZkdVr"
            />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-[800px] mx-auto px-4 md:px-0 py-12">
        {/* Error Banner */}
        {error && (
          <div className="mb-6 flex items-center gap-3 p-4 bg-error-container text-on-error-container rounded-xl border border-error/20" id="errorBanner">
            <span className="material-symbols-outlined text-error">error</span>
            <p className="font-hanken font-semibold text-sm">{error}</p>
            <button
              onClick={() => setError(null)}
              className="ml-auto material-symbols-outlined text-on-error-container/60 hover:text-on-error-container"
            >
              close
            </button>
          </div>
        )}

        {/* Headline */}
        <header className="mb-12 text-center max-w-2xl mx-auto">
          <h1 className="font-hanken text-4xl font-extrabold text-on-surface mb-4">
            Build Your Curriculum
          </h1>
          <p className="text-body-md text-on-surface-variant max-w-lg mx-auto">
            Describe what you want to master, and our AI will architect a personalized learning path for you.
          </p>
        </header>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="max-w-2xl mx-auto flex flex-col items-center gap-6" id="onboardingForm">
          <div className="w-full flex flex-col gap-3">
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-4 text-on-surface-variant">
                search
              </span>
              <textarea
                ref={textareaRef}
                value={topic}
                onChange={(e) => {
                  setTopic(e.target.value);
                  // Auto resize
                  e.target.style.height = "auto";
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                placeholder="What do you want to learn today? (e.g., Quantum Physics fundamentals)"
                className="w-full pl-12 pr-4 py-4 text-body-md rounded-2xl border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-secondary focus:border-secondary focus:bg-surface outline-none transition-all resize-none shadow-sm min-h-[60px] max-h-[120px]"
                rows={1}
              />
            </div>
            
            {/* Try Tags */}
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              <span className="text-xs font-semibold text-on-surface-variant/70 self-center mr-2 uppercase tracking-wider">
                Try:
              </span>
              <button
                type="button"
                onClick={() => setQuery("Machine Learning Foundations")}
                className="px-3 py-1 rounded-full border border-outline-variant bg-surface-container-low text-on-surface-variant text-xs hover:bg-surface-variant hover:border-secondary transition-all cursor-pointer"
              >
                Machine Learning
              </button>
              <button
                type="button"
                onClick={() => setQuery("Ancient Roman History")}
                className="px-3 py-1 rounded-full border border-outline-variant bg-surface-container-low text-on-surface-variant text-xs hover:bg-surface-variant hover:border-secondary transition-all cursor-pointer"
              >
                Roman History
              </button>
              <button
                type="button"
                onClick={() => setQuery("Advanced Organic Chemistry")}
                className="px-3 py-1 rounded-full border border-outline-variant bg-surface-container-low text-on-surface-variant text-xs hover:bg-surface-variant hover:border-secondary transition-all cursor-pointer"
              >
                Organic Chemistry
              </button>
            </div>
          </div>

          {/* Collapsible Configurations Section */}
          <div className="w-full border border-outline-variant bg-surface-container-lowest rounded-2xl overflow-hidden transition-all shadow-sm">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-surface-container-low transition-colors"
            >
              <div className="flex items-center gap-2 text-on-surface-variant">
                <span className="material-symbols-outlined">tune</span>
                <span className="font-hanken font-semibold text-sm">Textbook & Advanced Pacing Context</span>
              </div>
              <span className="material-symbols-outlined transition-transform duration-200" style={{ transform: showAdvanced ? "rotate(180deg)" : "rotate(0)" }}>
                expand_more
              </span>
            </button>

            {showAdvanced && (
              <div className="px-6 pb-6 pt-2 border-t border-outline-variant/60 space-y-5 bg-surface-container-lowest animate-fadeIn">
                {/* Subject and Grade Dropdowns */}
                {options && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                        Align with Subject
                      </label>
                      <select
                        value={selectedSubject}
                        onChange={(e) => {
                          setSelectedSubject(e.target.value);
                          setSelectedChapter("");
                        }}
                        className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                      >
                        <option value="">-- All Subjects --</option>
                        {options.subjects.map((sub) => (
                          <option key={sub} value={sub}>
                            {sub}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                        Grade / Class
                      </label>
                      <select
                        value={selectedGrade}
                        onChange={(e) => {
                          setSelectedGrade(e.target.value);
                          setSelectedChapter("");
                        }}
                        className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                      >
                        <option value="">-- All Grades --</option>
                        {options.grades.map((gr) => (
                          <option key={gr} value={gr}>
                            Grade {gr}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                {/* Chapter selection */}
                {options && (
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                      Reference Textbook Chapter
                    </label>
                    <select
                      value={selectedChapter}
                      onChange={(e) => handleChapterChange(e.target.value)}
                      className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                    >
                      <option value="">-- Use Custom Query Only --</option>
                      {filteredChapters.map((ch) => (
                        <option key={ch.id} value={ch.id}>
                          {ch.chapter_title} ({ch.subject} - Grade {ch.grade})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Learning style, Available time */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                      Current Knowledge Level
                    </label>
                    <select
                      value={currentLevel}
                      onChange={(e) => setCurrentLevel(e.target.value)}
                      className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                    >
                      <option value="beginner">Beginner (No background)</option>
                      <option value="intermediate">Intermediate (Some understanding)</option>
                      <option value="advanced">Advanced (Deep knowledge)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                      Confidence
                    </label>
                    <select
                      value={confidence}
                      onChange={(e) => setConfidence(e.target.value)}
                      className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                      Learning Style
                    </label>
                    <select
                      value={preferredStyle}
                      onChange={(e) => setPreferredStyle(e.target.value)}
                      className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                    >
                      <option value="theoretical">Theoretical & Conceptual</option>
                      <option value="practical">Practical & Problem-Solving</option>
                      <option value="summary-focused">Summary & Quick Notes</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                      Study Time Available
                    </label>
                    <input
                      type="text"
                      value={availableTime}
                      onChange={(e) => setAvailableTime(e.target.value)}
                      placeholder="e.g. 3 hours/week"
                      className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                      Target Pace or Deadline
                    </label>
                    <input
                      type="text"
                      value={deadlineOrPace}
                      onChange={(e) => setDeadlineOrPace(e.target.value)}
                      placeholder="e.g. 2 weeks, self-paced"
                      className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-on-surface-variant mb-1 uppercase tracking-wider">
                      Max Modules to Generate
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="15"
                      value={maxModules}
                      onChange={(e) => setMaxModules(Number(e.target.value))}
                      className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-secondary focus:ring-1 focus:ring-secondary focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Action Trigger Buttons */}
          <div className="flex flex-col items-center gap-4 w-full">
            <button
              type="submit"
              disabled={submitting}
              className="w-full sm:w-auto px-10 h-14 bg-primary text-on-primary font-hanken font-bold text-sm rounded-full hover:opacity-90 active:scale-95 transition-all shadow-md flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <span>{submitting ? "Analyzing Pathway..." : "Generate Curriculum"}</span>
              <span className="material-symbols-outlined">bolt</span>
            </button>
            <div className="flex items-center gap-2 text-on-surface-variant/70">
              <span className="material-symbols-outlined text-[16px]">info</span>
              <span className="text-xs italic">AI usually generates in 10-15 seconds.</span>
            </div>
          </div>
        </form>
      </main>

      <footer className="h-24"></footer>
    </div>
  );
}
