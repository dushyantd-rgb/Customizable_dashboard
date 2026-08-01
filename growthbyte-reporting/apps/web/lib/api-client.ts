import { PUBLIC_SERVICE_DEFAULTS } from "@growthbyte/config";
import type {
  ClientDetails,
  ClientSummary,
  KnowledgeCreate,
  KnowledgeRecord,
  KnowledgeUpdate,
  KpiCreate,
  KpiRecord,
  KpiUpdate,
  SafeErrorDetail,
  SafeErrorResponse,
} from "@growthbyte/shared-types";

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL ?? PUBLIC_SERVICE_DEFAULTS.apiUrl).replace(
  /\/+$/,
  "",
);
const genericErrorMessage = "The request could not be completed. Please try again.";

export class SafeApiError extends Error {
  readonly code: string;
  readonly details: readonly SafeErrorDetail[];

  constructor(code: string, message: string, details: readonly SafeErrorDetail[] = []) {
    super(message);
    this.name = "SafeApiError";
    this.code = code;
    this.details = details;
  }
}

function isSafeErrorResponse(value: unknown): value is SafeErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = value.error;
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string" &&
    error.code.length <= 100 &&
    error.message.length <= 300
  );
}

async function decodeJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  const payload = await decodeJson(response);
  if (!response.ok) {
    if (isSafeErrorResponse(payload)) {
      throw new SafeApiError(
        payload.error.code,
        payload.error.message,
        payload.error.details ?? [],
      );
    }
    throw new SafeApiError("request_failed", genericErrorMessage);
  }
  return payload as T;
}

export function safeErrorMessage(error: unknown): string {
  return error instanceof SafeApiError ? error.message : genericErrorMessage;
}

function clientPath(clientId: string): string {
  return `/clients/${encodeURIComponent(clientId)}`;
}

export const api = {
  listClients: () => apiRequest<ClientSummary[]>("/clients"),
  getClient: (clientId: string) => apiRequest<ClientDetails>(clientPath(clientId)),
  listKnowledge: (clientId: string) =>
    apiRequest<KnowledgeRecord[]>(`${clientPath(clientId)}/knowledge`),
  createKnowledge: (clientId: string, input: KnowledgeCreate) =>
    apiRequest<KnowledgeRecord>(`${clientPath(clientId)}/knowledge`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  updateKnowledge: (clientId: string, knowledgeId: string, input: KnowledgeUpdate) =>
    apiRequest<KnowledgeRecord>(
      `${clientPath(clientId)}/knowledge/${encodeURIComponent(knowledgeId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
    ),
  listKpis: (clientId: string) => apiRequest<KpiRecord[]>(`${clientPath(clientId)}/kpis`),
  createKpi: (clientId: string, input: KpiCreate) =>
    apiRequest<KpiRecord>(`${clientPath(clientId)}/kpis`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  updateKpi: (clientId: string, kpiId: string, input: KpiUpdate) =>
    apiRequest<KpiRecord>(`${clientPath(clientId)}/kpis/${encodeURIComponent(kpiId)}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),
};
