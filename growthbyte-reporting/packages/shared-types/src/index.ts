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

export interface MetaAccountSummary {
  readonly external_account_id: string;
  readonly name: string | null;
  readonly currency: string | null;
  readonly account_timezone: string | null;
  readonly account_status: string | null;
}

export interface MetaAccountDiscoveryResponse {
  readonly accounts: readonly MetaAccountSummary[];
}

export interface MetaConnectionInput {
  external_account_id: string;
  display_name?: string | null;
}

export interface MetaSyncInput {
  date_from: string;
  date_to: string;
  include_campaigns?: boolean;
  include_ad_sets?: boolean;
  include_ads?: boolean;
  include_insights?: boolean;
}

export interface MetaSyncResult {
  readonly sync_run_id: string;
  readonly client_id: string;
  readonly external_account_id: string;
  readonly status: string;
  readonly rows_read: number;
  readonly rows_written: number;
  readonly campaigns_synced: number;
  readonly ad_sets_synced: number;
  readonly ads_synced: number;
  readonly insights_synced: number;
  readonly error_summary: string | null;
}

export interface SpreadsheetSummary {
  readonly id: string;
  readonly name: string | null;
  readonly permissions: string | null;
}

export interface WorksheetSummary {
  readonly name: string;
  readonly sheet_id: number;
  readonly row_count: number;
}

export interface GoogleSheetConfigInput {
  spreadsheet_id: string;
  worksheet_name: string;
  header_row: number;
  data_start_row: number;
}

export interface ColumnMappingInput {
  source_header: string;
  canonical_field: string;
  required: boolean;
}

export interface StatusMappingInput {
  source_value: string;
  canonical_status: string;
  counts_as_reviewed: boolean;
}

export interface GoogleSyncResult {
  readonly sync_run_id: string;
  readonly client_id: string;
  readonly spreadsheet_id: string;
  readonly worksheet_name: string;
  readonly status: string;
  readonly rows_read: number;
  readonly rows_written: number;
  readonly rows_skipped: number;
  readonly error_summary: string | null;
}

export interface SyncRunSummary {
  readonly id: string;
  readonly client_id: string;
  readonly source_type: string;
  readonly status: string;
  readonly started_at: string | null;
  readonly finished_at: string | null;
  readonly rows_read: number;
  readonly rows_written: number;
  readonly rows_rejected: number;
  readonly error_summary: string | null;
  readonly created_at: string;
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
