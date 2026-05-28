import type { ExpandedCurriculumModulePayload } from "../types/curriculum";

export function readCachedModuleDesign(
  planId: string,
  moduleId: string
): ExpandedCurriculumModulePayload | null {
  if (typeof window === "undefined") return null;
  for (const key of moduleDesignStorageKeys(planId, moduleId)) {
    const raw = localStorage.getItem(key);
    if (!raw) continue;
    try {
      return JSON.parse(raw) as ExpandedCurriculumModulePayload;
    } catch {
      localStorage.removeItem(key);
    }
  }
  return null;
}

export function writeCachedModuleDesign(
  planId: string,
  moduleId: string,
  moduleDesign: ExpandedCurriculumModulePayload
): void {
  if (typeof window === "undefined") return;
  const serialized = JSON.stringify(moduleDesign);
  for (const key of moduleDesignStorageKeys(planId, moduleId)) {
    localStorage.setItem(key, serialized);
  }
}

function moduleDesignStorageKeys(planId: string, moduleId: string): string[] {
  const decodedKey = `curriculum-module-design-${planId}-${moduleId}`;
  const encodedKey = `curriculum-module-design-${encodeURIComponent(planId)}-${encodeURIComponent(moduleId)}`;
  return decodedKey === encodedKey ? [decodedKey] : [decodedKey, encodedKey];
}
