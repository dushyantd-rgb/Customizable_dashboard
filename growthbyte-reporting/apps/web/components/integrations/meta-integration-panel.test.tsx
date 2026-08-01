import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithFreshSWR } from "../test-utils";
import { MetaIntegrationPanel } from "./meta-integration-panel";

const clientId = "10000000-0000-4000-8000-000000000001";

describe("MetaIntegrationPanel", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("assigns one account, tests it, and manually syncs a client-scoped date range", async () => {
    const fetchMock = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith(`/integrations/meta/clients/${clientId}/accounts`)) {
        return Promise.resolve(
          jsonResponse({
            accounts: [
              {
                external_account_id: "123456",
                name: "Development Meta",
                currency: "USD",
                account_timezone: "UTC",
                account_status: "1",
              },
            ],
          }),
        );
      }
      if (url.endsWith("/sync-runs")) return Promise.resolve(jsonResponse([]));
      if (url.endsWith("/config") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            connection_id: "connection-1",
            external_account_id: "123456",
            display_name: "Development Meta",
          }),
        );
      }
      if (url.endsWith("/test") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ connected: true }));
      }
      if (url.endsWith("/sync") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            sync_run_id: "sync-1",
            client_id: clientId,
            external_account_id: "123456",
            status: "succeeded",
            rows_read: 12,
            rows_written: 12,
            campaigns_synced: 2,
            ad_sets_synced: 3,
            ads_synced: 4,
            insights_synced: 3,
            error_summary: null,
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    global.fetch = fetchMock;
    const user = userEvent.setup();

    renderWithFreshSWR(<MetaIntegrationPanel clientId={clientId} />);

    await user.selectOptions(await screen.findByLabelText("Meta ad account"), "123456");
    await user.click(screen.getByRole("button", { name: "Assign account" }));
    expect(await screen.findByText("Meta account assigned to this client.")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Test Meta connection" }));
    expect(await screen.findByText("Meta connection is ready.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-07-03" } });
    await user.click(screen.getByRole("button", { name: "Run Meta sync" }));
    expect(await screen.findByText("Meta sync succeeded: 12 read, 12 upserted.")).toBeTruthy();

    await waitFor(() => {
      const syncCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/sync") && init?.method === "POST",
      );
      expect(String(syncCall?.[0])).toContain(`/clients/${clientId}/sync`);
      expect(JSON.parse(String(syncCall?.[1]?.body))).toEqual({
        date_from: "2026-07-01",
        date_to: "2026-07-03",
      });
    });
  });

  it("rejects a reversed date range before calling sync", async () => {
    const fetchMock = jest.fn().mockImplementation((url: string) => {
      if (url.includes("/accounts")) return Promise.resolve(jsonResponse({ accounts: [] }));
      if (url.endsWith("/sync-runs")) return Promise.resolve(jsonResponse([]));
      throw new Error(`Unexpected request: ${url}`);
    });
    global.fetch = fetchMock;
    const user = userEvent.setup();

    renderWithFreshSWR(<MetaIntegrationPanel clientId={clientId} />);
    await screen.findByText(/No Meta ad accounts/);
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-03" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-07-01" } });
    await user.click(screen.getByRole("button", { name: "Run Meta sync" }));

    expect(await screen.findByText("Choose a valid Meta sync date range.")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/sync"))).toBe(false);
  });
});
