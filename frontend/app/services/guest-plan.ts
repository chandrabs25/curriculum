"use client";

import type { CurriculumPlanPayload } from "../types/curriculum";

export const PENDING_MODULE_ROUTE_KEY = "curriculum-pending-module-route";

function planKey(planId: string): string {
  return `curriculum-plan-${planId}`;
}

function persistedKey(planId: string): string {
  return `curriculum-plan-persisted-${planId}`;
}

export function saveGuestPlan(plan: CurriculumPlanPayload): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(planKey(plan.curriculum_plan_id), JSON.stringify(plan));
  localStorage.setItem("curriculum-current-plan-id", plan.curriculum_plan_id);
}

export function loadGuestPlan(planId: string): CurriculumPlanPayload | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(planKey(planId));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CurriculumPlanPayload;
  } catch {
    localStorage.removeItem(planKey(planId));
    return null;
  }
}

export function markGuestPlanPersisted(planId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(persistedKey(planId), "1");
}

export function isGuestPlanPersisted(planId: string): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(persistedKey(planId)) === "1";
}

export function planForModuleDesign(plan: CurriculumPlanPayload): CurriculumPlanPayload | undefined {
  return isGuestPlanPersisted(plan.curriculum_plan_id) ? undefined : plan;
}

export function storePendingModuleRoute(path: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(PENDING_MODULE_ROUTE_KEY, path);
  sessionStorage.setItem("curriculum-auth-return-to", path);
}

export function popPendingModuleRoute(): string | null {
  if (typeof window === "undefined") return null;
  const route = sessionStorage.getItem(PENDING_MODULE_ROUTE_KEY);
  if (route) {
    sessionStorage.removeItem(PENDING_MODULE_ROUTE_KEY);
  }
  return route;
}
