import type { SuperKFranchiseReportResponse } from "@growthbyte/report-schema";
import { fireEvent, render, screen } from "@testing-library/react";

import { jsonResponse } from "../test-utils";
import { SuperKReportGenerator } from "./superk-report-generator";

const generatedReport: SuperKFranchiseReportResponse = {
  client_id: "10000000-0000-4000-8000-000000000001",
  vertical: "b2b_franchise" as const,
  report_month: "2026-07",
  quality_status: "partial" as const,
  snapshot_id: "20000000-0000-4000-8000-000000000002",
  snapshot_reused: false,
  report_id: "30000000-0000-4000-8000-000000000003",
  report_status: "draft" as const,
  sources: {
    meta: { status: "succeeded", detail: "Meta data loaded." },
    gsc: { status: "partial", detail: "Search Console totals are incomplete." },
    lead_json: { status: "unavailable", detail: "The configured file is a Meta export." },
    knowledge: { status: "succeeded", detail: "4 approved knowledge sections." },
    kpis: { status: "succeeded", detail: "3 KPI targets." },
  },
  monthly_snapshot: {
    id: "20000000-0000-4000-8000-000000000002",
    formula_version: "superk-franchise-v1",
    input_hash: "input-hash",
    quality_status: "partial" as const,
    metrics: [
      {
        metric_key: "source_availability",
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
        evidence_id: "metric:source_availability",
        formula_version: "superk-franchise-v1",
      },
    ],
  },
  sections: {
    executive_summary: [
      {
        statement: "Verified paid performance is available.",
        evidence_ids: ["metric:source_availability"],
        confidence: "high",
        limitation: null,
      },
    ],
    paid_performance_summary: [
      {
        statement: "Paid summary.",
        evidence_ids: ["metric:source_availability"],
        confidence: "high",
        limitation: null,
      },
    ],
    lead_and_rtm_funnel: [
      {
        statement: "RTM metrics are unavailable.",
        evidence_ids: ["metric:source_availability"],
        confidence: "low",
        limitation: "The lead source is unavailable.",
      },
    ],
    search_console_seo_summary: [
      {
        statement: "SEO summary.",
        evidence_ids: ["metric:source_availability"],
        confidence: "medium",
        limitation: null,
      },
    ],
    campaign_and_creative_observations: [
      {
        statement: "Creative-level evidence is unavailable.",
        evidence_ids: ["metric:source_availability"],
        confidence: "low",
        limitation: "No creative breakdown was returned.",
      },
    ],
    search_query_and_page_movements: [
      {
        statement: "Query movement evidence is unavailable.",
        evidence_ids: ["metric:source_availability"],
        confidence: "low",
        limitation: "Search Console data is partial.",
      },
    ],
    important_wins: [
      {
        statement: "Paid data was verified.",
        evidence_ids: ["metric:source_availability"],
        confidence: "high",
        limitation: null,
      },
    ],
    important_problems: [
      {
        statement: "Operational lead data is unavailable.",
        evidence_ids: ["metric:source_availability"],
        confidence: "high",
        limitation: null,
      },
    ],
    recommended_actions: [
      {
        statement: "Provide a compatible operational lead export.",
        evidence_ids: ["metric:source_availability"],
        confidence: "high",
        limitation: null,
      },
    ],
    data_reconciliation_and_limitations: [
      {
        statement: "Lead JSON does not contain RTM data.",
        evidence_ids: ["metric:source_availability"],
        confidence: "high",
        limitation: null,
      },
    ],
  },
  warnings: [{ code: "lead_json_incompatible", message: "RTM metrics are unavailable." }],
};

describe("SuperKReportGenerator", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("starts with one Generate report action and no configuration controls", () => {
    const { container } = render(
      <SuperKReportGenerator clientId="10000000-0000-4000-8000-000000000001" />,
    );

    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Generate report" })).toBeTruthy();
    expect(container.querySelector("input, select, textarea")).toBeNull();
    expect(screen.queryByText(/upload/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /configure|sync|upload/i })).toBeNull();
  });

  it("posts an empty body and renders the generated partial report", async () => {
    const fetchMock = jest.fn().mockResolvedValue(jsonResponse(generatedReport));
    global.fetch = fetchMock;
    render(<SuperKReportGenerator clientId="client/one" />);

    fireEvent.click(screen.getByRole("button", { name: "Generate report" }));

    expect(await screen.findByTestId("unified-report")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/clients/client%2Fone/superk-franchise-report/generate");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
    expect(screen.getAllByText("partial").length).toBeGreaterThan(0);
    expect(screen.getAllByText("RTM metrics are unavailable.").length).toBeGreaterThan(0);
  });

  it("shows only the safe API error and allows retry", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: "superk_configuration_missing",
            message: "The SuperK report configuration is incomplete",
          },
        },
        false,
      ),
    );
    render(<SuperKReportGenerator clientId="client-a" />);

    fireEvent.click(screen.getByRole("button", { name: "Generate report" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "The SuperK report configuration is incomplete",
    );
    expect(screen.getByRole("button", { name: "Generate report" }).hasAttribute("disabled")).toBe(
      false,
    );
  });
});
