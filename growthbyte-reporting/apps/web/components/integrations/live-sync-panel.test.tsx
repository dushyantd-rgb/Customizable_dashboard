import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithFreshSWR } from "../test-utils";
import { LiveSyncPanel } from "./live-sync-panel";

const clientId = "10000000-0000-4000-8000-000000000001";

describe("LiveSyncPanel", () => {
  beforeEach(() => {
    jest.useFakeTimers({ doNotFake: ["nextTick", "setImmediate"] });
    jest.setSystemTime(new Date(2026, 7, 15, 12));
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("defaults Meta to month-to-date and lets the operator change the existing date filter", async () => {
    const fetchMock = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/sync-runs")) return Promise.resolve(jsonResponse([]));
      if (url.endsWith(`/clients/${clientId}/sync`) && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            sync_run_id: "sync-1",
            client_id: clientId,
            external_account_id: "123456",
            status: "succeeded",
            rows_read: 10,
            rows_written: 10,
            campaigns_synced: 1,
            ad_sets_synced: 2,
            ads_synced: 3,
            insights_synced: 4,
            error_summary: null,
          }),
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    global.fetch = fetchMock;
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    renderWithFreshSWR(<LiveSyncPanel clientId={clientId} />);

    expect((screen.getByLabelText("Start date") as HTMLInputElement).value).toBe("2026-08-01");
    expect((screen.getByLabelText("End date") as HTMLInputElement).value).toBe("2026-08-15");

    fireEvent.change(screen.getByLabelText("Start date"), {
      target: { value: "2026-07-01" },
    });
    fireEvent.change(screen.getByLabelText("End date"), {
      target: { value: "2026-07-31" },
    });
    await user.click(screen.getByRole("button", { name: "Sync Meta Ads" }));

    expect(await screen.findByText("Meta sync succeeded: 10 read, 10 upserted.")).toBeTruthy();
    await waitFor(() => {
      const syncCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/sync") && init?.method === "POST",
      );
      expect(JSON.parse(String(syncCall?.[1]?.body))).toEqual({
        date_from: "2026-07-01",
        date_to: "2026-07-31",
      });
    });
  });

  it("exposes client-bound Google OAuth and Google Sheet sync", async () => {
    const fetchMock = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/sync-runs")) return Promise.resolve(jsonResponse([]));
      if (
        url.includes("/integrations/google/") &&
        url.endsWith(`/clients/${clientId}/sync`) &&
        init?.method === "POST"
      ) {
        return Promise.resolve(
          jsonResponse({
            sync_run_id: "sync-2",
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
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    renderWithFreshSWR(<LiveSyncPanel clientId={clientId} />);

    expect(screen.getByRole("link", { name: "Connect Google" }).getAttribute("href")).toContain(
      `/clients/${clientId}/oauth/start`,
    );
    await user.click(screen.getByRole("button", { name: "Sync Google Sheets" }));

    expect(
      await screen.findByText("Google sync succeeded: 20 read, 18 upserted, 2 skipped."),
    ).toBeTruthy();
  });
});
