"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CurriculumPlanPayload, ExpandedCurriculumModulePayload } from "../types/curriculum";
import {
  curriculumSession,
  CurriculumSessionError,
  type ModuleOpenMode,
} from "../services/curriculum-session";

interface ModuleWorkspaceOptions {
  planId: string;
  moduleId: string;
  returnTo: string;
  mode: ModuleOpenMode;
  fallbackError: string;
}

export function useModuleWorkspace(options: ModuleWorkspaceOptions) {
  const { planId, moduleId, returnTo, mode, fallbackError } = options;
  const [plan, setPlan] = useState<CurriculumPlanPayload | null>(null);
  const [moduleData, setModuleData] = useState<ExpandedCurriculumModulePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorStage, setErrorStage] = useState<CurriculumSessionError["stage"] | null>(null);
  const requestSequence = useRef(0);

  const load = useCallback(async (retry: boolean) => {
    const sequence = ++requestSequence.current;
    if (retry) setRetrying(true);
    else {
      setLoading(true);
      setPlan(null);
      setModuleData(null);
    }
    setError(null);
    setErrorStage(null);
    let redirecting = false;
    try {
      const result = await curriculumSession.openModule({ planId, moduleId, returnTo, mode });
      if (sequence !== requestSequence.current) return;
      if (result.kind === "redirecting-to-login") {
        redirecting = true;
        return;
      }
      setPlan(result.plan);
      if (result.kind === "module-error") {
        setError(result.error.message);
        setErrorStage(result.error.stage);
        return;
      }
      setModuleData(result.module);
    } catch (caught) {
      if (sequence !== requestSequence.current) return;
      console.error(caught);
      setError(caught instanceof Error && caught.message ? caught.message : fallbackError);
      setErrorStage(caught instanceof CurriculumSessionError ? caught.stage : "module");
    } finally {
      if (!redirecting && sequence === requestSequence.current) {
        setLoading(false);
        setRetrying(false);
      }
    }
  }, [fallbackError, mode, moduleId, planId, returnTo]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(false), 0);
    return () => {
      window.clearTimeout(timer);
      requestSequence.current += 1;
    };
  }, [load]);

  return {
    plan,
    moduleData,
    loading,
    retrying,
    error,
    errorStage,
    retry: () => load(true),
  };
}
