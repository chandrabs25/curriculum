import type {
  CheckpointResultPayload,
  CheckpointSubmitPayload,
  CurriculumPlanSummary,
  CurriculumPlanPayload,
  CurriculumProgressPayload,
  CurriculumQueryPayload,
  ExpandedCurriculumModulePayload,
  HealthResponse,
  IntentClassificationResponse,
  IntentClassifyPayload,
  ModuleDesignPayload,
  OptionsResponse,
  RetrievalPreviewResponse,
  SectionLearningInsight,
  UserProfilePayload,
} from "../types/curriculum";
import { getAccessToken, redirectToLogin } from "./auth";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function requestJson<TResponse>(
  path: string,
  init?: RequestInit,
  options?: { auth?: boolean; accessToken?: string }
): Promise<TResponse> {
  const authHeaders: Record<string, string> = {};
  if (options?.auth) {
    const token = options.accessToken || await getAccessToken();
    if (!token) {
      redirectToLogin();
      throw new ApiError("Sign in required.", 401, { detail: "Sign in required." });
    }
    authHeaders.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...init?.headers,
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const body: unknown = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    if (options?.auth && response.status === 401) {
      redirectToLogin();
    }
    throw new ApiError(apiErrorMessage(body, response), response.status, body);
  }

  return body as TResponse;
}

function postJson<TPayload, TResponse>(
  path: string,
  payload: TPayload,
  options?: { auth?: boolean; accessToken?: string }
): Promise<TResponse> {
  return requestJson<TResponse>(path, {
    method: "POST",
    body: JSON.stringify(payload),
  }, options);
}

function apiErrorMessage(body: unknown, response: Response): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    return typeof detail === "string"
      ? detail
      : `Request failed with status ${response.status}`;
  }
  if (typeof body === "string" && body.trim()) {
    return body;
  }
  return `Request failed with status ${response.status}`;
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}

export function fetchOptions(): Promise<OptionsResponse> {
  return requestJson<OptionsResponse>("/api/options");
}

export function classifyIntent(
  payload: IntentClassifyPayload
): Promise<IntentClassificationResponse> {
  return postJson<IntentClassifyPayload, IntentClassificationResponse>(
    "/api/intent/classify",
    payload
  );
}

export function previewRetrieval(
  payload: CurriculumQueryPayload
): Promise<RetrievalPreviewResponse> {
  return postJson<CurriculumQueryPayload, RetrievalPreviewResponse>(
    "/api/retrieval/preview",
    payload
  );
}

export function createCurriculumPlan(
  payload: CurriculumQueryPayload
): Promise<CurriculumPlanPayload> {
  return postJson<CurriculumQueryPayload, CurriculumPlanPayload>(
    "/api/curriculum/plan",
    payload
  );
}

export function fetchCurriculumPlan(
  curriculumPlanId: string,
  accessToken?: string
): Promise<CurriculumPlanPayload> {
  return requestJson<CurriculumPlanPayload>(
    `/api/curriculum/plans/${encodeURIComponent(curriculumPlanId)}`,
    undefined,
    { auth: true, accessToken }
  );
}

export function designModule(
  payload: ModuleDesignPayload,
  accessToken?: string
): Promise<ExpandedCurriculumModulePayload> {
  return postJson<ModuleDesignPayload, ExpandedCurriculumModulePayload>(
    "/api/modules/design",
    payload,
    { auth: true, accessToken }
  );
}

export function fetchModuleDesign(
  curriculumPlanId: string,
  moduleId: string,
  accessToken?: string
): Promise<ExpandedCurriculumModulePayload> {
  return requestJson<ExpandedCurriculumModulePayload>(
    `/api/curriculum/plans/${encodeURIComponent(curriculumPlanId)}/modules/${encodeURIComponent(moduleId)}/design`,
    undefined,
    { auth: true, accessToken }
  );
}

export async function fetchOrDesignModule(
  payload: ModuleDesignPayload,
  accessToken?: string
): Promise<ExpandedCurriculumModulePayload> {
  try {
    return await fetchModuleDesign(payload.curriculum_plan_id, payload.module_id, accessToken);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) {
      throw error;
    }
  }
  return designModule(payload, accessToken);
}

export function submitCheckpoint(
  payload: CheckpointSubmitPayload
): Promise<CheckpointResultPayload> {
  return postJson<CheckpointSubmitPayload, CheckpointResultPayload>(
    "/api/checkpoints/submit",
    payload,
    { auth: true }
  );
}

export function fetchLatestCheckpointResult(
  curriculumPlanId: string,
  moduleId: string
): Promise<CheckpointResultPayload> {
  return requestJson<CheckpointResultPayload>(
    `/api/curriculum/plans/${encodeURIComponent(curriculumPlanId)}/modules/${encodeURIComponent(moduleId)}/checkpoint/latest`,
    undefined,
    { auth: true }
  );
}

export function fetchCurriculumProgress(
  curriculumPlanId: string
): Promise<CurriculumProgressPayload> {
  return requestJson<CurriculumProgressPayload>(
    `/api/curriculum/plans/${encodeURIComponent(curriculumPlanId)}/progress`,
    undefined,
    { auth: true }
  );
}

export function fetchLearnerPlans(
  limit = 20
): Promise<{ plans: CurriculumPlanSummary[] }> {
  return requestJson<{ plans: CurriculumPlanSummary[] }>(
    `/api/me/plans?limit=${encodeURIComponent(String(limit))}`,
    undefined,
    { auth: true }
  );
}

export function fetchMyProfile(): Promise<{ profile: UserProfilePayload }> {
  return requestJson<{ profile: UserProfilePayload }>(
    "/api/me/profile",
    undefined,
    { auth: true }
  );
}

export function fetchLatestSectionInsights(
  sectionIds: string[]
): Promise<{ section_insights: SectionLearningInsight[] }> {
  const ids = sectionIds.join(",");
  return requestJson<{ section_insights: SectionLearningInsight[] }>(
    `/api/me/section-insights?section_ids=${encodeURIComponent(ids)}`,
    undefined,
    { auth: true }
  );
}
