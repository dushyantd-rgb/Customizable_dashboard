import { PUBLIC_SERVICE_DEFAULTS } from "@growthbyte/config";
import type {
  ClientDetails,
  ClientSummary,
  ColumnMappingInput,
  GoogleSheetConfigInput,
  GoogleSyncResult,
  KnowledgeCreate,
  KnowledgeRecord,
  KnowledgeUpdate,
  KpiCreate,
  KpiRecord,
  KpiUpdate,
  MetaAccountDiscoveryResponse,
  MetaConnectionInput,
  MetaSyncInput,
  MetaSyncResult,
  SafeErrorDetail,
  SafeErrorResponse,
  SpreadsheetSummary,
  StatusMappingInput,
  SyncRunSummary,
  WorksheetSummary,
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

function metaPath(clientId: string): string {
  return `/integrations/meta/clients/${encodeURIComponent(clientId)}`;
}

function googlePath(clientId: string): string {
  return `/integrations/google/clients/${encodeURIComponent(clientId)}`;
}

export function googleOAuthUrl(clientId: string): string {
  return `${apiBaseUrl}${googlePath(clientId)}/oauth/start`;
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
  listMetaAccounts: (clientId: string) =>
    apiRequest<MetaAccountDiscoveryResponse>(`${metaPath(clientId)}/accounts`),
  configureMeta: (clientId: string, input: MetaConnectionInput) =>
    apiRequest<{ connection_id: string; external_account_id: string; display_name: string | null }>(
      `${metaPath(clientId)}/config`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
    ),
  testMeta: (clientId: string) =>
    apiRequest<{ connected: boolean }>(`${metaPath(clientId)}/test`, { method: "POST" }),
  syncMeta: (clientId: string, input: MetaSyncInput) =>
    apiRequest<MetaSyncResult>(`${metaPath(clientId)}/sync`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  listMetaSyncRuns: (clientId: string) =>
    apiRequest<SyncRunSummary[]>(`${metaPath(clientId)}/sync-runs`),
  listGoogleSpreadsheets: (clientId: string) =>
    apiRequest<SpreadsheetSummary[]>(`${googlePath(clientId)}/spreadsheets`),
  listGoogleWorksheets: (clientId: string, spreadsheetId: string) =>
    apiRequest<WorksheetSummary[]>(
      `${googlePath(clientId)}/spreadsheets/${encodeURIComponent(spreadsheetId)}/worksheets`,
    ),
  previewGoogleSheet: (
    clientId: string,
    spreadsheetId: string,
    worksheetName: string,
    headerRow: number,
    dataStartRow: number,
  ) =>
    apiRequest<{ headers: string[] }>(
      `${googlePath(clientId)}/spreadsheets/${encodeURIComponent(
        spreadsheetId,
      )}/worksheets/${encodeURIComponent(
        worksheetName,
      )}/preview?header_row=${headerRow}&data_start_row=${dataStartRow}`,
    ),
  configureGoogleSheet: (clientId: string, input: GoogleSheetConfigInput) =>
    apiRequest<{ config_id: string }>(`${googlePath(clientId)}/config`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  saveGoogleColumnMappings: (
    clientId: string,
    configId: string,
    mappings: readonly ColumnMappingInput[],
  ) =>
    apiRequest<{ mappings_saved: number }>(
      `${googlePath(clientId)}/config/${encodeURIComponent(configId)}/column-mappings`,
      { method: "POST", body: JSON.stringify(mappings) },
    ),
  saveGoogleStatusMappings: (
    clientId: string,
    configId: string,
    mappings: readonly StatusMappingInput[],
  ) =>
    apiRequest<{ mappings_saved: number }>(
      `${googlePath(clientId)}/config/${encodeURIComponent(configId)}/status-mappings`,
      { method: "POST", body: JSON.stringify(mappings) },
    ),
  testGoogle: (clientId: string) =>
    apiRequest<{ connected: boolean }>(`${googlePath(clientId)}/test`, { method: "POST" }),
  syncGoogle: (clientId: string) =>
    apiRequest<GoogleSyncResult>(`${googlePath(clientId)}/sync`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  listGoogleSyncRuns: (clientId: string) =>
    apiRequest<SyncRunSummary[]>(`${googlePath(clientId)}/sync-runs`),
  // Matching endpoints
  runNormalisation: (clientId: string, syncRunId?: string) =>
    apiRequest<{ normalised: number; skipped: number }>(
      `/matching/normalise?client_id=${encodeURIComponent(clientId)}`,
      { method: "POST", body: JSON.stringify({ sync_run_id: syncRunId }) }
    ),
  runMatching: (clientId: string) =>
    apiRequest<{ matched: number; ambiguous: number; unmatched: number }>(
      `/matching/match?client_id=${encodeURIComponent(clientId)}`,
      { method: "POST", body: JSON.stringify({}) }
    ),
  listUnmatchedLeads: (clientId: string, limit = 100) =>
    apiRequest<unknown[]>(`/matching/leads/unmatched?client_id=${encodeURIComponent(clientId)}&limit=${limit}`),
  listAmbiguousLeads: (clientId: string, limit = 100) =>
    apiRequest<unknown[]>(`/matching/leads/ambiguous?client_id=${encodeURIComponent(clientId)}&limit=${limit}`),
  // Metrics endpoints
  getMetrics: (clientId: string, periodStart: string, periodEnd: string, attributionLevel = "client") =>
    apiRequest<unknown>(
      `/metrics?client_id=${encodeURIComponent(clientId)}&period_start=${periodStart}&period_end=${periodEnd}&attribution_level=${attributionLevel}`
    ),
  generateSnapshot: (clientId: string, periodStart: string, periodEnd: string, attributionLevels = ["client"]) =>
    apiRequest<{ snapshot_count: number; snapshots: string[] }>(
      `/metrics/snapshots?client_id=${encodeURIComponent(clientId)}`,
      { method: "POST", body: JSON.stringify({ period_start: periodStart, period_end: periodEnd, attribution_levels: attributionLevels }) }
    ),
  listSnapshots: (clientId: string, periodStart?: string, periodEnd?: string) => {
    const params = new URLSearchParams({ client_id: clientId });
    if (periodStart) params.append("period_start", periodStart);
    if (periodEnd) params.append("period_end", periodEnd);
    return apiRequest<unknown[]>(`/metrics/snapshots?${params.toString()}`);
  },
  getSnapshot: (clientId: string, snapshotId: string) =>
    apiRequest<unknown>(`/metrics/snapshots/${encodeURIComponent(snapshotId)}?client_id=${encodeURIComponent(clientId)}`),
};
