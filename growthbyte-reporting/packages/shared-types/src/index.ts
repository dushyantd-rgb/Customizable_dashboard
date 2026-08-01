export type HealthStatus = "ok" | "ready";

export interface ServiceHealth {
  readonly service: "api" | "mcp" | "web";
  readonly status: HealthStatus;
  readonly version: string;
}

export type JsonPrimitive = boolean | number | string | null;
export type JsonValue = JsonPrimitive | JsonObject | readonly JsonValue[];

export interface JsonObject {
  readonly [key: string]: JsonValue;
}

export interface ClientSummary {
  readonly id: string;
  readonly name: string;
  readonly slug: string;
  readonly status: string;
}

export interface ClientDetails extends ClientSummary {
  readonly reporting_timezone: string;
  readonly default_currency: string;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface KnowledgeRecord {
  readonly id: string;
  readonly client_id: string;
  readonly category: string;
  readonly knowledge_key: string;
  readonly value: JsonObject;
  readonly status: string;
  readonly source_type: string;
  readonly source_identifier: string | null;
  readonly source_display_name: string | null;
  readonly source_reference: string | null;
  readonly source_version: string | null;
  readonly imported_at: string | null;
  readonly version: number;
  readonly approved_by_label: string | null;
  readonly approved_at: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface KnowledgeCreate {
  category: string;
  knowledge_key: string;
  value: JsonObject;
  status: string;
}

export interface KnowledgeUpdate {
  category?: string;
  knowledge_key?: string;
  value?: JsonObject;
  status?: string;
}

export interface KpiRecord {
  readonly id: string;
  readonly client_id: string;
  readonly metric_key: string;
  readonly label: string;
  readonly target_value: string | null;
  readonly unit: string;
  readonly direction: string;
  readonly attribution_level: string;
  readonly active_from: string;
  readonly active_to: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface KpiCreate {
  metric_key: string;
  label: string;
  target_value: string | null;
  unit: string;
  direction: string;
  attribution_level: string;
  active_from: string;
  active_to: string | null;
}

export interface KpiUpdate {
  metric_key?: string;
  label?: string;
  target_value?: string | null;
  unit?: string;
  direction?: string;
  attribution_level?: string;
  active_from?: string;
  active_to?: string | null;
}

export interface SafeErrorDetail {
  readonly location: readonly (number | string)[];
  readonly code: string;
  readonly message: string;
}

export interface SafeErrorBody {
  readonly code: string;
  readonly message: string;
  readonly details?: readonly SafeErrorDetail[];
}

export interface SafeErrorResponse {
  readonly error: SafeErrorBody;
}
