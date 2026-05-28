import type {
  CheckpointResultPayload,
  CheckpointSubmitPayload,
  CurriculumPlanPayload,
  CurriculumQueryPayload,
  ExpandedCurriculumModulePayload,
  HealthResponse,
  IntentClassificationResponse,
  IntentClassifyPayload,
  ModuleDesignPayload,
  OptionsResponse,
  RetrievalPreviewResponse,
} from "../types/curriculum";

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
  init?: RequestInit
): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const body: unknown = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    throw new ApiError(apiErrorMessage(body, response), response.status, body);
  }

  return body as TResponse;
}

function postJson<TPayload, TResponse>(
  path: string,
  payload: TPayload
): Promise<TResponse> {
  return requestJson<TResponse>(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
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

export function designModule(
  payload: ModuleDesignPayload
): Promise<ExpandedCurriculumModulePayload> {
  return postJson<ModuleDesignPayload, ExpandedCurriculumModulePayload>(
    "/api/modules/design",
    payload
  );
}

export function submitCheckpoint(
  payload: CheckpointSubmitPayload
): Promise<CheckpointResultPayload> {
  return postJson<CheckpointSubmitPayload, CheckpointResultPayload>(
    "/api/checkpoints/submit",
    payload
  );
}
