import type { KpiRecord } from "@growthbyte/shared-types";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithFreshSWR } from "../test-utils";
import { KpiManager } from "./kpi-manager";

const kpi: KpiRecord = {
  id: "50000000-0000-4000-8000-000000000005",
  client_id: "10000000-0000-4000-8000-000000000001",
  metric_key: "qualified_leads",
  label: "Qualified leads",
  target_value: "25.00",
  unit: "count",
  direction: "increase",
  attribution_level: "client",
  active_from: "2026-08-01",
  active_to: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

describe("KpiManager", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("shows schema-backed KPI values without calculating performance", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse([kpi]));

    renderWithFreshSWR(<KpiManager clientId={kpi.client_id} reportingTimezone="UTC" />);

    expect(await screen.findByRole("heading", { name: "Qualified leads" })).toBeTruthy();
    expect(screen.getByText("25.00")).toBeTruthy();
    expect(screen.getByText("count")).toBeTruthy();
    expect(screen.getByText("Open-ended")).toBeTruthy();
    expect(screen.queryByText(/actual performance/i)).toBeNull();
  });

  it("rejects an invalid effective-date interval before mutation", async () => {
    const fetchMock = jest.fn().mockResolvedValue(jsonResponse([kpi]));
    global.fetch = fetchMock;
    const user = userEvent.setup();

    renderWithFreshSWR(<KpiManager clientId={kpi.client_id} reportingTimezone="UTC" />);
    await user.click(await screen.findByRole("button", { name: "Edit Qualified leads" }));
    fireEvent.change(screen.getByLabelText("Active from"), { target: { value: "2026-08-10" } });
    fireEvent.change(screen.getByLabelText("Active to (optional)"), {
      target: { value: "2026-08-09" },
    });
    await user.click(screen.getByRole("button", { name: "Save KPI" }));

    expect(await screen.findByText("Active-to cannot be before active-from.")).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);
  });
});
