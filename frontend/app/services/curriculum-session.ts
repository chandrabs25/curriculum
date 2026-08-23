"use client";

import type {
  CurriculumPlanPayload,
  ExpandedCurriculumModulePayload,
  ModuleDesignPayload,
} from "../types/curriculum";
import {
  designModule,
  fetchCurriculumPlan,
  fetchModuleDesign,
  fetchOrDesignModule,
} from "./api";
import { getAccessToken, redirectToLogin } from "./auth";
import {
  loadGuestPlan,
  markGuestPlanPersisted,
  planForModuleDesign,
  storePendingModuleRoute,
} from "./guest-plan";

export type ModuleOpenMode = "fetch-or-design" | "fetch-only";

export interface ModuleWorkspaceRequest {
  planId: string;
  moduleId: string;
  returnTo: string;
  mode: ModuleOpenMode;
}

export type ModuleWorkspaceResult =
  | { kind: "ready"; plan: CurriculumPlanPayload; module: ExpandedCurriculumModulePayload }
  | { kind: "module-error"; plan: CurriculumPlanPayload; error: CurriculumSessionError }
  | { kind: "redirecting-to-login" };

export class CurriculumSessionError extends Error {
  stage: "authentication" | "plan" | "module";

  constructor(stage: CurriculumSessionError["stage"], message: string, cause?: unknown) {
    super(message, { cause });
    this.name = "CurriculumSessionError";
    this.stage = stage;
  }
}

export interface CurriculumSessionDependencies {
  getAccessToken(): Promise<string | null>;
  redirectToLogin(returnTo: string): void;
  storePendingModuleRoute(path: string): void;
  loadGuestPlan(planId: string): CurriculumPlanPayload | null;
  markGuestPlanPersisted(planId: string): void;
  planForModuleDesign(plan: CurriculumPlanPayload): CurriculumPlanPayload | undefined;
  fetchCurriculumPlan(planId: string, accessToken?: string): Promise<CurriculumPlanPayload>;
  fetchModuleDesign(planId: string, moduleId: string, accessToken?: string): Promise<ExpandedCurriculumModulePayload>;
  fetchOrDesignModule(payload: ModuleDesignPayload, accessToken?: string): Promise<ExpandedCurriculumModulePayload>;
  designModule(payload: ModuleDesignPayload, accessToken?: string): Promise<ExpandedCurriculumModulePayload>;
}

const defaultDependencies: CurriculumSessionDependencies = {
  getAccessToken,
  redirectToLogin,
  storePendingModuleRoute,
  loadGuestPlan,
  markGuestPlanPersisted,
  planForModuleDesign,
  fetchCurriculumPlan,
  fetchModuleDesign,
  fetchOrDesignModule,
  designModule,
};

export class CurriculumSession {
  private readonly moduleRequests = new Map<string, Promise<ModuleWorkspaceResult>>();

  constructor(private readonly dependencies: CurriculumSessionDependencies = defaultDependencies) {}

  async loadPlanForViewing(planId: string): Promise<{ plan: CurriculumPlanPayload; persisted: boolean }> {
    const localPlan = this.dependencies.loadGuestPlan(planId);
    if (localPlan) {
      return {
        plan: localPlan,
        persisted: this.dependencies.planForModuleDesign(localPlan) === undefined,
      };
    }
    try {
      return { plan: await this.dependencies.fetchCurriculumPlan(planId), persisted: true };
    } catch (error) {
      throw new CurriculumSessionError("plan", errorMessage(error, "Curriculum plan could not be loaded."), error);
    }
  }

  async openModule(request: ModuleWorkspaceRequest): Promise<ModuleWorkspaceResult> {
    const requestKey = [request.mode, request.planId, request.moduleId, request.returnTo].join("|");
    const existing = this.moduleRequests.get(requestKey);
    if (existing) return existing;
    const pending = this.openModuleOnce(request).finally(() => {
      if (this.moduleRequests.get(requestKey) === pending) {
        this.moduleRequests.delete(requestKey);
      }
    });
    this.moduleRequests.set(requestKey, pending);
    return pending;
  }

  private async openModuleOnce(request: ModuleWorkspaceRequest): Promise<ModuleWorkspaceResult> {
    const token = await this.requireAuthentication(request.returnTo);
    if (!token) return { kind: "redirecting-to-login" };

    const plan = await this.loadOwnedOrGuestPlan(request.planId, token);
    try {
      const moduleData = request.mode === "fetch-only"
        ? await this.dependencies.fetchModuleDesign(plan.curriculum_plan_id, request.moduleId, token)
        : await this.dependencies.fetchOrDesignModule(
            {
              curriculum_plan_id: plan.curriculum_plan_id,
              module_id: request.moduleId,
              plan: this.dependencies.planForModuleDesign(plan),
              learner_state: [],
            },
            token
          );
      if (request.mode === "fetch-or-design") {
        this.dependencies.markGuestPlanPersisted(plan.curriculum_plan_id);
      }
      return { kind: "ready", plan, module: moduleData };
    } catch (error) {
      return {
        kind: "module-error",
        plan,
        error: new CurriculumSessionError("module", errorMessage(error, "Module could not be loaded."), error),
      };
    }
  }

  async regenerateModule(plan: CurriculumPlanPayload, moduleId: string, returnTo: string): Promise<ExpandedCurriculumModulePayload | null> {
    const token = await this.requireAuthentication(returnTo);
    if (!token) return null;
    try {
      const moduleData = await this.dependencies.designModule(
        {
          curriculum_plan_id: plan.curriculum_plan_id,
          module_id: moduleId,
          plan: this.dependencies.planForModuleDesign(plan),
          learner_state: [],
          force_regenerate: true,
        },
        token
      );
      this.dependencies.markGuestPlanPersisted(plan.curriculum_plan_id);
      return moduleData;
    } catch (error) {
      throw new CurriculumSessionError("module", errorMessage(error, "Module could not be regenerated."), error);
    }
  }

  private async requireAuthentication(returnTo: string): Promise<string | null> {
    let token: string | null;
    try {
      token = await this.dependencies.getAccessToken();
    } catch (error) {
      throw new CurriculumSessionError("authentication", errorMessage(error, "Authentication could not be verified."), error);
    }
    if (!token) {
      this.dependencies.storePendingModuleRoute(returnTo);
      this.dependencies.redirectToLogin(returnTo);
      return null;
    }
    return token;
  }

  private async loadOwnedOrGuestPlan(planId: string, accessToken: string): Promise<CurriculumPlanPayload> {
    const localPlan = this.dependencies.loadGuestPlan(planId);
    if (localPlan) return localPlan;
    try {
      return await this.dependencies.fetchCurriculumPlan(planId, accessToken);
    } catch (error) {
      throw new CurriculumSessionError("plan", errorMessage(error, "Curriculum plan could not be loaded."), error);
    }
  }
}

export const curriculumSession = new CurriculumSession();

export function moduleHref(planId: string, moduleId: string): string {
  return `/plan/${encodeURIComponent(planId)}/module/${encodeURIComponent(moduleId)}`;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
