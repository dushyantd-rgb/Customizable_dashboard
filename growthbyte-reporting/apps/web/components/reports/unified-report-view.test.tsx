import type {
  ReportAnalysisItem,
  ReportMetric,
  SuperKFranchiseReportResponse,
} from "@growthbyte/report-schema";
import { render, screen } from "@testing-library/react";

import { formatReportMetric, UnifiedReportView } from "./unified-report-view";

function claim(
  statement: string,
  evidenceIds: readonly [string, ...string[]] = ["metric:spend"],
): ReportAnalysisItem {
  return {
    statement,
    evidence_ids: evidenceIds,
    confidence: "high",
    limitation: null,
  };
}

function metric(overrides: Pick<ReportMetric, "metric_key"> & Partial<ReportMetric>): ReportMetric {
  const { metric_key: metricKey, ...rest } = overrides;
  return {
    metric_key: metricKey,
    value: null,
    unit: "count",
    currency: null,
    numerator: null,
    denominator: null,
    previous_value: null,
    absolute_change: null,
    percentage_change: null,
    kpi_target: null,
    kpi_variance: null,
    quality_status: "unavailable",
    evidence_id: `metric:${metricKey}`,
    formula_version: "superk-franchise-v1",
    ...rest,
  };
}

function reportFixture(
  overrides: Partial<SuperKFranchiseReportResponse> = {},
): SuperKFranchiseReportResponse {
  return {
    client_id: "10000000-0000-4000-8000-000000000001",
    vertical: "b2b_franchise",
    report_month: "2026-07",
    quality_status: "verified",
    snapshot_id: "20000000-0000-4000-8000-000000000002",
    snapshot_reused: true,
    report_id: "30000000-0000-4000-8000-000000000003",
    report_status: "approved",
    sources: {
      meta: { status: "succeeded", detail: "Meta data loaded." },
      gsc: { status: "succeeded", detail: "Search Console data loaded." },
      lead_json: { status: "succeeded", detail: "Aggregate lead file loaded." },
      knowledge: { status: "succeeded", detail: "4 approved knowledge sections." },
      kpis: { status: "succeeded", detail: "3 KPI targets." },
    },
    monthly_snapshot: {
      id: "20000000-0000-4000-8000-000000000002",
      formula_version: "superk-franchise-v1",
      input_hash: "stable-input-hash",
      quality_status: "verified",
      metrics: [
        metric({
          metric_key: "spend",
          value: "125000",
          previous_value: "100000",
          absolute_change: "25000",
          percentage_change: "25",
          unit: "currency",
          currency: "INR",
          quality_status: "verified",
          evidence_id: "metric:spend",
        }),
        metric({
          metric_key: "link_clicks",
          value: 5000,
          previous_value: 4500,
          absolute_change: 500,
          percentage_change: 11.11,
          unit: "count",
          quality_status: "verified",
          evidence_id: "metric:link_clicks",
        }),
        metric({
          metric_key: "total_leads",
          value: 100,
          previous_value: 110,
          absolute_change: -10,
          percentage_change: -9.09,
          unit: "count",
          quality_status: "verified",
          evidence_id: "metric:total_leads",
        }),
        metric({
          metric_key: "rtm_leads",
          value: 25,
          previous_value: 20,
          absolute_change: 5,
          percentage_change: 25,
          unit: "count",
          quality_status: "verified",
          evidence_id: "metric:rtm_leads",
        }),
        metric({
          metric_key: "organic_clicks",
          value: 2400,
          previous_value: 2000,
          absolute_change: 400,
          percentage_change: 20,
          unit: "count",
          quality_status: "verified",
          evidence_id: "metric:organic_clicks",
        }),
        metric({
          metric_key: "organic_average_position",
          value: 8.4,
          previous_value: 9.1,
          absolute_change: -0.7,
          percentage_change: -7.69,
          unit: "position",
          quality_status: "verified",
          evidence_id: "metric:organic_average_position",
        }),
      ],
    },
    sections: {
      executive_summary: [claim("Lead volume declined while paid spend increased.")],
      paid_performance_summary: [claim("Paid reach remained efficient.")],
      lead_and_rtm_funnel: [claim("RTM conversion improved.")],
      search_console_seo_summary: [claim("Organic clicks improved.")],
      campaign_and_creative_observations: [
        claim("Creative A generated stronger engagement.", ["metric:link_clicks"]),
      ],
      search_query_and_page_movements: [claim("Franchise query visibility improved.")],
      important_wins: [claim("Organic clicks increased.", ["metric:organic_clicks"])],
      important_problems: [claim("Operational leads declined.", ["metric:total_leads"])],
      recommended_actions: [claim("Test the stronger creative with a controlled budget.")],
      data_reconciliation_and_limitations: [
        claim("Meta and operational lead counts are shown separately."),
      ],
    },
    warnings: [],
    pdf: {
      download_url: "/api/v1/clients/client/reports/report/exports/export/download",
      snapshot_id: "20000000-0000-4000-8000-000000000002",
    },
    ...overrides,
  };
}

describe("UnifiedReportView", () => {
  it("formats Pydantic Decimal strings as numeric values", () => {
    expect(formatReportMetric("1234.5", "count")).toBe("1,234.5");
    expect(formatReportMetric("0", "percent")).toBe("0%");
  });

  it("renders the unified sections, comparison, evidence, and approved PDF", () => {
    render(<UnifiedReportView report={reportFixture()} />);

    expect(screen.getByRole("heading", { name: "Current versus previous month" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Paid performance" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Lead and RTM funnel" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Google Search Console" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Important wins" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Important problems" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Recommended actions" })).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Data reconciliation and limitations" }),
    ).toBeTruthy();
    expect(screen.getAllByText("metric:spend").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Average position").length).toBeGreaterThan(1);
    expect(screen.getByRole("link", { name: "Download PDF" }).getAttribute("href")).toContain(
      "/exports/export/download",
    );
  });

  it("does not expose a PDF link before approval even when a URL is supplied", () => {
    render(<UnifiedReportView report={reportFixture({ report_status: "draft" })} />);

    expect(screen.queryByRole("link", { name: "Download PDF" })).toBeNull();
  });

  it("distinguishes valid zero values from unavailable values", () => {
    const fixture = reportFixture();
    render(
      <UnifiedReportView
        report={{
          ...fixture,
          monthly_snapshot: {
            ...fixture.monthly_snapshot!,
            metrics: [
              metric({
                metric_key: "link_clicks",
                value: 0,
                unit: "count",
                quality_status: "verified",
              }),
              metric({
                metric_key: "cost_per_lead",
                value: null,
                unit: "currency",
                currency: "INR",
                quality_status: "unavailable",
              }),
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("0")).toBeTruthy();
    expect(screen.getAllByText("Unavailable.").length).toBeGreaterThan(0);
    expect(screen.getByText("Previous-month comparison is unavailable.")).toBeTruthy();
  });
});
