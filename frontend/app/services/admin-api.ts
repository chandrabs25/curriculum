import type {
  AdminDashboard,
  CheckpointAnalytics,
  ContentStats,
  HotspotRow,
  HotspotStatusPayload,
  LearnerDetail,
  PaginatedHotspots,
  PaginatedLearners,
} from "../types/admin";
import { getAccessToken, redirectToLogin } from "./auth";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

class AdminApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AdminApiError";
    this.status = status;
  }
}

async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  if (!token) {
    redirectToLogin();
    throw new AdminApiError("Sign in required.", 401);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const body: unknown = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    if (response.status === 401) redirectToLogin();
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail?: unknown }).detail)
        : `Request failed: ${response.status}`;
    throw new AdminApiError(detail, response.status);
  }

  return body as T;
}

// -- Admin check -----------------------------------------------------------

export async function checkAdminAccess(): Promise<boolean> {
  try {
    await adminRequest<{ ok: boolean }>("/api/admin/check");
    return true;
  } catch {
    return false;
  }
}

// -- Dashboard -------------------------------------------------------------

export function fetchAdminDashboard(): Promise<AdminDashboard> {
  return adminRequest<AdminDashboard>("/api/admin/dashboard");
}

// -- Learners --------------------------------------------------------------

export function fetchAdminLearners(params?: {
  limit?: number;
  offset?: number;
  search?: string;
}): Promise<PaginatedLearners> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  if (params?.search) qs.set("search", params.search);
  const query = qs.toString();
  return adminRequest<PaginatedLearners>(
    `/api/admin/learners${query ? `?${query}` : ""}`
  );
}

export function fetchAdminLearnerDetail(
  userId: string
): Promise<LearnerDetail> {
  return adminRequest<LearnerDetail>(
    `/api/admin/learners/${encodeURIComponent(userId)}`
  );
}

// -- Hotspots --------------------------------------------------------------

export function fetchAdminHotspots(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<PaginatedHotspots> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return adminRequest<PaginatedHotspots>(
    `/api/admin/hotspots${query ? `?${query}` : ""}`
  );
}

export function fetchAdminHotspot(hotspotId: string): Promise<HotspotRow> {
  return adminRequest<HotspotRow>(
    `/api/admin/hotspots/${encodeURIComponent(hotspotId)}`
  );
}

export function updateAdminHotspot(
  hotspotId: string,
  payload: HotspotStatusPayload
): Promise<HotspotRow> {
  return adminRequest<HotspotRow>(
    `/api/admin/hotspots/${encodeURIComponent(hotspotId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    }
  );
}

// -- Content ---------------------------------------------------------------

export function fetchAdminContentStats(): Promise<ContentStats> {
  return adminRequest<ContentStats>("/api/admin/content/stats");
}

export function fetchAdminCheckpointAnalytics(): Promise<CheckpointAnalytics> {
  return adminRequest<CheckpointAnalytics>("/api/admin/checkpoint-analytics");
}
