import { api, SafeApiError } from "./api-client";

describe("API client", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("surfaces only the backend safe-error contract", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({
        error: { code: "client_not_found", message: "Client was not found" },
      }),
      ok: false,
    });

    await expect(api.getClient("client-a")).rejects.toEqual(
      expect.objectContaining<Partial<SafeApiError>>({
        code: "client_not_found",
        message: "Client was not found",
      }),
    );
  });

  it("does not expose an unstructured backend response", async () => {
    const rawDetail = "database=https://private.example.test service_role=secret";
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({ detail: rawDetail }),
      ok: false,
    });

    await expect(api.listClients()).rejects.toThrow(
      "The request could not be completed. Please try again.",
    );
    try {
      await api.listClients();
    } catch (error) {
      expect(String(error)).not.toContain(rawDetail);
    }
  });

  it("keeps client scope in the path and out of mutation data", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      json: async () => ({}),
      ok: true,
    });
    global.fetch = fetchMock;

    await api.updateKnowledge("client/a", "record?one", {
      status: "approved",
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/clients/client%2Fa/knowledge/record%3Fone");
    expect(JSON.parse(String(init.body))).toEqual({ status: "approved" });
    expect(String(init.body)).not.toContain("client_id");
  });

  it("client-scopes and encodes integration routes", async () => {
    const fetchMock = jest.fn().mockResolvedValue({ json: async () => ({}), ok: true });
    global.fetch = fetchMock;

    await api.listMetaAccounts("client/a");
    await api.listGoogleWorksheets("client/a", "sheet?one");
    await api.previewGoogleSheet("client/a", "sheet?one", "Leads / 2026", 3, 4);

    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/integrations/meta/clients/client%2Fa/accounts",
    );
    expect(String(fetchMock.mock.calls[1][0])).toContain(
      "/integrations/google/clients/client%2Fa/spreadsheets/sheet%3Fone/worksheets",
    );
    expect(String(fetchMock.mock.calls[2][0])).toContain(
      "/sheet%3Fone/worksheets/Leads%20%2F%202026/preview?header_row=3&data_start_row=4",
    );
  });

  it("never places OAuth or provider tokens in integration mutation bodies", async () => {
    const fetchMock = jest.fn().mockResolvedValue({ json: async () => ({}), ok: true });
    global.fetch = fetchMock;

    await api.configureMeta("client-a", {
      external_account_id: "123456",
      display_name: "Development account",
    });
    await api.configureGoogleSheet("client-a", {
      spreadsheet_id: "sheet-1",
      worksheet_name: "Leads",
      header_row: 1,
      data_start_row: 2,
    });

    for (const [, init] of fetchMock.mock.calls as [string, RequestInit][]) {
      const body = String(init.body);
      expect(body).not.toMatch(/access_token|refresh_token|client_secret|service_role/i);
    }
  });

  it("generates the SuperK Franchise report with an empty client-scoped request", async () => {
    const fetchMock = jest.fn().mockResolvedValue({ json: async () => ({}), ok: true });
    global.fetch = fetchMock;

    await api.generateSuperKFranchiseReport("client/one");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/clients/client%2Fone/superk-franchise-report/generate");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });
});
