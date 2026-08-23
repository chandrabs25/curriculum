import { describe, expect, it, vi } from "vitest";
import type { CurriculumPlanPayload, ExpandedCurriculumModulePayload } from "../types/curriculum";
import {
  CurriculumSession,
  type CurriculumSessionDependencies,
} from "./curriculum-session";


function plan(): CurriculumPlanPayload {
  return {
    curriculum_plan_id: "plan:1",
    learner_id: "guest",
    onboarding: {
      subject: "physics",
      topic: "gravity",
      current_level: "",
      confidence: "",
      learning_goal: "",
      available_time: "",
      preferred_learning_style: "",
      deadline_or_pace: "",
    },
    modules: [],
    metadata: {},
  };
}

function moduleDesign(): ExpandedCurriculumModulePayload {
  return {
    module_id: "module:1",
    title: "Gravity",
    module_goal: "Understand gravity.",
    source_section_ids: ["section:1"],
    concept_ids: ["concept:gravity"],
    larger_goal_alignment: "Explains the learning goal.",
    transition_from_previous: "",
    transition_to_next: "",
    lesson_sections: [],
    guided_activity: "Compare two falling objects.",
    common_misconceptions: [],
    checkpoint_mcqs: [],
    metadata: { source_mode: "summary" },
  };
}

function dependencies(overrides: Partial<CurriculumSessionDependencies> = {}): CurriculumSessionDependencies {
  return {
    getAccessToken: vi.fn().mockResolvedValue("access-token"),
    redirectToLogin: vi.fn(),
    storePendingModuleRoute: vi.fn(),
    loadGuestPlan: vi.fn().mockReturnValue(plan()),
    markGuestPlanPersisted: vi.fn(),
    planForModuleDesign: vi.fn().mockImplementation((value) => value),
    fetchCurriculumPlan: vi.fn().mockResolvedValue(plan()),
    fetchModuleDesign: vi.fn().mockResolvedValue(moduleDesign()),
    fetchOrDesignModule: vi.fn().mockResolvedValue(moduleDesign()),
    designModule: vi.fn().mockResolvedValue(moduleDesign()),
    ...overrides,
  };
}

describe("CurriculumSession", () => {
  it("redirects before loading or claiming a module when authentication is absent", async () => {
    const deps = dependencies({ getAccessToken: vi.fn().mockResolvedValue(null) });
    const session = new CurriculumSession(deps);

    const result = await session.openModule({
      planId: "plan:1",
      moduleId: "module:1",
      returnTo: "/plan/plan%3A1/module/module%3A1",
      mode: "fetch-or-design",
    });

    expect(result).toEqual({ kind: "redirecting-to-login" });
    expect(deps.storePendingModuleRoute).toHaveBeenCalledWith("/plan/plan%3A1/module/module%3A1");
    expect(deps.redirectToLogin).toHaveBeenCalledWith("/plan/plan%3A1/module/module%3A1");
    expect(deps.fetchOrDesignModule).not.toHaveBeenCalled();
  });

  it("claims a guest plan through fetch-or-design and marks it persisted", async () => {
    const guestPlan = plan();
    const deps = dependencies({ loadGuestPlan: vi.fn().mockReturnValue(guestPlan) });
    const session = new CurriculumSession(deps);

    const result = await session.openModule({
      planId: "plan:1",
      moduleId: "module:1",
      returnTo: "/module",
      mode: "fetch-or-design",
    });

    expect(result.kind).toBe("ready");
    expect(deps.fetchOrDesignModule).toHaveBeenCalledWith(
      expect.objectContaining({ curriculum_plan_id: "plan:1", module_id: "module:1", plan: guestPlan }),
      "access-token"
    );
    expect(deps.markGuestPlanPersisted).toHaveBeenCalledWith("plan:1");
  });

  it("deduplicates concurrent module opens for the same route", async () => {
    let resolveModule: ((value: ExpandedCurriculumModulePayload) => void) | undefined;
    const pendingModule = new Promise<ExpandedCurriculumModulePayload>((resolve) => {
      resolveModule = resolve;
    });
    const deps = dependencies({ fetchOrDesignModule: vi.fn().mockReturnValue(pendingModule) });
    const session = new CurriculumSession(deps);
    const request = {
      planId: "plan:1",
      moduleId: "module:1",
      returnTo: "/module",
      mode: "fetch-or-design" as const,
    };

    const first = session.openModule(request);
    const second = session.openModule(request);
    resolveModule?.(moduleDesign());
    await Promise.all([first, second]);

    expect(deps.fetchOrDesignModule).toHaveBeenCalledTimes(1);
    expect(deps.markGuestPlanPersisted).toHaveBeenCalledTimes(1);
  });

  it("uses fetch-only mode for results without generating or marking a plan", async () => {
    const deps = dependencies();
    const session = new CurriculumSession(deps);

    const result = await session.openModule({
      planId: "plan:1",
      moduleId: "module:1",
      returnTo: "/results",
      mode: "fetch-only",
    });

    expect(result.kind).toBe("ready");
    expect(deps.fetchModuleDesign).toHaveBeenCalledWith("plan:1", "module:1", "access-token");
    expect(deps.fetchOrDesignModule).not.toHaveBeenCalled();
    expect(deps.markGuestPlanPersisted).not.toHaveBeenCalled();
  });

  it("retains the resolved plan when module loading fails", async () => {
    const deps = dependencies({
      fetchModuleDesign: vi.fn().mockRejectedValue(new Error("module unavailable")),
    });
    const session = new CurriculumSession(deps);

    const result = await session.openModule({
      planId: "plan:1",
      moduleId: "module:1",
      returnTo: "/results",
      mode: "fetch-only",
    });

    expect(result.kind).toBe("module-error");
    if (result.kind === "module-error") {
      expect(result.plan.curriculum_plan_id).toBe("plan:1");
      expect(result.error.message).toBe("module unavailable");
    }
  });

  it("reports whether a viewable local plan has already been persisted", async () => {
    const deps = dependencies({ planForModuleDesign: vi.fn().mockReturnValue(undefined) });
    const session = new CurriculumSession(deps);

    const result = await session.loadPlanForViewing("plan:1");

    expect(result.persisted).toBe(true);
    expect(result.plan.curriculum_plan_id).toBe("plan:1");
  });
});
