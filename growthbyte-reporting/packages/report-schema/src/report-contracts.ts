export type ReportQualityStatus = "verified" | "partial" | "unavailable";

export type ReportLifecycleStatus = "draft" | "in_review" | "approved" | "not_created";

export type MetricUnit = "count" | "currency" | "percent" | "position";

/**
 * Pydantic serializes Decimal values as JSON strings so that the API does not
 * silently lose precision. Number remains accepted for fixtures and any
 * non-Decimal values returned by a future source adapter.
 */
export type ReportNumericValue = string | number;

export interface ReportMetric {
  readonly metric_key: string;
  readonly value: ReportNumericValue | null;
  readonly unit: MetricUnit;
  readonly currency: string | null;
  readonly numerator: ReportNumericValue | null;
  readonly denominator: ReportNumericValue | null;
  readonly previous_value: ReportNumericValue | null;
  readonly absolute_change: ReportNumericValue | null;
  readonly percentage_change: ReportNumericValue | null;
  readonly kpi_target: ReportNumericValue | null;
  readonly kpi_variance: ReportNumericValue | null;
  readonly quality_status: ReportQualityStatus;
  readonly evidence_id: string;
  readonly formula_version: string;
}

export interface ReportAnalysisItem {
  readonly statement: string;
  readonly evidence_ids: readonly [string, ...string[]];
  readonly confidence: "high" | "medium" | "low";
  readonly limitation: string | null;
}

export type ReportSectionContent = readonly [ReportAnalysisItem, ...ReportAnalysisItem[]];

export interface SuperKReportSections {
  readonly executive_summary: ReportSectionContent;
  readonly paid_performance_summary: ReportSectionContent;
  readonly lead_and_rtm_funnel: ReportSectionContent;
  readonly search_console_seo_summary: ReportSectionContent;
  readonly campaign_and_creative_observations: ReportSectionContent;
  readonly search_query_and_page_movements: ReportSectionContent;
  readonly important_wins: ReportSectionContent;
  readonly important_problems: ReportSectionContent;
  readonly recommended_actions: ReportSectionContent;
  readonly data_reconciliation_and_limitations: ReportSectionContent;
}

export interface ReportWarning {
  readonly code: string;
  readonly message: string;
}

export type ReportSourceStatusValue =
  "ready" | "succeeded" | "partial" | "unavailable" | "not_configured" | "rejected";

export interface ReportSourceStatus {
  readonly status: ReportSourceStatusValue;
  readonly detail: string;
  readonly synced_at?: string | null;
}

export interface SuperKReportSources {
  readonly meta: ReportSourceStatus;
  readonly gsc: ReportSourceStatus;
  readonly lead_json: ReportSourceStatus;
  readonly knowledge: ReportSourceStatus;
  readonly kpis: ReportSourceStatus;
}

export interface SuperKMonthlySnapshot {
  readonly id: string;
  readonly formula_version: string;
  readonly input_hash: string;
  readonly quality_status: ReportQualityStatus;
  readonly metrics: readonly ReportMetric[];
}

export interface ReportPdfExport {
  readonly download_url: string;
  readonly export_id?: string | null;
  readonly snapshot_id?: string | null;
}

export interface SuperKFranchiseReportResponse {
  readonly client_id: string;
  readonly vertical: "b2b_franchise";
  readonly report_month: string;
  readonly quality_status: ReportQualityStatus;
  readonly snapshot_id: string | null;
  readonly snapshot_reused: boolean;
  readonly report_id: string | null;
  readonly report_status: ReportLifecycleStatus;
  readonly sources: SuperKReportSources;
  readonly monthly_snapshot: SuperKMonthlySnapshot | null;
  readonly sections: SuperKReportSections;
  readonly warnings: readonly ReportWarning[];
  readonly pdf?: ReportPdfExport | null;
}
