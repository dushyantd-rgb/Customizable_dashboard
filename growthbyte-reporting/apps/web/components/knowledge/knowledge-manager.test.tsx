import type { KnowledgeRecord } from "@growthbyte/shared-types";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderWithFreshSWR } from "../test-utils";
import { KnowledgeManager } from "./knowledge-manager";

const records: KnowledgeRecord[] = [
  {
    id: "30000000-0000-4000-8000-000000000003",
    client_id: "10000000-0000-4000-8000-000000000001",
    category: "Brand",
    knowledge_key: "voice",
    value: { tone: "warm" },
    status: "approved",
    source_type: "knowledge_supabase.org_knowledge_base_sections",
    source_identifier: "source-section-1",
    source_display_name: "Brand voice",
    source_reference: "org_knowledge_base_sections",
    source_version: "4",
    imported_at: "2026-08-01T00:00:00Z",
    version: 4,
    approved_by_label: null,
    approved_at: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
  },
  {
    id: "40000000-0000-4000-8000-000000000004",
    client_id: "10000000-0000-4000-8000-000000000001",
    category: "Offering",
    knowledge_key: "primary-service",
    value: { name: "De-identified service" },
    status: "draft",
    source_type: "manual",
    source_identifier: null,
    source_display_name: null,
    source_reference: null,
    source_version: null,
    imported_at: null,
    version: 1,
    approved_by_label: null,
    approved_at: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
  },
];

describe("KnowledgeManager", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("groups knowledge and distinguishes imported from manual records without deletion", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(records));

    renderWithFreshSWR(<KnowledgeManager clientId={records[0].client_id} />);

    expect(await screen.findByRole("heading", { name: "Brand" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Offering" })).toBeTruthy();
    expect(screen.getByText("Imported")).toBeTruthy();
    expect(screen.getByText("Manual")).toBeTruthy();
    expect(screen.getByText("Brand voice")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
  });

  it("requires explicit confirmation before overwriting a value", async () => {
    const fetchMock = jest.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({
            ...records[0],
            value: { tone: "direct" },
            updated_at: "2026-08-02T00:00:00Z",
          }),
        );
      }
      return Promise.resolve(jsonResponse(records));
    });
    global.fetch = fetchMock;
    const user = userEvent.setup();

    renderWithFreshSWR(<KnowledgeManager clientId={records[0].client_id} />);
    await user.click(await screen.findByRole("button", { name: "Edit voice" }));
    fireEvent.change(screen.getByLabelText("Value (JSON)"), {
      target: { value: '{"tone":"direct"}' },
    });
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Overwrite this knowledge value?")).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Overwrite value" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1),
    );
    const patchCall = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(String(patchCall?.[1]?.body)).not.toContain("source_identifier");
    expect(String(patchCall?.[1]?.body)).not.toContain("client_id");
  });

  it("rejects a non-object JSON value before mutation", async () => {
    const fetchMock = jest.fn().mockResolvedValue(jsonResponse(records));
    global.fetch = fetchMock;
    const user = userEvent.setup();

    renderWithFreshSWR(<KnowledgeManager clientId={records[0].client_id} />);
    await user.click(await screen.findByRole("button", { name: "Edit voice" }));
    fireEvent.change(screen.getByLabelText("Value (JSON)"), {
      target: { value: '["not", "an", "object"]' },
    });
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Value must be a valid JSON object.")).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);
  });
});
