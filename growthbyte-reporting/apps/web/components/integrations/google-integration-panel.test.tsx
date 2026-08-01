import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithFreshSWR } from "../test-utils";
import { GoogleIntegrationPanel } from "./google-integration-panel";

const clientId = "10000000-0000-4000-8000-000000000001";

describe("GoogleIntegrationPanel", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("discovers a Sheet, saves approved mappings, and runs a read-only sync", async () => {
    const fetchMock = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith(`/clients/${clientId}/sync-runs`)) return Promise.resolve(jsonResponse([]));
      if (url.endsWith(`/clients/${clientId}/spreadsheets`)) {
        return Promise.resolve(
          jsonResponse([{ id: "sheet-1", name: "Development leads", permissions: "view" }]),
        );
      }
      if (url.endsWith(`/clients/${clientId}/spreadsheets/sheet-1/worksheets`)) {
        return Promise.resolve(jsonResponse([{ name: "Leads", sheet_id: 7, row_count: 25 }]));
      }
      if (url.includes("/sheet-1/worksheets/Leads/preview?header_row=1&data_start_row=2")) {
        return Promise.resolve(jsonResponse({ headers: ["Lead ID", "Status"], sample_rows: [] }));
      }
      if (url.endsWith(`/clients/${clientId}/config`) && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ config_id: "config-1" }));
      }
      if (url.includes(`/clients/${clientId}/config/config-1/column-mappings`)) {
        return Promise.resolve(jsonResponse({ mappings_saved: 2 }));
      }
      if (url.includes(`/clients/${clientId}/config/config-1/status-mappings`)) {
        return Promise.resolve(jsonResponse({ mappings_saved: 1 }));
      }
      if (url.endsWith(`/clients/${clientId}/sync`) && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            sync_run_id: "sync-1",
            client_id: clientId,
            spreadsheet_id: "sheet-1",
            worksheet_name: "Leads",
            status: "succeeded",
            rows_read: 20,
            rows_written: 18,
            rows_skipped: 2,
            error_summary: null,
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    global.fetch = fetchMock;
    const user = userEvent.setup();

    renderWithFreshSWR(<GoogleIntegrationPanel clientId={clientId} />);

    const connectLink = screen.getByRole("link", { name: "Connect Google" });
    expect(connectLink.getAttribute("href")).toContain(`/clients/${clientId}/oauth/start`);
    await user.click(screen.getByRole("button", { name: "Discover spreadsheets" }));
    expect(await screen.findByText("Found 1 readable spreadsheet(s).")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Load worksheets" }));
    await user.selectOptions(await screen.findByLabelText("Worksheet"), "Leads");
    await user.click(screen.getByRole("button", { name: "Preview headers" }));
    await user.selectOptions(await screen.findByLabelText("Map Lead ID"), "source_lead_id");
    await user.selectOptions(screen.getByLabelText("Map Status"), "lead_status");
    await user.click(screen.getByLabelText("Require Lead ID"));
    fireEvent.change(screen.getByLabelText("Source status 1"), { target: { value: "Won" } });
    await user.selectOptions(screen.getByLabelText("Canonical status 1"), "converted");
    await user.click(screen.getByLabelText("Counts as reviewed"));

    await user.click(screen.getByRole("button", { name: "Save Sheet mapping" }));
    expect(
      await screen.findByText("Saved 2 column mapping(s) and 1 status mapping(s)."),
    ).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Run Google Sheet sync" }));
    expect(
      await screen.findByText("Google sync succeeded: 20 read, 18 upserted, 2 skipped."),
    ).toBeTruthy();

    await waitFor(() => {
      const columnCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/column-mappings"),
      );
      const statusCall = fetchMock.mock.calls.find(([url]) =>
        String(url).includes("/status-mappings"),
      );
      expect(JSON.parse(String(columnCall?.[1]?.body))).toEqual([
        { source_header: "Lead ID", canonical_field: "source_lead_id", required: true },
        { source_header: "Status", canonical_field: "lead_status", required: false },
      ]);
      expect(JSON.parse(String(statusCall?.[1]?.body))).toEqual([
        { source_value: "Won", canonical_status: "converted", counts_as_reviewed: true },
      ]);
    });
  });

  it("requires mapped columns before configuration writes", async () => {
    const fetchMock = jest.fn().mockImplementation((url: string) => {
      if (url.endsWith(`/clients/${clientId}/sync-runs`)) return Promise.resolve(jsonResponse([]));
      if (url.endsWith(`/clients/${clientId}/spreadsheets/sheet-1/worksheets`)) {
        return Promise.resolve(jsonResponse([{ name: "Leads", sheet_id: 7, row_count: 2 }]));
      }
      if (url.includes("/sheet-1/worksheets/Leads/preview")) {
        return Promise.resolve(jsonResponse({ headers: ["Unknown"], sample_rows: [] }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    global.fetch = fetchMock;
    const user = userEvent.setup();

    renderWithFreshSWR(<GoogleIntegrationPanel clientId={clientId} />);
    fireEvent.change(screen.getByLabelText("Spreadsheet"), { target: { value: "sheet-1" } });
    await user.click(screen.getByRole("button", { name: "Load worksheets" }));
    await user.selectOptions(await screen.findByLabelText("Worksheet"), "Leads");
    await user.click(screen.getByRole("button", { name: "Preview headers" }));
    await screen.findByText("Read 1 worksheet header(s).");
    await user.click(screen.getByRole("button", { name: "Save Sheet mapping" }));

    expect(await screen.findByText("Map at least one Sheet column.")).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes(`/clients/${clientId}/config`)),
    ).toBe(false);
  });
});
